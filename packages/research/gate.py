"""Gate de promotion — LE Checker unique : un candidat est-il promouvable ?

Avant, la décision « promu/rejeté » était dupliquée en inline dans chaque script (seuils
parfois différents). On la centralise ici → une seule définition, testée, partagée par
tous les backtests/event-studies. C'est le pilier Maker-Checker rendu structurel :
le Maker génère, CE module tranche, selon des critères déterministes (pas un 2e LLM).

Critères (un contrôle à None est IGNORÉ — pas encore mesuré, ne bloque pas) :
- placebo p-value < `placebo_max` (l'effet bat le hasard)
- DSR > `dsr_min`            (Sharpe déflaté du multiple-testing, López de Prado)
- PBO < `pbo_max`            (pas de surajustement du choix de config, CSCV)
- edge net > 0               (rentable APRÈS coûts)
"""

from __future__ import annotations

# Seuils par défaut = SOURCE UNIQUE DE VÉRITÉ (étaient en dur, dispersés).
DSR_MIN = 0.5
PBO_MAX = 0.5
PLACEBO_MAX = 0.05


def promotion_verdict(*, dsr: float | None = None, pbo: float | None = None,
                      edge: float | None = None, placebo_p: float | None = None,
                      dsr_min: float = DSR_MIN, pbo_max: float = PBO_MAX,
                      placebo_max: float = PLACEBO_MAX) -> dict:
    """Verdict booléen + justification. `promoted` exige AU MOINS un contrôle mesuré et
    que TOUS les contrôles mesurés passent. Renvoie {promoted, checks, reasons}."""
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    if placebo_p is not None:
        checks["placebo"] = placebo_p < placebo_max
        if not checks["placebo"]:
            reasons.append(f"placebo p={placebo_p} ≥ {placebo_max}")
    if dsr is not None:
        checks["dsr"] = dsr > dsr_min
        if not checks["dsr"]:
            reasons.append(f"DSR {dsr} ≤ {dsr_min}")
    if pbo is not None:
        checks["pbo"] = pbo < pbo_max
        if not checks["pbo"]:
            reasons.append(f"PBO {pbo} ≥ {pbo_max}")
    if edge is not None:
        checks["edge"] = edge > 0
        if not checks["edge"]:
            reasons.append(f"edge net {edge} ≤ 0")
    promoted = bool(checks) and all(checks.values())
    return {"promoted": promoted, "checks": checks, "reasons": reasons}


def verdict_hors_echantillon(*, sharpe_oos: float, n_obs_oos: int,
                             pbo: float | None = None, edge: float | None = None,
                             placebo_p: float | None = None,
                             skew: float = 0.0, kurtosis: float = 3.0,
                             ecart_type_sharpe: float | None = None,
                             chemin_ledger=None, **seuils) -> dict:
    """`promotion_verdict` dont le DSR est CALCULÉ, jamais fourni.

    LE TROU QUE ÇA FERME. `promotion_verdict` reçoit `dsr` comme un nombre : c'est
    l'appelant qui l'a calculé, donc c'est lui qui a choisi le nombre d'essais dont il
    déflate. Or `protocole_oos` le dit sans détour — « le DSR n'a de sens que si le
    nombre d'essais qu'il déflate est COMPTÉ, pas choisi ». Un appelant optimiste qui
    déclare un seul essai obtient un seuil bas et une porte grande ouverte.

    Ici `n_essais` vient du ledger et de nulle part ailleurs. Il n'y a volontairement
    AUCUN paramètre pour le fournir : un garde-fou contournable par un argument nommé
    n'est pas un garde-fou.

    `promotion_verdict` reste inchangée — trois appelants s'en servent et rien n'oblige
    un backtest déjà écrit à migrer. Le verdict renvoyé porte en plus `dsr_calcule`,
    `n_essais` et `deployable` (la porte à 95 % de `protocole_oos`, plus stricte que le
    `dsr_min` de promotion : la première dit « déployable », la seconde
    « promouvable »).
    """
    from packages.research.protocole_oos import essais_du_ledger, porte_de_deploiement
    n_essais = essais_du_ledger(chemin_ledger)
    porte = porte_de_deploiement(sharpe_oos, n_obs_oos, n_essais,
                                 ecart_type_sharpe=ecart_type_sharpe,
                                 skew=skew, kurtosis=kurtosis)
    verdict = promotion_verdict(dsr=porte["dsr"], pbo=pbo, edge=edge,
                                placebo_p=placebo_p, **seuils)
    verdict["dsr_calcule"] = porte["dsr"]
    verdict["n_essais"] = n_essais
    verdict["deployable"] = porte["deployable"]
    if porte["motif"]:
        verdict["reasons"] = [*verdict["reasons"], porte["motif"]]
    return verdict
