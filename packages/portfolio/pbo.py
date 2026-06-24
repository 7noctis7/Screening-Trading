"""PBO — Probability of Backtest Overfitting via CSCV (Bailey, Borwein, López de Prado).

DSR corrige le *multiple testing* ; le PBO répond à une autre question : la config
la MEILLEURE en in-sample est-elle aussi bonne en out-of-sample, ou est-ce un overfit ?
CSCV : on découpe le temps en S blocs, on essaie toutes les partitions IS/OOS (S/2
chacune), on choisit la championne en IS et on regarde son rang OOS. PBO = fréquence où
la championne IS tombe sous la médiane OOS (logit ≤ 0). PBO élevé = surajusté. numpy.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np


def _sharpe(x: np.ndarray) -> float:
    sd = float(x.std(ddof=1)) if x.size > 1 else 0.0
    return float(x.mean()) / sd if sd > 0 else 0.0


def pbo_cscv(perf: np.ndarray, n_splits: int = 10) -> dict:
    """PBO via CSCV. `perf` : matrice (T observations × N configs) de rendements.

    Renvoie {available, pbo, n_combos, n_configs, n_splits, median_logit}. `pbo` ∈ [0,1]
    : < 0.5 = robuste (championne IS au-dessus de la médiane OOS), > 0.5 = overfit.
    """
    m = np.asarray(perf, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        return {"available": False, "reason": "≥2 configs requises"}
    t, n = m.shape
    s = n_splits - (n_splits % 2)              # S pair
    if s < 2 or t < s:
        return {"available": False, "reason": "trop peu d'observations"}
    blocks = np.array_split(np.arange(t), s)
    half = s // 2
    lambdas: list[float] = []
    for is_sel in combinations(range(s), half):
        is_set = set(is_sel)
        is_idx = np.concatenate([blocks[b] for b in is_sel])
        oos_idx = np.concatenate([blocks[b] for b in range(s) if b not in is_set])
        is_sr = np.array([_sharpe(m[is_idx, j]) for j in range(n)])
        oos_sr = np.array([_sharpe(m[oos_idx, j]) for j in range(n)])
        n_star = int(np.argmax(is_sr))
        rank = int(np.argsort(np.argsort(oos_sr))[n_star]) + 1   # rang OOS (1..N)
        omega = min(1 - 1e-6, max(1e-6, rank / (n + 1)))
        lambdas.append(float(np.log(omega / (1 - omega))))
    lam = np.array(lambdas)
    return {"available": True, "pbo": round(float((lam <= 0).mean()), 4),
            "n_combos": int(lam.size), "n_configs": n, "n_splits": s,
            "median_logit": round(float(np.median(lam)), 4)}
