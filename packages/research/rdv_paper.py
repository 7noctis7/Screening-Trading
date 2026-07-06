"""RDV paper (2026-08-06) — verdict GO/NO-GO MÉCANIQUE : courbe paper réelle vs backtest.

Transforme LA décision du projet (premier euro réel limité OU re-calibrage) en sortie
de machine, selon les critères DÉJÀ écrits au vault (03_TODO « RENDEZ-VOUS ») :
  - pas de dérive de Sharpe > 1 point (paper vs backtest, annualisés) ;
  - MaxDD paper ≤ MaxDD backtest (pas pire que promis) ;
  - track record suffisant : N jours ≥ MinTRL (López de Prado) ET ≥ 20 jours.
Verdict : GO / NO-GO / INSUFFISANT (pas assez de données → on n'invente pas).

Fonctions PURES (listes de floats) — testables hors-ligne ; le chargement des courbes
réelles vit dans `scripts/rdv_paper.py` (Mac, données réelles).
"""

from __future__ import annotations

import math


def _rets(curve: list[float]) -> list[float]:
    return [curve[i] / curve[i - 1] - 1.0 for i in range(1, len(curve))
            if curve[i - 1] > 0]


def _sharpe_ann(rets: list[float]) -> float | None:
    n = len(rets)
    if n < 2:
        return None
    mu = sum(rets) / n
    var = sum((r - mu) ** 2 for r in rets) / (n - 1)
    sd = math.sqrt(var)
    return (mu / sd) * math.sqrt(252) if sd > 0 else None


def _max_dd(curve: list[float]) -> float:
    peak, worst = float("-inf"), 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def _min_trl_days(sharpe_ann: float | None) -> int | None:
    """MinTRL (jours) pour distinguer le Sharpe paper de 0 à 95 % ; None si indisponible."""
    if sharpe_ann is None:
        return None
    try:
        from packages.portfolio.psr import min_track_record_length
        v = min_track_record_length(sharpe_ann / math.sqrt(252), sr_benchmark=0.0)
        return None if v is None else int(math.ceil(v))
    except Exception:  # noqa: BLE001 — MinTRL indisponible ≠ verdict cassé
        return None


def compare(paper: list[float], model: list[float], *, min_days: int = 20,
            max_sharpe_drift: float = 1.0) -> dict:
    """Compare la courbe PAPER réelle à la courbe MODÈLE (backtest) → verdict mécanique.

    Retourne un dict complet (métriques + critères un par un + verdict) — jamais de
    chiffre inventé : données insuffisantes → verdict INSUFFISANT, pas GO par défaut."""
    pr, mr = _rets(paper), _rets(model)
    n = len(pr)
    out: dict = {"n_days_paper": n, "criteria": [], "verdict": "INSUFFISANT"}
    sp, sm = _sharpe_ann(pr), _sharpe_ann(mr)
    ddp, ddm = _max_dd(paper), _max_dd(model)
    out.update({"sharpe_paper": None if sp is None else round(sp, 3),
                "sharpe_model": None if sm is None else round(sm, 3),
                "maxdd_paper": round(ddp, 4), "maxdd_model": round(ddm, 4)})
    mintrl = _min_trl_days(sp)
    out["min_trl_days"] = mintrl

    c1 = n >= min_days
    out["criteria"].append({"name": f"track record ≥ {min_days} j", "value": n, "ok": c1})
    c_trl = (mintrl is None) or (n >= mintrl)
    out["criteria"].append({"name": "N ≥ MinTRL (Sharpe distinguable de 0)",
                            "value": f"{n} vs {mintrl if mintrl is not None else 'n/d'}",
                            "ok": c_trl})
    c2 = sp is not None and sm is not None and (sm - sp) <= max_sharpe_drift
    out["criteria"].append({"name": f"dérive Sharpe ≤ {max_sharpe_drift} pt",
                            "value": "n/d" if sp is None or sm is None
                            else round(sm - sp, 3), "ok": bool(c2)})
    c3 = ddp >= ddm - 1e-9                          # dd négatifs : paper pas PIRE que promis
    out["criteria"].append({"name": "MaxDD paper ≤ MaxDD backtest",
                            "value": f"{ddp:.1%} vs {ddm:.1%}", "ok": c3})

    if not c1 or not c_trl:
        out["verdict"] = "INSUFFISANT"               # trop tôt pour trancher — pas un NO-GO
    elif c2 and c3:
        out["verdict"] = "GO"
    else:
        out["verdict"] = "NO-GO"
    out["decision"] = {
        "GO": "premier euro réel LIMITÉ autorisé (sizing défensif, Alpaca actions uniquement)",
        "NO-GO": "re-calibrage requis — le paper ne confirme pas le backtest",
        "INSUFFISANT": "continuer le paper — trancher serait inventer",
    }[out["verdict"]]
    return out
