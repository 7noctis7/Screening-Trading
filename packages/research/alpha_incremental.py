"""Le NLP apporte-t-il quelque chose que le lexique n'avait pas ? — mesuré, pas supposé.

CE QUE CE MODULE DÉCIDE. Le poids du NLP dans le système : validé, ou ZÉRO. Le cahier des
charges le demande explicitement (point 29), et c'est la seule question qui justifie ou non
la suite du chantier — un GPU loué pour accélérer un signal qui n'existe pas est une
dépense, pas un investissement.

LE PIÈGE QU'IL ÉVITE, ET QUI INVALIDE LA PLUPART DES COMPARAISONS. `sentiment_event_study`
écarte les événements dont le score est nul. Or « score nul » dépend DU SCOREUR : le
lexique ignore un titre sans mot de son dictionnaire, le LLM le classe NEUTRE, et pas sur
les mêmes titres. Comparer les deux ainsi les mesure sur des ÉCHANTILLONS DIFFÉRENTS, et
l'écart observé mélange alors deux choses inséparables — une différence de pouvoir prédictif
et une différence de sélection. On extrait donc les événements UNE fois, puis on demande à
chaque scoreur de noter EXACTEMENT les mêmes.

Cela rend aussi la comparaison APPARIÉE : chaque événement a une note par scoreur, donc les
différences se testent par paires, ce qui est bien plus puissant qu'une comparaison de deux
moyennes indépendantes sur le même nombre d'observations.

LE POINT-IN-TIME VIENT DU CORPUS, PAS DE LA DATE. Un titre entre dans l'étude à partir de
`max(date, vu_le)` (cf. `packages.sentiment.corpus`) : ni avant sa publication, ni avant
qu'on ait pu le lire. Se fier à la date de publication seule laisserait une stratégie
« savoir » avant d'avoir pu savoir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from packages.portfolio.psr import deflated_sharpe_ratio

MIN_EVENEMENTS = 30       # en dessous, aucun IC ne veut rien dire
PLACEBO_TIRAGES = 500


@dataclass(frozen=True)
class Evenement:
    """Un titre, et le rendement qui a SUIVI — indépendant de tout scoreur."""

    symbole: str
    jour: str                 # `max(date, vu_le)` : l'instant où l'info devient utilisable
    titre: str
    rendement: float


def extraire(data: dict, corpus: list[dict], hold: int = 5,
             entry_lag: int = 1) -> list[Evenement]:
    """Les événements exploitables, UNE fois pour tous les scoreurs.

    `entry_lag=1` : on entre au close SUIVANT la disponibilité de l'information. Entrer le
    jour même supposerait d'avoir lu, décidé et exécuté avant la clôture — ce qui est
    précisément le look-ahead que tout le monde s'accorde à dénoncer et que beaucoup
    d'études commettent quand même.
    """
    from packages.sentiment.corpus import utilisable_le
    out: list[Evenement] = []
    for ligne in corpus or []:
        sym = str(ligne.get("symbol") or "")
        titre = str(ligne.get("headline") or "").strip()
        bars = data.get(sym)
        jour = utilisable_le(ligne)
        if not bars or not titre or not jour:
            continue
        r = _rendement_futur(bars, jour, hold, entry_lag)
        if r is None:
            continue
        out.append(Evenement(symbole=sym, jour=jour, titre=titre, rendement=r))
    return out


def _rendement_futur(bars, jour: str, hold: int, entry_lag: int) -> float | None:
    dates = [str(b.ts.date() if hasattr(b.ts, "date") else b.ts) for b in bars]
    closes = [float(b.close) for b in bars]
    i = next((k for k, d in enumerate(dates) if d >= jour), None)
    if i is None:
        return None
    entree, sortie = i + entry_lag, i + entry_lag + hold
    if sortie >= len(closes) or closes[entree] <= 0:
        return None
    return closes[sortie] / closes[entree] - 1.0


@dataclass
class Mesure:
    """Ce qu'un scoreur produit sur un jeu d'événements donné."""

    nom: str
    n: int
    ic: float
    sharpe: float
    dsr: float
    rendement_moyen: float
    part_notee: float                     # part des événements auxquels il attribue un avis
    p_placebo: float | None = None
    incidents: list[str] = field(default_factory=list)

    def en_dict(self) -> dict:
        return {**self.__dict__}


def _degenere(x: np.ndarray) -> bool:
    """La série porte-t-elle une dispersion RÉELLE ?

    `x.std() == 0` est un test FAUX en virgule flottante : soixante fois `0.3` ont une
    moyenne de 0.30000000000000004, donc des écarts de 5e-17 et un écart-type non nul. Les
    rangs de ce bruit sont alors arbitraires, et l'IC qui en sort — mesuré ici à 0,21 pour
    un scoreur strictement constant — est une pure illusion.

    C'est le piège déjà rencontré sur `channel_break` (CLAUDE.md) : un canal plat dérive
    sous le niveau réel par erreur flottante et fabrique des cassures. Même remède, une
    tolérance RELATIVE — plus un test exact sur le nombre de valeurs distinctes, qui tranche
    sans arithmétique le cas le plus fréquent.
    """
    if len(np.unique(x)) < 2:
        return True
    return float(x.std()) <= 1e-12 * max(1.0, abs(float(x.mean())))


def _ic(scores: np.ndarray, rendements: np.ndarray) -> float:
    """Corrélation de RANG. Un IC de Pearson serait dominé par quelques valeurs extrêmes,
    et un titre de presse produit exactement ce genre de valeurs."""
    if len(scores) < 3 or _degenere(scores) or _degenere(rendements):
        return 0.0
    ra = scores.argsort().argsort().astype(float)
    rb = rendements.argsort().argsort().astype(float)
    c = float(np.corrcoef(ra, rb)[0, 1])
    return c if math.isfinite(c) else 0.0


def evaluer(nom: str, evenements: list[Evenement], scores: list[float], hold: int = 5,
            n_essais: int = 1, n_effectif: int | None = None) -> Mesure:
    """IC, Sharpe et DSR d'un scoreur. `n_essais` porte la correction de tests multiples.

    `n_essais` doit compter TOUTES les variantes essayées — scoreurs, invites, horizons.
    Le laisser à 1 quand on en a comparé six fait passer pour significatif le meilleur de
    six tirages, ce qui est la définition même du surapprentissage par sélection.

    `n_effectif` EST LE NOMBRE D'OBSERVATIONS INDÉPENDANTES, et il n'est presque jamais
    `len(scores)`. Deux dépendances le réduisent, et elles se cumulent : des rendements
    forward à `hold` barres calculés à chaque barre se RECOUVRENT (chacun partage
    hold−1 barres avec le suivant), et des titres notés le même jour bougent ENSEMBLE.
    Le DSR divise par √n : passer le nombre brut fait croire à une précision qu'on n'a
    pas. Mesuré sur des rendements i.i.d. SANS aucun signal, un scoreur TIRÉ AU HASARD
    allumé 40 % du temps obtient DSR = 1,000 à n = 499 585 — le garde-fou ne garde plus
    rien. Par défaut `len(scores)`, pour ne rien changer aux appelants qui notent un
    événement par titre et par jour.
    """
    s = np.asarray(scores, dtype=float)
    r = np.asarray([e.rendement for e in evenements], dtype=float)
    avis = s != 0.0
    if len(r) < MIN_EVENEMENTS:
        return Mesure(nom, len(r), 0.0, 0.0, 0.0, 0.0, 0.0,
                      incidents=[f"{len(r)} événements < {MIN_EVENEMENTS} — rien à conclure"])
    strategie = np.where(s > 0, 1.0, np.where(s < 0, -1.0, 0.0)) * r
    ecart = float(strategie.std())
    par_an = 252.0 / max(1, hold)
    sr = float(strategie.mean() / ecart) if ecart > 0 else 0.0
    return Mesure(
        nom=nom, n=int(len(r)), ic=round(_ic(s, r), 4),
        sharpe=round(sr * math.sqrt(par_an), 3),
        dsr=round(float(deflated_sharpe_ratio(
            sr, max(2, int(n_effectif or len(strategie))), n_trials=n_essais)), 3),
        rendement_moyen=round(float(strategie.mean()), 5),
        part_notee=round(float(avis.mean()), 3),
        incidents=[] if avis.mean() > 0.2 else
        [f"{avis.mean():.0%} d'avis seulement — le scoreur se tait sur la plupart des titres"],
    )


def placebo(evenements: list[Evenement], scores: list[float], tirages: int = PLACEBO_TIRAGES,
            graine: int = 7) -> float:
    """p-valeur empirique : quelle part des IC obtenus AU HASARD dépasse le nôtre ?

    On mélange les scores, pas les rendements : cela casse le lien tout en conservant les
    deux distributions marginales, donc l'asymétrie des rendements et la forme des scores
    restent celles des vraies données. Mélanger les rendements donnerait la même p-valeur
    en théorie, mais détruirait l'autocorrélation entre événements voisins d'un même titre.
    """
    s = np.asarray(scores, dtype=float)
    r = np.asarray([e.rendement for e in evenements], dtype=float)
    if len(r) < MIN_EVENEMENTS:
        return 1.0
    reel = abs(_ic(s, r))
    rng = np.random.default_rng(graine)
    melange = s.copy()
    depasse = 0
    for _ in range(max(1, tirages)):
        rng.shuffle(melange)
        depasse += int(abs(_ic(melange, r)) >= reel)
    # +1 au numérateur ET au dénominateur : une p-valeur de 0 exacte n'existe pas avec un
    # nombre fini de tirages, et l'écrire laisserait croire à une certitude.
    #
    # ARRONDI VERS LE HAUT, et pour DEUX raisons qui vont dans le même sens. D'abord un
    # arrondi au plus proche peut passer sous le plancher 1/(n+1) — mesuré à 500 tirages :
    # round(1/501, 6) = 0,001996 < 0,00199601 — et une garantie que l'arrondi défait est
    # pire que pas de garantie. Ensuite, arrondir une p-valeur VERS LE BAS fait paraître un
    # résultat plus significatif qu'il ne l'est : c'est la seule direction dans laquelle
    # une erreur d'arrondi peut coûter une fausse découverte.
    p = (depasse + 1) / (tirages + 1)
    return math.ceil(p * 1_000_000) / 1_000_000


def comparer(evenements: list[Evenement], scores_par_scoreur: dict[str, list[float]],
             hold: int = 5, tirages: int = PLACEBO_TIRAGES,
             n_effectif: int | None = None) -> dict:
    """Compare des scoreurs sur les MÊMES événements, avec correction de tests multiples.

    `n_effectif` est transmis tel quel au DSR : cf. `evaluer`. Il est RAPPORTÉ dans le
    rapport, pour qu'un lecteur voie sur combien d'observations indépendantes le
    garde-fou a réellement statué.
    """
    n_essais = max(1, len(scores_par_scoreur))
    mesures: dict[str, Mesure] = {}
    for nom, sc in scores_par_scoreur.items():
        if len(sc) != len(evenements):
            raise ValueError(f"{nom} : {len(sc)} scores pour {len(evenements)} événements — "
                             "les scoreurs DOIVENT noter exactement le même échantillon")
        m = evaluer(nom, evenements, sc, hold=hold, n_essais=n_essais,
                    n_effectif=n_effectif)
        m.p_placebo = placebo(evenements, sc, tirages)
        mesures[nom] = m
    return {"n_evenements": len(evenements), "n_essais": n_essais,
            "n_effectif": int(n_effectif or len(evenements)),
            "mesures": {k: v.en_dict() for k, v in mesures.items()},
            "ecarts": _ecarts(evenements, scores_par_scoreur, hold)}


def _ecarts(evenements: list[Evenement], scores: dict[str, list[float]],
            hold: int) -> list[dict]:
    """Écarts APPARIÉS entre scoreurs : même événement, deux avis, une différence.

    Un test apparié est bien plus puissant qu'une comparaison de deux moyennes
    indépendantes, parce qu'il élimine la variance commune — celle du marché ce jour-là,
    qui affecte les deux scoreurs identiquement et n'apprend rien sur l'un contre l'autre.
    """
    noms = sorted(scores)
    r = np.asarray([e.rendement for e in evenements], dtype=float)
    out: list[dict] = []
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            sa = np.where(np.asarray(scores[a]) > 0, 1.0,
                          np.where(np.asarray(scores[a]) < 0, -1.0, 0.0)) * r
            sb = np.where(np.asarray(scores[b]) > 0, 1.0,
                          np.where(np.asarray(scores[b]) < 0, -1.0, 0.0)) * r
            d = sa - sb
            ec = float(d.std())
            t = float(d.mean() / (ec / math.sqrt(len(d)))) if ec > 0 and len(d) > 1 else 0.0
            # Le nom porte le SENS. Les paires sont ordonnées alphabétiquement — un choix
            # déterministe mais arbitraire — donc « ecart_moyen » seul invite à l'erreur de
            # signe la plus banale : lire « oracle bat miroir » sur un chiffre qui dit
            # l'inverse. Le nom l'empêche.
            out.append({"a": a, "b": b,
                        "ecart_moyen_a_moins_b": round(float(d.mean()), 5),
                        "t_apparie_a_moins_b": round(t if math.isfinite(t) else 0.0, 3),
                        "hold": hold})
    return out


def verdict(rapport: dict, seuil_p: float = 0.05, seuil_dsr: float = 0.90,
            seuil_ic: float = 0.03) -> dict:
    """Le poids du NLP : validé, ou ZÉRO. Conservateur par défaut, et il DIT pourquoi.

    Les trois conditions sont CONJOINTES. Un IC élevé avec un placebo non concluant est un
    tirage chanceux ; un DSR élevé avec un IC nul est un artefact de la distribution des
    rendements, pas un signal.
    """
    lignes: list[dict] = []
    for nom, m in (rapport.get("mesures") or {}).items():
        motifs = []
        if m["n"] < MIN_EVENEMENTS:
            motifs.append(f"{m['n']} événements — échantillon insuffisant")
        if (m.get("p_placebo") or 1.0) > seuil_p:
            motifs.append(f"placebo p={m.get('p_placebo')} > {seuil_p}")
        if m["dsr"] < seuil_dsr:
            motifs.append(f"DSR {m['dsr']} < {seuil_dsr}")
        if abs(m["ic"]) < seuil_ic:
            motifs.append(f"|IC| {abs(m['ic']):.4f} < {seuil_ic}")
        lignes.append({"scoreur": nom, "retenu": not motifs,
                       "poids": 1.0 if not motifs else 0.0,
                       "motif": " · ".join(motifs) or "les trois portes passées"})
    return {"n_evenements": rapport.get("n_evenements", 0),
            "n_essais": rapport.get("n_essais", 1), "scoreurs": lignes,
            "retenus": [x["scoreur"] for x in lignes if x["retenu"]]}
