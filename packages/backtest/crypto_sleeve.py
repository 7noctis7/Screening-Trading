"""Sleeve CRYPTO — best practice : les cryptos n'ont pas de fondamentaux, donc le tilt qualité du
preset ne s'applique pas. On construit une poche crypto par **risk-parity (ERC) + vol-target +
plafond de concentration**, sur les paires liquides. Même discipline de risque que les actions
(jamais de levier), mais univers sélectionné par la LIQUIDITÉ, pas la qualité comptable.

La poche est ensuite mélangée à l'allocation actions selon `QUANT_CRYPTO_PCT` (part du capital).
"""

from __future__ import annotations

import numpy as np

from packages.backtest.preset_backtest import _weights_at


def crypto_weights(data: dict, asset_classes: dict | None = None, dd_target: float = 0.35,
                   lookback: int = 120, top_k: int = 12, k_dd: float = 2.5,
                   blackout_move: float = 0.20, max_weight: float = 0.20,
                   min_names: int = 4) -> dict:
    """Poids actuels de la poche crypto (somme ≤ 1). Univers = paires crypto les plus liquides
    (proxy : dollar-volume médian récent). blackout/plafond plus larges (crypto = plus volatil)."""
    ac = asset_classes or {}
    syms = [s for s, b in data.items()
            if (ac.get(s) == "crypto" or "/USD" in s.upper() or s.upper().endswith(("USDT", "USDC")))
            and b and len(b) > lookback]
    if len(syms) < 2:
        return {}
    # tri par liquidité approchée (prix moyen × dispersion récente — proxy d'activité)
    def _liq(s):
        c = np.asarray([x.close for x in data[s]][-60:], float)
        return float(np.mean(c)) * float(np.std(c) / (np.mean(c) + 1e-9))
    universe = sorted(syms, key=_liq, reverse=True)[:top_k]
    L = min(len(data[s]) for s in universe)
    A = np.asarray([[x.close for x in data[s]][-L:] for s in universe], float)
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    w = _weights_at(A, rets, L - 1, lookback, blackout_move, max_weight, min_names, tgt_vol)
    if w is None:
        return {}
    return {universe[i]: round(float(w[i]), 4) for i in range(len(universe)) if w[i] > 1e-4}
