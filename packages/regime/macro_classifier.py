"""Classifieur de cycle MACRO (nowcasting) — point-in-time via MacroStore.

Combine des signaux macro lus tels que connus à `t` :
- courbe des taux 10a−3m (T10Y3M) : inversion = signal de récession (fix audit 07/15 :
  le classifieur lisait T10Y2Y alors que l'ingestion ALFRED écrit T10Y3M → la série
  point-in-time persistée n'était JAMAIS consommée) ;
- activité (ISM/PMI) : < 50 = contraction ;
- emploi (UNRATE) : tendance haussière du chômage = ralentissement ;
- VIX : stress de marché → risk-off.

→ CyclePhase + RiskMode + extras (les lectures macro). Combinable avec le
classifieur prix (breadth, tendance des indices).
"""

from __future__ import annotations

from datetime import datetime

from packages.core.models import CyclePhase, RegimeState, RiskMode
from packages.storage.macro_store import MacroStore


class MacroRegimeClassifier:
    name = "macro_nowcast_v1"

    def __init__(self, store: MacroStore, curve_id: str = "T10Y3M",
                 activity_id: str = "ISM", unrate_id: str = "UNRATE",
                 vix_id: str = "VIXCLS", high_vix: float = 25.0) -> None:
        self.store = store
        self.curve_id, self.activity_id = curve_id, activity_id
        self.unrate_id, self.vix_id, self.high_vix = unrate_id, vix_id, high_vix

    def classify(self, t: datetime) -> RegimeState:
        curve = self._val(self.curve_id, t)
        pmi = self._val(self.activity_id, t)
        vix = self._val(self.vix_id, t)
        unrate_rising = self._rising(self.unrate_id, t)
        extras = {"curve_2s10s": curve, "pmi": pmi, "vix": vix,
                  "unemp_rising": unrate_rising}

        inverted = curve is not None and curve < 0
        contracting = pmi is not None and pmi < 50
        if inverted and contracting:
            cycle = CyclePhase.RECESSION
        elif contracting or unrate_rising:
            cycle = CyclePhase.SLOWDOWN
        elif pmi is not None and pmi >= 50 and not unrate_rising:
            cycle = CyclePhase.EXPANSION
        else:
            cycle = CyclePhase.RECOVERY

        if vix is not None and vix > self.high_vix:
            risk = RiskMode.RISK_OFF
        elif cycle in (CyclePhase.RECESSION, CyclePhase.SLOWDOWN):
            risk = RiskMode.RISK_OFF if inverted else RiskMode.NEUTRAL
        else:
            risk = RiskMode.RISK_ON
        return RegimeState(t, cycle, risk, vix=vix, extras=extras)

    def _val(self, sid: str, t: datetime) -> float | None:
        r = self.store.as_of(sid, t)
        return r[1] if r else None

    def _rising(self, sid: str, t: datetime, lookback: int = 3) -> bool:
        hist = self.store.history_as_of(sid, t)
        if len(hist) < lookback + 1:
            return False
        recent = [v for _, v in hist[-lookback - 1:]]
        return recent[-1] > recent[0]
