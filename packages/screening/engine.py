"""Moteur de screening — filtres durs (YAML) puis scoring z-score cross-sectional.

Pipeline :
1. **Filtres** : règles `{metric, op, value}` appliquées symbole par symbole. Un symbole
   rejeté par une règle est écarté (avec la raison). Donnée manquante (NaN) → rejet par
   défaut (`on_missing: pass` pour tolérer).
2. **Scoring** : les survivants sont notés par un composite z-score (même mécanique
   que le ranking : `_zscore`). Un facteur sans donnée est ignoré.

Config (YAML) :
    filters:
      - {metric: dollar_volume, op: ">=", value: 5000000}
      - {metric: above_sma200,  op: ">=", value: 1}
      - {metric: drawdown_from_high, op: ">=", value: -0.30}
      - {metric: ret_12m, op: between, value: [0.0, 3.0]}
    scoring:
      weights: {momentum: 1.0, trend: 0.5, low_vol: 0.5}
      sector_neutral: false
      top_n: 25
"""

from __future__ import annotations

import operator as _op
from dataclasses import dataclass, field
from pathlib import Path

from packages.ranking.engine import _zscore
from packages.ranking.factors import FactorContext
from packages.screening.metrics import metric_values

_OPS = {
    ">": _op.gt, ">=": _op.ge, "<": _op.lt, "<=": _op.le, "==": _op.eq, "!=": _op.ne,
}


@dataclass
class ScreenResult:
    symbol: str
    passed: bool
    score: float = 0.0
    failed: list[str] = field(default_factory=list)          # règles non satisfaites
    metrics: dict[str, float] = field(default_factory=dict)  # valeurs brutes évaluées
    contributions: dict[str, float] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        if not self.passed:
            return "rejeté : " + " ; ".join(self.failed)
        top = sorted(self.contributions.items(), key=lambda kv: -abs(kv[1]))[:2]
        return ", ".join(f"{k}={v:+.2f}" for k, v in top)


def _passes(rule: dict, v: float, on_missing: str) -> bool:
    if v != v:  # NaN → on ne peut pas confirmer
        return on_missing == "pass"
    op = rule.get("op", ">=")
    thr = rule.get("value")
    if op == "between":
        lo, hi = thr
        return bool(lo <= v <= hi)
    fn = _OPS.get(op)
    if fn is None:
        raise ValueError(f"opérateur de filtre inconnu : {op!r}")
    return bool(fn(v, thr))


class ScreeningEngine:
    def __init__(self, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.filters: list[dict] = list(cfg.get("filters") or [])
        scoring = cfg.get("scoring") or {}
        self.weights: dict[str, float] = dict(scoring.get("weights") or {})
        self.sector_neutral: bool = bool(scoring.get("sector_neutral", False))
        self.top_n: int | None = scoring.get("top_n")

    @classmethod
    def from_yaml(cls, path: str | Path) -> ScreeningEngine:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {})

    def screen(
        self,
        panel: dict[str, list],
        t: int = 10**9,
        fundamentals: dict | None = None,
        include_rejected: bool = False,
    ) -> list[ScreenResult]:
        """Filtre puis note l'univers. Retourne les survivants triés par score
        décroissant (plus les rejetés si `include_rejected`, score 0, à la fin)."""
        ctx = FactorContext(panel, t, fundamentals)
        sectors = (
            {s: f.sector for s, f in fundamentals.items()} if fundamentals else None
        )
        cache: dict[str, dict[str, float]] = {}
        results = {sym: ScreenResult(sym, True) for sym in panel}

        # 1. filtres durs
        for rule in self.filters:
            metric = rule["metric"]
            if metric not in cache:
                cache[metric] = metric_values(metric, ctx)
            vals = cache[metric]
            label = f"{metric} {rule.get('op', '>=')} {rule.get('value')}"
            on_missing = rule.get("on_missing", "fail")
            for sym in panel:
                r = results[sym]
                v = vals.get(sym, float("nan"))
                r.metrics[metric] = v
                if not _passes(rule, v, on_missing):
                    r.passed = False
                    r.failed.append(label)

        survivors = [s for s in panel if results[s].passed]

        # 2. scoring z-score des survivants
        if self.weights and survivors:
            sec = {s: sectors.get(s) for s in survivors} if sectors else None
            zmaps: dict[str, tuple[dict[str, float], float]] = {}
            for fname, w in self.weights.items():
                if fname not in cache:
                    cache[fname] = metric_values(fname, ctx)
                raw = {s: cache[fname].get(s, float("nan")) for s in survivors}
                if all(v != v for v in raw.values()):  # facteur sans donnée → ignoré
                    continue
                zmaps[fname] = (_zscore(raw, sec, self.sector_neutral), float(w))
                for s in survivors:
                    results[s].metrics.setdefault(fname, raw[s])
            for s in survivors:
                contrib, wsum = {}, 0.0
                for fname, (zmap, w) in zmaps.items():
                    contrib[fname] = w * zmap.get(s, 0.0)
                    wsum += w
                results[s].contributions = contrib
                results[s].score = sum(contrib.values()) / wsum if wsum > 0 else 0.0

        out = [results[s] for s in panel if results[s].passed]
        out.sort(key=lambda r: r.score, reverse=True)
        if self.top_n:
            out = out[: self.top_n]
        if include_rejected:
            out += [results[s] for s in panel if not results[s].passed]
        return out
