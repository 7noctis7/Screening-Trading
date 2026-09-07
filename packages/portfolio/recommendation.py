"""Recommandation d'univers : QUE détenir, et pas seulement comment repondérer l'existant.

Différence de nature avec `user_analysis.analyze`, qui répond « comment mieux répartir ce
que j'ai ». Ici la sélection vient du screening quotidien (filtres durs YAML puis score
composite z-score sur l'univers investable), et les poids des trois profils viennent des
mêmes moteurs de risque que l'étape 4. Aucune vue, aucun rendement attendu : « idéal »
signifie « bien réparti sur une sélection », jamais « le plus rentable ».

MISE EN GARDE PUBLIÉE AVEC LE RÉSULTAT : le pouvoir prédictif du score de sélection n'est
pas validé hors échantillon dans ce dépôt. La carte le dit ; elle ne le suppose pas.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from packages.portfolio.conviction import scenario_conviction
from packages.portfolio.indicateurs import (
    bornes_52_semaines,
    correlation_moyenne,
    performance_realisee,
    positions_effectives,
    ratio_diversification,
)
from packages.portfolio.filtre_resultats import FENETRE_DEFAUT, ecarter
from packages.portfolio.user_analysis import (
    ALIGNEMENT,
    MIN_OBSERVATIONS,
    charger_series,
    covariance_annuelle,
    scenarios_risque,
)

# T/N minimal exigé pour une covariance empirique. En deçà, les valeurs propres sont
# dominées par l'erreur d'estimation (Marchenko-Pastur : le bruit occupe une bande de
# largeur ~(1+√(N/T))²) et un min-variance nourri de cette matrice optimise du bruit —
# il concentre sur les actifs dont la variance est SOUS-ESTIMÉE par accident.
RATIO_T_SUR_N_MIN = 30.0
MIN_ACTIFS = 3


def _debut(serie: dict[str, float]) -> str:
    return min(serie) if serie else "9999-99-99"


def _fenetre(series: dict[str, dict[str, float]]) -> int:
    if not series:
        return 0
    return len(set.intersection(*(set(valeurs) for valeurs in series.values())))


PERIME_JOURS = 10        # même seuil que le nettoyage d'univers de `build_snapshot`


def ecarter_perimes(series: dict[str, dict[str, float]],
                    seuil: int = PERIME_JOURS) -> tuple[dict, list[dict]]:
    """Retire les séries ARRÊTÉES avant tout calcul. Défense en profondeur, et elle a servi.

    Le 07/09, `BK` (dernière barre au 18 juin), `EA` (10 août) et `EQR` (21 août) occupaient
    57 % de la recommandation. Deux conséquences distinctes, la seconde plus vicieuse :

    1. L'alignement se fait par INTERSECTION des dates. Un seul actif arrêté au 18 juin
       tronque donc la fenêtre commune de TOUT le portefeuille au 18 juin — la carte
       affichait « historique commun jusqu'au 2026-06-17 » sans que personne n'y voie un
       avertissement.
    2. Une série figée n'a plus de variance récente. Un min-variance la prend pour l'actif
       le moins risqué de l'univers et la surpondère mécaniquement. La donnée morte n'est
       pas seulement inutile : elle ATTIRE le capital.

    Seuil RELATIF à la barre la plus fraîche des candidats — un seuil absolu écarterait tout
    l'univers un lundi férié ou après une semaine sans ingestion.
    """
    from datetime import date, timedelta
    fins = {symbole: max(valeurs) for symbole, valeurs in series.items() if valeurs}
    if not fins:
        return series, []
    fraiche = max(fins.values())
    try:
        limite = (date.fromisoformat(fraiche[:10]) - timedelta(days=seuil)).isoformat()
    except ValueError:                       # dates non ISO : on ne tranche pas au hasard
        return series, []
    perimes = [{"symbol": s, "last": fins[s],
                "reason": f"dernière barre {fins[s]} < {limite} — série arrêtée"}
               for s in sorted(fins) if fins[s][:10] < limite]
    retires = {ligne["symbol"] for ligne in perimes}
    return {s: v for s, v in series.items() if s not in retires}, perimes


def elaguer(series: dict[str, dict[str, float]], scores: dict[str, float],
            ratio_min: float = RATIO_T_SUR_N_MIN) -> tuple[dict, list[dict]]:
    """Retire les candidats qui rendent la covariance non estimable, et dit lesquels.

    L'intersection des calendriers est bornée par l'actif dont l'historique COMMENCE LE
    PLUS TARD : une introduction récente au milieu de quinze candidats peut réduire la
    fenêtre commune à quelques semaines. Retirer ce candidat augmente T et diminue N —
    les deux dans le bon sens. On itère jusqu'à T ≥ ratio·N, en départageant les débuts
    identiques par le score le plus faible.

    Ce qui est retiré est RENDU, avec sa date de début : un actif écarté doit être
    visible, jamais absorbé en silence.
    """
    retenus = dict(series)
    ecartes: list[dict] = []
    while len(retenus) > MIN_ACTIFS:
        t = _fenetre(retenus)
        if t >= ratio_min * len(retenus) and t > MIN_OBSERVATIONS:
            break
        tardif = max(retenus, key=lambda s: (_debut(retenus[s]), -scores.get(s, 0.0)))
        ecartes.append({"symbol": tardif, "start": _debut(retenus[tardif]),
                        "reason": "historique trop court pour la fenêtre commune"})
        del retenus[tardif]
    return retenus, ecartes


def lien_source(symbole: str) -> str:
    """Fiche de l'INSTRUMENT chez le fournisseur qui a produit nos prix.

    Pourquoi pas le site « relations investisseurs » de la société : il faudrait le déduire
    d'un nom, et un nom mal apparié enverrait vers UNE AUTRE ENTREPRISE — précisément
    l'erreur qu'on cherche à éviter. Le lien pointe donc vers la fiche du fournisseur,
    indexée par le symbole EXACT que nous avons utilisé. Si notre identifiant est faux, la
    page ouverte est fausse de la même façon, donc visiblement fausse. Un lien qui échoue
    de manière détectable vaut mieux qu'un lien plausible et faux.
    """
    return f"https://finance.yahoo.com/quote/{symbole}"


def _lignes(symboles: list[str], meta: dict[str, dict], poids: dict,
            alias: dict[str, str] | None = None,
            series: dict[str, dict[str, float]] | None = None) -> list[dict]:
    """Chaque ligne porte de quoi IDENTIFIER l'instrument, pas seulement le pondérer.

    `name` reste None quand il est absent, au lieu de retomber sur le ticker. Afficher
    « BK / BK » a l'apparence d'une information et n'en est pas une : le lecteur croit
    avoir vérifié. Un nom manquant doit se voir comme manquant, et le lien prend le relais.
    """
    return [{"symbol": s, "name": (meta.get(s, {}).get("name") or "").strip() or None,
             "sector": meta.get(s, {}).get("sector") or None,
             "asset_class": meta.get(s, {}).get("asset_class") or None,
             "venue": meta.get(s, {}).get("venue") or None,
             "currency": meta.get(s, {}).get("currency") or None,
             # Le symbole RÉELLEMENT coté : `ETH` a pu être valorisé via `ETH-USD`. C'est le
             # désambiguïsateur le plus utile — il dit quelle série a servi au calcul.
             "alias": (alias or {}).get(s) or s,
             "lien": lien_source((alias or {}).get(s) or s),
             "score": meta.get(s, {}).get("score"),
             "reason": meta.get(s, {}).get("reason", ""),
             # Bornes 52 semaines : un constat, pas un objectif de cours. La distance au
             # plus haut se lit sans contexte — −40 % exige +67 % pour revenir.
             **bornes_52_semaines((series or {}).get(s, {})),
             **{profil: round(float(vecteur[i]), 6) for profil, vecteur in poids.items()}}
            for i, s in enumerate(symboles)]


CHEMIN_IC = Path(__file__).resolve().parents[2] / "out" / "ic_screening.json"


def charger_ic(chemin: Path = CHEMIN_IC) -> dict | None:
    """Mesure d'IC produite par `make ic-screening`, ou None si jamais mesurée.

    On LIT un fichier daté au lieu de recalculer : la mesure walk-forward réexécute le
    moteur à chaque date de la grille, ce n'est pas une opération de requête HTTP.
    """
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — jamais mesuré, illisible : on le dit par None
        return None


def _plafonner(poids: list[float], plafond: float) -> tuple[list[float], int, float]:
    """Projection sur le simplex sous plafond : (poids, nb de plafonds activés, effet moyen).

    Les poids excédentaires sont fixés au plafond et le reliquat redistribué au prorata,
    par itérations — un simple `min(w, cap)` suivi d'une renormalisation ferait ressortir
    au-dessus du plafond ce qu'on venait d'y ramener.
    """
    base = [max(0.0, float(v)) for v in poids]
    n = len(base)
    if n * plafond < 1 - 1e-9:                      # contrainte infaisable, on ne bricole pas
        return base, 0, 0.0
    sortie, actifs, reste = [0.0] * n, set(range(n)), 1.0
    while actifs:
        total = sum(base[i] for i in actifs)
        equi = reste / len(actifs)
        depasse = [i for i in actifs
                   if (reste * base[i] / total if total > 0 else equi) > plafond + 1e-9]
        if not depasse:
            for i in actifs:
                sortie[i] = reste * base[i] / total if total > 0 else equi
            break
        for i in depasse:
            sortie[i], reste = plafond, reste - plafond
            actifs.discard(i)
    actives = sum(1 for v in base if v > plafond + 1e-9)
    effet = (sum(abs(sortie[i] - base[i]) for i in range(n)) / n) if actives else 0.0
    return sortie, actives, effet


def contraindre(poids: list[float], covariance: np.ndarray, plafond: float,
                profil: dict | None, moderation: float = 1.0) -> dict:
    """Plafond de ligne PUIS exposition dictée par le budget de perte du profil.

    L'ORDRE compte et n'est pas arbitraire. Le plafond est une contrainte RELATIVE (aucune
    ligne au-dessus de x %) : il redistribue à somme constante. L'exposition est ABSOLUE
    (le portefeuille entier ne doit pas pouvoir baisser de plus que le budget déclaré) :
    elle se lit sur la volatilité des poids DÉFINITIFS. Faire l'inverse mesurerait la
    volatilité d'une allocation qui ne sera pas détenue.

    `maxDD ≈ 2.5 × vol` (`vol_target_from_drawdown`) : la même conversion que le
    dimensionnement de production, pas une seconde formule pour le même objet.
    """
    plafonnes, actives, effet = _plafonner(poids, plafond)
    vecteur = np.asarray(plafonnes, dtype=float)
    vol = float(np.sqrt(max(0.0, vecteur @ covariance @ vecteur)))
    sortie = {"poids": plafonnes, "vol_annuelle": vol, "exposition": 1.0, "cash": 0.0,
              "plafonds_actives": actives, "effet_moyen_plafond": effet,
              "budget_perte": None, "vol_cible": None}
    if not profil:
        return sortie
    from packages.portfolio.construction import vol_target_from_drawdown
    from packages.profile.investor import Profil, budget_perte
    budget = budget_perte(Profil(**profil))
    cible = vol_target_from_drawdown(budget)
    # La modération de régime s'applique APRÈS le budget de perte : elle ne peut que
    # resserrer une exposition déjà autorisée, jamais l'élargir (facteur ≤ 1).
    exposition = (1.0 if vol <= 0 else min(1.0, cible / vol)) * max(0.0, min(1.0, moderation))
    sortie |= {"poids": [w * exposition for w in plafonnes], "exposition": exposition,
               "cash": 1.0 - exposition, "budget_perte": budget, "vol_cible": cible,
               "vol_apres_exposition": vol * exposition}
    return sortie


def moderation_regime(regime: dict | None, ic: dict | None) -> dict:
    """Le régime macro module l'EXPOSITION, jamais le choix des titres — et seulement vers le bas.

    DEUX DÉCISIONS, toutes deux discutables, donc énoncées.

    *Pourquoi l'exposition et pas les poids.* Incliner les poids entre titres suppose de
    savoir QUI profitera du régime : c'est une prévision transversale, et rien ici ne la
    valide. Réduire l'exposition ne suppose que de savoir que le risque global est moins
    bien payé — une affirmation plus faible, donc plus soutenable.

    *Pourquoi seulement vers le bas.* La perte et le gain ne sont pas symétriques : se
    tromper en étant prudent coûte un rendement manqué, se tromper en étant agressif peut
    coûter la capacité à rester investi. Un régime favorable n'autorise donc AUCUNE
    augmentation d'exposition au-delà de ce que le profil permet déjà.

    L'amplitude suit `force_preuve` — la même règle que les inclinaisons de la page profil :
    proportionnelle à la force de la PREUVE, pas à celle du signal. Sans mesure, la force
    vaut 0 et la modération vaut exactement 1,0 : le câblage est actif et n'a aucun effet
    tant que rien n'est démontré. C'est voulu.
    """
    from packages.profile.tilts import AMPLITUDE_MAX, force_preuve, vues_depuis_regime
    cycle = (regime or {}).get("cycle")
    risk_mode = (regime or {}).get("risk_mode")
    vues = vues_depuis_regime(cycle, risk_mode)
    # La preuve disponible est celle du score : c'est la seule mesurée dans ce dépôt. Le
    # régime lui-même n'a pas de t-stat publié — l'absence se dit, elle ne se remplace pas.
    preuve = force_preuve((ic or {}).get("t_stat"), (ic or {}).get("n_dates"))
    penchant = float(vues.get("actions_dev", 0.0))
    if penchant >= 0 or preuve["force"] <= 0:
        return {"facteur": 1.0, "cycle": cycle, "risk_mode": risk_mode,
                "force_preuve": preuve["force"], "motif": preuve["motif"] if penchant < 0
                else "régime non défensif — aucune réduction d'exposition",
                "reduction": 0.0}
    reduction = AMPLITUDE_MAX * preuve["force"] * min(1.0, abs(penchant))
    return {"facteur": 1.0 - reduction, "cycle": cycle, "risk_mode": risk_mode,
            "force_preuve": preuve["force"], "reduction": reduction,
            "motif": f"régime défensif ({cycle or 'n/d'} · {risk_mode or 'n/d'}), preuve "
                     f"{preuve['force']:.2f} → exposition réduite de {reduction:.1%}"}


def chemin_de_moindre_effort(covariance: np.ndarray, symboles: list[str],
                             actuel: dict[str, float], cible: dict[str, float]) -> list[dict]:
    """Ordonne les mouvements par variance évitée PAR POINT DE TURNOVER.

    « Voici la cible » n'est pas actionnable quand le turnover est de 100 % : le coût est
    certain et immédiat, le bénéfice diffus. La question utile est « quels mouvements
    achètent le plus de réduction de risque par euro échangé », et elle a une réponse
    exacte, pas une opinion.

    Glouton assumé : à chaque étape on retient le mouvement de meilleur rapport, on
    l'applique, on recalcule. Ce n'est pas l'optimum global du sous-ensemble — le problème
    est combinatoire — mais l'ordre produit est celui qu'un opérateur suivrait, et chaque
    ligne publie la variance ATTEINTE, vérifiable.

    La trésorerie est le résidu implicite (1 − Σw) : elle ne contribue pas à la variance,
    donc un mouvement qui sort du marché apparaît naturellement comme réducteur.
    """
    def variance(poids: dict[str, float]) -> float:
        vecteur = np.asarray([poids.get(s, 0.0) for s in symboles], dtype=float)
        return float(vecteur @ covariance @ vecteur)

    courant = {s: float(actuel.get(s, 0.0)) for s in symboles}
    restants = {s for s in symboles if abs(cible.get(s, 0.0) - courant[s]) > 1e-6}
    depart = variance(courant)
    total = variance({s: float(cible.get(s, 0.0)) for s in symboles})
    etapes, turnover_cumule = [], 0.0
    while restants:
        meilleur, meilleur_gain = None, None
        for symbole in restants:
            essai = dict(courant, **{symbole: float(cible.get(symbole, 0.0))})
            cout = abs(essai[symbole] - courant[symbole])
            gain = (variance(courant) - variance(essai)) / cout if cout > 1e-12 else 0.0
            if meilleur_gain is None or gain > meilleur_gain:
                meilleur, meilleur_gain = symbole, gain
        cout = abs(float(cible.get(meilleur, 0.0)) - courant[meilleur])
        courant[meilleur] = float(cible.get(meilleur, 0.0))
        restants.discard(meilleur)
        turnover_cumule += cout / 2
        atteinte = variance(courant)
        part = ((depart - atteinte) / (depart - total)) if abs(depart - total) > 1e-12 else 1.0
        etapes.append({
            "symbol": meilleur, "de": round(float(actuel.get(meilleur, 0.0)), 6),
            "vers": round(float(cible.get(meilleur, 0.0)), 6),
            "turnover_cumule": round(turnover_cumule, 6),
            "vol_atteinte": round(float(np.sqrt(max(0.0, atteinte))), 6),
            "part_du_gain": round(float(part), 4),
        })
    return etapes


def _avertissement(ic: dict | None) -> str:
    """L'avertissement dit l'état RÉEL de la mesure — jamais une formule figée."""
    base = ("Les poids répartissent le risque mesuré. Aucun de ces profils ne prédit un "
            "rendement, sauf « Conviction » lorsqu'il est disponible. Exploratoire — aucun ordre.")
    if not ic or not ic.get("available"):
        return ("Le pouvoir prédictif du score de sélection n'a JAMAIS été mesuré ici "
                "(`make ic-screening`). " + base)
    signe = "+" if ic.get("ic_moyen", 0) >= 0 else ""
    etat = "robuste hors échantillon" if ic.get("robuste") else "NON robuste hors échantillon"
    return (f"IC du score mesuré à {signe}{ic.get('ic_moyen', 0):.4f} sur "
            f"{ic.get('n_dates')} fenêtres disjointes de {ic.get('horizon')} jours, {etat}. " + base)


def _indisponible(raison: str, **extra) -> dict:
    return {"available": False, "reason": raison, **extra}


def recommander(screen: dict, n: int = 15, years: int = 5, plafond: float = 0.20,
                profil: dict | None = None,
                blackout_resultats: int = FENETRE_DEFAUT,
                regime: dict | None = None, ml_scores: dict | None = None,
                ml_auc: float | None = None, positions: dict | None = None) -> dict:
    """Sélection = top `n` du screening du jour ; poids = min-var / ERC / HRP sur eux.

    `screen` est la section `/api/screen` du snapshot : elle porte déjà les filtres durs
    appliqués, la taille de l'univers investable et le score de chaque candidat. On ne
    refait pas le screening ici — on consomme son résultat, daté, tel quel.
    """
    if not screen.get("available"):
        return _indisponible("screening du jour indisponible : aucune sélection à proposer.")
    rows = list(screen.get("rows") or [])[:max(MIN_ACTIFS, int(n))]
    if len(rows) < MIN_ACTIFS:
        return _indisponible(f"screening trop maigre : {len(rows)} candidat(s), {MIN_ACTIFS} minimum.")
    meta = {r["symbol"]: r for r in rows}
    scores = {r["symbol"]: float(r.get("score") or 0.0) for r in rows}
    # Filtre d'ENTRÉE avant tout calcul : inutile d'estimer une covariance sur des titres
    # qu'on ne prendra pas. Le risque de résultats est daté et binaire — une covariance
    # historique ne le mesure pas, donc aucun optimiseur ne peut le voir.
    candidats, blackout, sans_date = ecarter(list(meta), fenetre=blackout_resultats)
    if len(candidats) < MIN_ACTIFS:
        return _indisponible(
            f"{len(blackout)} candidat(s) écarté(s) pour résultats imminents — il en reste "
            f"{len(candidats)}, {MIN_ACTIFS} minimum. Réessayer après les publications.",
            earnings_blackout=blackout)
    meta = {s: meta[s] for s in candidats}
    # La classe d'actif du screening interdit le repli crypto sur une action : sans elle,
    # `ABC` (action délistée) se ferait valoriser par `ABC-USD`, un jeton.
    series, aliases, manquants = charger_series(
        candidats, years, {s: (meta[s].get("asset_class") or "") for s in candidats})
    if len(series) < MIN_ACTIFS:
        return _indisponible("historiques insuffisants pour les candidats du jour.",
                             missing=manquants, selected=list(meta))
    series, perimes = ecarter_perimes(series)
    if len(series) < MIN_ACTIFS:
        return _indisponible(
            f"{len(perimes)} candidat(s) écarté(s) pour série arrêtée — il en reste "
            f"{len(series)}, {MIN_ACTIFS} minimum.", stale=perimes, missing=manquants)
    retenus, ecartes = elaguer(series, scores)
    symboles, covariance, dates = covariance_annuelle(retenus)
    if covariance.size == 0 or len(dates) <= MIN_OBSERVATIONS:
        return _indisponible("calendrier commun insuffisant entre les candidats retenus.",
                             missing=manquants, dropped=ecartes)
    poids = scenarios_risque(covariance)
    ic = charger_ic()
    conviction, motif_conviction = scenario_conviction(
        covariance, [scores.get(sym, 0.0) for sym in symboles], ic,
        [(ml_scores or {}).get(sym) for sym in symboles], ml_auc)
    if conviction is not None:
        poids["conviction"] = conviction
    # Le profil déclaré BORNE le résultat au lieu de le commenter. Sans profil, la contrainte
    # se réduit au plafond de ligne : le comportement d'avant, inchangé.
    moderation = moderation_regime(regime, ic)
    contraintes = {nom: contraindre(vecteur, covariance, plafond, profil,
                                    moderation["facteur"])
                   for nom, vecteur in poids.items()}
    poids = {nom: c["poids"] for nom, c in contraintes.items()}
    # Ratios de STRUCTURE (ce que la matrice implique aujourd'hui) et performance RÉALISÉE
    # (ce qui s'est produit). Les deux sont des constats ; aucun n'est une prévision.
    for nom, contrainte in contraintes.items():
        vecteur = contrainte["poids"]
        contrainte |= {
            "ratio_diversification": ratio_diversification(vecteur, covariance),
            "positions_effectives": positions_effectives(vecteur),
            "correlation_moyenne": correlation_moyenne(covariance),
            **performance_realisee(retenus, symboles, vecteur),
        }
    return {
        "available": True, "symbols": symboles, "aliases": aliases,
        "rows": _lignes(symboles, meta, poids, aliases, retenus),
        "scenarios": {profil: [round(float(v), 6) for v in vecteur]
                      for profil, vecteur in poids.items()},
        "as_of": dates[-1], "start": dates[0], "n_observations": len(dates) - 1,
        "t_sur_n": round(len(dates) / max(1, len(symboles)), 1),
        "alignment": ALIGNEMENT, "annualization": 252,
        "selection": {
            "source": "screening quotidien (filtres durs YAML puis score composite z-score)",
            "asked": int(n), "kept": len(symboles),
            "universe_size": screen.get("universe_size"),
            "filters": screen.get("filters") or [],
            "missing_history": manquants, "dropped": ecartes,
            # Le blackout est publié même vide : « aucun résultat imminent » est une
            # information, et son absence d'affichage se lirait comme un filtre inactif.
            "earnings_blackout": blackout, "earnings_window": blackout_resultats,
            "earnings_unknown": sans_date,
            # Séries arrêtées : publiées avec leur dernière date. Une donnée morte n'est pas
            # seulement inutile — figée, elle paraît sans risque et attire le capital.
            "stale": perimes, "stale_window": PERIME_JOURS,
        },
        # La mesure, telle quelle. Si elle vaut UNCALIBRATED, la carte l'affiche —
        # l'absence de mesure est une information, pas un blanc à combler.
        "ic": ic or {"available": False, "status": "JAMAIS MESURÉ",
                     "reason": "Lancer `make ic-screening`."},
        "conviction_reason": motif_conviction,
        "contraintes": contraintes,
        # Chemin de moindre effort : sans les positions détenues, la question « quels
        # mouvements achètent le plus de risque évité » n'a pas de point de départ.
        "chemin": {nom: chemin_de_moindre_effort(
                       covariance, symboles, positions or {},
                       dict(zip(symboles, c["poids"])))
                   for nom, c in contraintes.items()} if positions else {},
        "profil_applique": bool(profil),
        "regime": moderation,
        "plafond_ligne": plafond,
        # L'étiquette SUIT la mesure. La figer sur « non validé » alors qu'une mesure
        # existe serait aussi faux que l'inverse : on publie ce qui a été constaté.
        "caveat": _avertissement(ic),
    }
