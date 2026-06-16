"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.api import payloads as PL
from packages.common import load_yaml
from packages.data import data_providers
from packages.execution import CostModel, LiveTradingEngine, SimBroker
from packages.portfolio.sizing import sizers
from packages.portfolio import (attribution, correlation_matrix, cluster, expert_review,
                                monte_carlo, relative_metrics, risk_metrics_fn)
from packages.portfolio.metrics import returns_from_equity
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.risk import RiskEngine, risk_rules
from packages.storage import MacroStore
from packages.strategies import strategies

ROOT = Path(__file__).resolve().parents[2]
_SYMS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]


def build_snapshot(seed: int = 7) -> dict:
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    data = {s: data_providers.create("synthetic", seed=seed + i, drift=0.08).fetch_ohlcv(
        s, "1d", start, start + timedelta(days=500)) for i, s in enumerate(_SYMS)}

    broker = SimBroker(cash=100_000, costs=CostModel())
    eng = LiveTradingEngine(
        strategy=strategies.create("ma_crossover", fast=20, slow=50),
        sizer=sizers.create("vol_target", max_capital_frac=0.10),
        risk_engine=RiskEngine([risk_rules.create("max_positions", max_positions=10),
                                risk_rules.create("max_exposure_per_asset", max_pct=0.10)]),
        broker=broker)
    n = max(len(b) for b in data.values())
    equity = []
    for i in range(60, n):
        eng.step({s: data[s][: i + 1] for s in _SYMS})
        equity.append(broker.equity())

    # régime macro point-in-time
    ms = MacroStore(":memory:"); ms.upsert(synthetic_macro(start, months=24))
    regime = MacroRegimeClassifier(ms).classify(start + timedelta(days=480))
    impact = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))
    expo = impact.exposure_multiplier(regime)

    # ranking sur le dernier panel
    panel = {s: data[s] for s in _SYMS}
    ranker = RankingEngine(load_yaml(ROOT / "config" / "factors.yaml"),
                           {s: "equity" for s in _SYMS})
    ranked = ranker.rank(panel, t=n - 1, regime=regime, top_n=10)

    # --- analyse de portefeuille (mesures relatives, corrélation, risque, revue) ---
    bench_px = [b.close for b in data["AAPL"][60:]]
    rel = relative_metrics(equity, bench_px)
    rets = returns_from_equity(equity)
    rm = risk_metrics_fn(rets)
    mc = monte_carlo(rets, seed=1)
    rets_by = {s: returns_from_equity([b.close for b in data[s][60:]]) for s in _SYMS}
    syms, corr = correlation_matrix({k: list(v) for k, v in rets_by.items()})
    clusters = cluster(syms, corr, 0.7)
    attr = attribution.attribute(eng.journal.all(), "strategy")
    agg = {**PL.metrics_payload(equity), **rel, **rm, **mc}

    marks = {s: data[s][-1].close for s in _SYMS}
    comp = PL.composition_payload(broker.positions(), marks)
    benches = {"S&P 500": [b.close for b in data["AAPL"][60:]],
               "BTC": [b.close for b in data["NVDA"][60:]]}
    return {
        "dashboard": {
            "regime": PL.regime_payload(regime, expo),
            "metrics": PL.metrics_payload(equity),
            "equity": PL.equity_series(equity),
            "positions": comp["rows"], "totals": comp["totals"],
        },
        "screener": PL.screener_payload(ranked, regime.ts),
        "portfolio": {
            **comp,
            "metrics": PL.metrics_payload(equity),
            "benchmarks": PL.benchmark_comparison(equity, benches),
            "analysis": {
                "relative": rel, "risk": rm, "monte_carlo": mc,
                "attribution": attr,
                "correlation": PL.correlation_payload(syms, corr, clusters),
                "review": PL.review_payload(expert_review({**agg, **comp["totals"]})),
            },
        },
        "trades": [PL.trade_payload(t) for t in eng.journal.all()[:50]],
    }
