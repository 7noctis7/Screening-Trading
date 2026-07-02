"""Probability of Backtest Overfitting via CSCV (Bailey et al. 2015).

Input: matrix M (T periods x N configs) of per-period returns for every
configuration tried. Output: PBO = P(the IS-best config underperforms the
median OOS). Discard the strategy family if PBO > ~0.5."""
from __future__ import annotations

from itertools import combinations

import numpy as np


def _sharpe(x: np.ndarray) -> np.ndarray:
    mu, sd = x.mean(axis=0), x.std(axis=0, ddof=1)
    sd[sd == 0] = np.inf
    return mu / sd


def pbo_cscv(M: np.ndarray, n_blocks: int = 8, max_combos: int = 200,
             seed: int = 42) -> dict:
    T, N = M.shape
    blocks = np.array_split(np.arange(T), n_blocks)
    combos = list(combinations(range(n_blocks), n_blocks // 2))
    if len(combos) > max_combos:
        rng = np.random.default_rng(seed)
        combos = [combos[i] for i in rng.choice(len(combos), max_combos, False)]
    logits = []
    for c in combos:
        is_idx = np.concatenate([blocks[i] for i in c])
        oos_idx = np.concatenate([blocks[i] for i in range(n_blocks) if i not in c])
        best = int(np.argmax(_sharpe(M[is_idx])))
        oos_sr = _sharpe(M[oos_idx])
        rank = (oos_sr < oos_sr[best]).sum() + 1  # rank of IS-best OOS
        omega = rank / (N + 1)
        logits.append(np.log(omega / (1 - omega)))
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()),
            "n_splits": len(combos),
            "median_logit": float(np.median(logits))}
