"""Calcul des poids du preset — production (dernière barre) et pas de rebalancement.

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier). Comportement
repris à l'identique.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.cov_risk import cov_annual as _cov_annual
from packages.backtest.cov_risk import cov_for_step
from packages.backtest.panel import fenetre_commune
from packages.backtest.preset_config import MIN_BARRES_REGIME
from packages.backtest.preset_helpers import (
    adaptive_cap as _adaptive_cap_fn,
)
from packages.backtest.preset_helpers import (
    breadth as _breadth_fn,
)
from packages.backtest.preset_helpers import (
    cap_weights as _cap_weights_fn,
)
from packages.backtest.preset_helpers import (
    mom_tilt as _mom_tilt_fn,
)
from packages.backtest.preset_helpers import (
    regime_mult as _regime_mult_fn,
)
from packages.portfolio.optimize import equal_risk_contribution


def _concentrate(w: np.ndarray, min_weight: float) -> np.ndarray:
    """Élimine les positions sous `min_weight` (fraction de l'investi) et redistribue leur poids
    aux survivants → portefeuille CONCENTRÉ sur les meilleures convictions, même gross investi.
    Anti-« poussière » : fini les dizaines de lignes à quelques dollars."""
    inv = float(w.sum())
    if inv <= 0 or min_weight <= 0:
        return w
    w = np.where(w / inv < min_weight, 0.0, w)
    keep = float(w.sum())
    return w * (inv / keep) if keep > 0 else w


def _erc_blackout(A, cov, t, blackout_move, min_names):
    """ERC + blackout appliqué SEULEMENT s'il laisse un portefeuille diversifié, puis renormalisé."""
    w = np.asarray(equal_risk_contribution(cov), float)
    last2 = A[:, t] / A[:, t - 2] - 1
    w_bl = np.where(np.abs(last2) > blackout_move, 0.0, w)
    if int((w_bl > 0).sum()) >= min_names:
        w = w_bl
    s1 = w.sum()
    return w / s1 if s1 > 0 else w


def _weights_at(A, rets, t, lookback, blackout_move, max_weight, min_names, tgt_vol):
    """Poids du preset au temps t (ERC + blackout diversifié + plafond + DD-target)."""
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return None
    cov = _cov_annual(win)
    w = _cap_weights_fn(_erc_blackout(A, cov, t, blackout_move, min_names), max_weight)
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    return w * gross


def _prod_panel(data: dict, lookback: int):
    """Panel de PRODUCTION : exige MIN_BARRES_REGIME barres (MM200 + pic historique).

    Le seuil d'éligibilité était à `lookback` (120), et `min(len)` laissait ensuite la série
    la plus courte fixer L pour tout le monde. Mesuré : une seule série de 125 barres,
    incapable d'entrer dans le top-K, déplaçait les poids de PRODUCTION de 2 points — la
    MM200 devenait une MM125 et le pic se calculait sur 125 jours.
    """
    syms = [s for s, b in data.items() if b and len(b) > max(lookback, MIN_BARRES_REGIME)]
    if len(syms) < 5:
        return None, None, None
    syms, L, _panel = fenetre_commune(data, syms)
    if len(syms) < 5 or L < MIN_BARRES_REGIME:
        return None, None, None
    return syms, L, {s: np.asarray([x.close for x in data[s]][-L:], float) for s in syms}


def preset_latest_weights(data: dict, quality: dict | None = None,
                          asset_classes: dict | None = None,
                          dd_target: float = 0.35, band: float = 0.03, lookback: int = 120,
                          top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
                          max_weight: float = 0.10, min_names: int = 12,
                          regime_gate: bool = True, mom_tilt: bool = True,
                          breadth_gate: bool = True, min_weight: float = 0.025,
                          corr_tighten: bool = True, cov_denoise: bool = False) -> dict:
    """Poids cibles ACTUELS du preset (dernière barre) — pilote la PRODUCTION (make live).

    Même logique que le backtest (qualité top-K -> risk-parity ERC -> DD-target -> blackout), mais
    calculée au dernier point seulement. Renvoie {symbol: poids} (somme <= 1, le reste en cash).
    """
    syms, L, M = _prod_panel(data, lookback)
    if M is None:
        return {}
    quality = quality or {}
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    universe = (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                if len(q) >= 5 else syms[:top_k])
    A = np.asarray([M[s] for s in universe])
    mkt = A.mean(axis=0)                            # indice de marché (porte régime + frein DD)
    rets = A[:, 1:] / A[:, :-1] - 1
    t = L - 1
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return {}
    cov, _, _ = cov_for_step(win, denoise=cov_denoise)   # défaut : covariance historique
    w = _erc_blackout(A, cov, t, blackout_move, min_names)
    if mom_tilt:                                    # #4 tilt momentum (avant le plafond)
        w = _mom_tilt_fn(A, t, w)
    # PLAFOND DE CONCENTRATION (rail prod) : resserré ×0,5 si la corrélation moyenne de
    # l'univers dépasse 0,60 (diversification en breakdown → plus de noms imposés).
    w = _cap_weights_fn(w, _adaptive_cap_fn(cov, max_weight, corr_tighten))
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    if regime_gate:                                 # #5 régime + #6 frein DD (production)
        gross *= _regime_mult_fn(mkt, t)
    if breadth_gate:                                # #8 ampleur de marché (production)
        gross *= float(np.clip(_breadth_fn(A, t) / 0.5, 0.0, 1.0))
    w = _concentrate(w * gross, min_weight)  # jette la poussière → moins d'actifs, mieux dimensionnés
    return {universe[i]: round(float(w[i]), 4) for i in range(len(universe)) if w[i] > 1e-4}
