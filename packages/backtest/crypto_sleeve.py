"""Sleeve CRYPTO — best practice : les cryptos n'ont pas de fondamentaux, donc le tilt qualité du
preset ne s'applique pas. On construit une poche crypto par **risk-parity (ERC) + vol-target +
plafond de concentration**, sur les paires liquides. Même discipline de risque que les actions
(jamais de levier), mais univers sélectionné par la LIQUIDITÉ, pas la qualité comptable.

La poche est ensuite mélangée à l'allocation actions selon `QUANT_CRYPTO_PCT` (part du capital).
"""

from __future__ import annotations

import numpy as np

from packages.backtest.panel import fenetre_commune
from packages.backtest.preset_backtest import _weights_at


def liquidite(barres: list, fenetre: int = 60) -> float:
    """Dollar-volume MÉDIAN (close × volume) des `fenetre` dernières barres ; 0 si inconnu.
    La médiane résiste aux journées de volume aberrant (listing, incident d'exchange)."""
    dv = [float(b.close) * float(getattr(b, "volume", 0.0) or 0.0) for b in barres[-fenetre:]]
    dv = [x for x in dv if np.isfinite(x) and x > 0]
    return float(np.median(dv)) if dv else 0.0


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
    # tri par DOLLAR-VOLUME médian récent (QML-014). L'ancien « proxy » valait l'écart-type
    # du PRIX en dollars : une paire chère et morte passait devant une paire échangée.
    universe = sorted(syms, key=lambda s: liquidite(data[s]), reverse=True)[:top_k]
    # La crypto compte beaucoup de cotations récentes : sans fenêtre commune, un seul jeton
    # listé il y a trois mois ramenait toute la poche à trois mois d'historique.
    universe, L, _panel = fenetre_commune(data, universe, min_noms=2)
    if len(universe) < 2:
        return {}
    A = np.asarray([[x.close for x in data[s]][-L:] for s in universe], float)
    rets = A[:, 1:] / A[:, :-1] - 1
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    w = _weights_at(A, rets, L - 1, lookback, blackout_move, max_weight, min_names, tgt_vol)
    if w is None:
        return {}
    return {universe[i]: round(float(w[i]), 4) for i in range(len(universe)) if w[i] > 1e-4}
