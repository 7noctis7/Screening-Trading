"""Applique la cartographie macro→actifs (config/macro_impact.yaml).

Produit, à partir d'un RegimeState + surprises : un multiplicateur d'exposition
globale, des inclinaisons de facteurs (additif aux poids du ranking) et des
inclinaisons par classe d'actif. Pur / testable.
"""

from __future__ import annotations

from packages.core.models import RegimeState


class MacroImpactMap:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg

    def exposure_multiplier(self, regime: RegimeState) -> float:
        m_risk = self.cfg.get("exposure_by_risk_mode", {}).get(regime.risk_mode.value, 1.0)
        m_cycle = self.cfg.get("exposure_by_cycle", {}).get(regime.cycle.value, 1.0)
        return float(m_risk * m_cycle)

    def factor_tilts(self, regime: RegimeState) -> dict[str, float]:
        tilts = dict(self.cfg.get("factor_tilts", {}).get(regime.risk_mode.value, {}))
        for f, v in self.cfg.get("factor_tilts", {}).get(regime.cycle.value, {}).items():
            tilts[f] = tilts.get(f, 0.0) + v
        return tilts

    def class_tilts(self, surprises: dict[str, float], thr: float = 0.5) -> dict[str, float]:
        resp = self.cfg.get("surprise_response", {})
        out: dict[str, float] = {}
        if surprises.get("inflation", 0) > thr:
            _merge(out, resp.get("inflation_up", {}))
        if surprises.get("growth", 0) > thr:
            _merge(out, resp.get("growth_up", {}))
        elif surprises.get("growth", 0) < -thr:
            _merge(out, resp.get("growth_down", {}))
        return out


def _merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        dst[k] = dst.get(k, 0.0) + v
