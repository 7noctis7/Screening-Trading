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
    return [{"symbol": s, "name": meta.get(s, {}).get("name", s),
             "sector": meta.get(s, {}).get("sector", ""),
             "asset_class": meta.get(s, {}).get("asset_class", ""),
             "score": meta.get(s, {}).get("score"),
             "reason": meta.get(s, {}).get("reason", ""),
             **{profil: round(float(vecteur[i]), 6) for profil, vecteur in poids.items()}}
            for i, s in enumerate(symboles)]


def _indisponible(raison: str, **extra) -> dict:
    return {"available": False, "reason": raison, **extra}


def recommander(screen: dict, n: int = 15, years: int = 5) -> dict:
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
        # Étiquette obligatoire : les poids sont mesurés, la SÉLECTION ne l'est pas.
        "caveat": ("Les poids répartissent le risque mesuré ; la sélection repose sur un score "
                   "composite dont le pouvoir prédictif n'est pas validé hors échantillon. "
                   "Exploratoire — aucun ordre."),
    }
