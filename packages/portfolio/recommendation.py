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


def _lignes(symboles: list[str], meta: dict[str, dict], poids: dict) -> list[dict]:
    # `or s` et non `.get(..., s)` : le screener publie parfois une chaîne VIDE plutôt que
    # d'omettre la clé, et le repli par défaut ne se déclenchait alors pas — colonne « Nom »
    # blanche sur des lignes pourtant valides (constaté le 07/09 sur BK, EA, NDX).
    return [{"symbol": s, "name": meta.get(s, {}).get("name") or s,
             "sector": meta.get(s, {}).get("sector", ""),
             "asset_class": meta.get(s, {}).get("asset_class", ""),
             "score": meta.get(s, {}).get("score"),
             "reason": meta.get(s, {}).get("reason", ""),
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


def scenario_conviction(covariance: np.ndarray, scores: list[float],
                        ic: dict | None) -> tuple[list | None, str]:
    """Profil orienté RENDEMENT — et le seul que la mesure a le droit d'interdire.

    Black-Litterman : prior = ERC (pas de vue), vues issues des scores. L'amplitude des
    vues n'est pas un réglage esthétique : elle vaut IC × σ × z, la formule de Grinold.
    Un IC de 0,02 produit donc des vues quinze fois plus faibles qu'un IC de 0,30, et le
    postérieur retombe naturellement sur le prior. C'est le mécanisme qui empêche une
    conviction non mesurée de déplacer un euro.

    Sans mesure, ou avec une mesure non robuste, le scénario n'existe PAS. On ne le
    dégrade pas silencieusement en HRP sous un nom prometteur : on dit pourquoi il manque.
    """
    if not ic or not ic.get("available"):
        return None, ("IC du score jamais mesuré. Lancer `make ic-screening` : sans lui, "
                      "aucun rendement attendu n'est calibré et ce profil n'a pas de sens.")
    if not ic.get("robuste"):
        return None, (f"IC mesuré ({ic.get('ic_moyen', 0):+.4f}) mais NON robuste : "
                      f"{ic.get('ic_premiere_moitie', 0):+.4f} sur la première moitié contre "
                      f"{ic.get('ic_seconde_moitie', 0):+.4f} sur la seconde. Le signal ne "
                      "survit pas à sa période d'origine — on ne l'utilise pas.")
    try:
        from packages.portfolio.black_litterman import (
            black_litterman,
            views_from_scores,
        )
        from packages.portfolio.optimize import equal_risk_contribution
        vol = float(np.sqrt(np.mean(np.diag(covariance))))       # vol annuelle typique
        echelle = abs(float(ic["ic_moyen"])) * vol               # Grinold : α = IC × σ × z
        matrice, vues = views_from_scores(list(scores), scale=echelle)
        return black_litterman(covariance, equal_risk_contribution(covariance),
                               matrice, vues)["weights"], ""
    except Exception as erreur:  # noqa: BLE001
        return None, f"Black-Litterman indisponible : {erreur}"


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
                profil: dict | None) -> dict:
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
    exposition = 1.0 if vol <= 0 else min(1.0, cible / vol)
    sortie |= {"poids": [w * exposition for w in plafonnes], "exposition": exposition,
               "cash": 1.0 - exposition, "budget_perte": budget, "vol_cible": cible,
               "vol_apres_exposition": vol * exposition}
    return sortie


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
                profil: dict | None = None) -> dict:
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
    series, aliases, manquants = charger_series(list(meta), years)
    if len(series) < MIN_ACTIFS:
        return _indisponible("historiques insuffisants pour les candidats du jour.",
                             missing=manquants, selected=list(meta))
    retenus, ecartes = elaguer(series, scores)
    symboles, covariance, dates = covariance_annuelle(retenus)
    if covariance.size == 0 or len(dates) <= MIN_OBSERVATIONS:
        return _indisponible("calendrier commun insuffisant entre les candidats retenus.",
                             missing=manquants, dropped=ecartes)
    poids = scenarios_risque(covariance)
    ic = charger_ic()
    conviction, motif_conviction = scenario_conviction(
        covariance, [scores.get(sym, 0.0) for sym in symboles], ic)
    if conviction is not None:
        poids["conviction"] = conviction
    # Le profil déclaré BORNE le résultat au lieu de le commenter. Sans profil, la contrainte
    # se réduit au plafond de ligne : le comportement d'avant, inchangé.
    contraintes = {nom: contraindre(vecteur, covariance, plafond, profil)
                   for nom, vecteur in poids.items()}
    poids = {nom: c["poids"] for nom, c in contraintes.items()}
    return {
        "available": True, "symbols": symboles, "aliases": aliases,
        "rows": _lignes(symboles, meta, poids),
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
        },
        # La mesure, telle quelle. Si elle vaut UNCALIBRATED, la carte l'affiche —
        # l'absence de mesure est une information, pas un blanc à combler.
        "ic": ic or {"available": False, "status": "JAMAIS MESURÉ",
                     "reason": "Lancer `make ic-screening`."},
        "conviction_reason": motif_conviction,
        "contraintes": contraintes,
        "profil_applique": bool(profil),
        "plafond_ligne": plafond,
        # L'étiquette SUIT la mesure. La figer sur « non validé » alors qu'une mesure
        # existe serait aussi faux que l'inverse : on publie ce qui a été constaté.
        "caveat": _avertissement(ic),
    }
