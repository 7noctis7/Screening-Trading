"""Classifieur de régime — version rule-based (v1, top-down minimal).

Produit un `RegimeState` à partir de la tendance (cours vs SMA longue + pente)
et de la volatilité réalisée. À enrichir en P1 avec FRED/ALFRED + surprises éco
(le `RegimeState.extras` est prévu pour ça). Point-in-time : ne lit que bars[:t].
"""

from __future__ import annotations

import numpy as np

from packages.core.models import CyclePhase, RegimeState, RiskMode
from packages.indicators.registry import closes


class RegimeClassifier:
    name = "rule_based_v1"

    def __init__(self, trend_window: int = 200, vol_window: int = 20,
                 high_vol_annual: float = 0.30) -> None:
        self.trend_window = trend_window
        self.vol_window = vol_window
        self.high_vol_annual = high_vol_annual

    def classify(self, bars) -> RegimeState:
        x = np.asarray(closes(bars), float)
        ts = bars[-1].ts
        if x.size < max(self.trend_window, self.vol_window) + 1:
            return RegimeState(ts, CyclePhase.EXPANSION, RiskMode.NEUTRAL)
        ma = x[-self.trend_window :].mean()
        slope = np.polyfit(np.arange(self.trend_window), x[-self.trend_window :], 1)[0]
        rets = np.diff(np.log(x[-self.vol_window - 1 :]))
        ann_vol = float(rets.std(ddof=1) * np.sqrt(252))
        above, rising = x[-1] > ma, slope > 0
        if above and rising:
            cycle = CyclePhase.EXPANSION
        elif above and not rising:
            cycle = CyclePhase.SLOWDOWN
        elif not above and not rising:
            cycle = CyclePhase.RECESSION
        else:
            cycle = CyclePhase.RECOVERY
        risk = RiskMode.RISK_OFF if ann_vol > self.high_vol_annual else (
            RiskMode.RISK_ON if above and rising else RiskMode.NEUTRAL)
        return RegimeState(ts, cycle, risk, extras={"ann_vol": round(ann_vol, 4),
                                                     "above_ma": above})
