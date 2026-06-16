"""Moteur de ranking multi-facteur (Module 4) — interface a contexte.

Combine des facteurs (techniques + fondamentaux) normalises en z-score
cross-sectional (global ou sector-neutral), ponderes selon regime ET classe
d'actif. Un facteur sans aucune donnee (ex. value/quality sans fondamental
charge) est retire du composite (poids non compte) - jamais une erreur.

Sortie : top N avec score composite + contribution par facteur + raison.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from packages.core.models import RegimeState, RiskMode
from packages.ranking.factors import FactorContext, factor_calcs


@dataclass
class RankedAsset:
    symbol: str
    asset_class: str
    score: float
    contributions: dict[str, float] = field(default_factory=dict)
    raw: dict[str, float] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        top = sorted(self.contributions.items(), key=lambda kv: -abs(kv[1]))[:2]
        return ", ".join(f"{k}={v:+.2f}" for k, v in top)


def _zscore(values, sectors, sector_neutral):
    """z-score cross-sectional (global ou intra-secteur). NaN -> 0."""
    def z_of(items):
        valid = {s: v for s, v in items.items() if v == v}
        if len(valid) < 2:
            return {s: 0.0 for s in items}
        arr = np.array(list(valid.values()))
        mu, sd = arr.mean(), arr.std(ddof=1)
        return {s: ((v - mu) / sd if sd > 0 else 0.0) if v == v else 0.0
                for s, v in items.items()}

    if not (sector_neutral and sectors):
        return z_of(values)
    groups = {}
    for sym, v in values.items():
        groups.setdefault(sectors.get(sym, "_"), {})[sym] = v
    out = {}
    for grp in groups.values():
        out.update(z_of(grp))
    return out


class RankingEngine:
    def __init__(self, weights_cfg, instruments_class):
        self.weights_cfg = weights_cfg
        self.cls = instruments_class

    def _weights(self, regime):
        w = dict(self.weights_cfg.get("weights", {}).get("default", {}))
        if regime and regime.risk_mode is RiskMode.RISK_OFF:
            w.update(self.weights_cfg.get("weights", {})
                     .get("regime_overrides", {}).get("risk_off", {}))
        return w

    def _applicable(self, asset_class):
        allowed = self.weights_cfg.get("class_applicability", {}).get(asset_class)
        return set(allowed) if allowed is not None else None

    def rank(self, panel, t=10**9, regime=None, top_n=20, fundamentals=None):
        ctx = FactorContext(panel, t, fundamentals)
        sectors = {s: f.sector for s, f in fundamentals.items()} if fundamentals else None
        weights = self._weights(regime)
        z, raw_all, active = {}, {}, []
        for fname in (f for f in weights if f in factor_calcs):
            calc = factor_calcs.create(fname)
            raw = calc.values(ctx)
            if all(v != v for v in raw.values()):     # aucune donnee -> facteur retire
                continue
            raw_all[fname] = raw
            z[fname] = _zscore(raw, sectors, getattr(calc, "sector_neutral", False))
            active.append(fname)
        ranked = []
        for sym in panel:
            cls = self.cls.get(sym, "equity")
            allowed = self._applicable(cls)
            contrib, wsum = {}, 0.0
            for fname in active:
                if allowed is not None and fname not in allowed:
                    continue
                contrib[fname] = weights[fname] * z[fname].get(sym, 0.0)
                wsum += weights[fname]
            score = sum(contrib.values()) / wsum if wsum > 0 else 0.0
            ranked.append(RankedAsset(sym, cls, score, contrib,
                                      {f: raw_all[f].get(sym, float("nan")) for f in active}))
        ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked[:top_n]
