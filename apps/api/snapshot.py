"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

import csv
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
_NETWORK_KINDS = {"wikipedia", "ishares_holdings", "nasdaq_trader", "coingecko"}


def _universe_section() -> dict:
    """Vue UNIVERS : sources déclarées (offline/réseau), seeds, répartition par classe."""
    cfg = load_yaml(ROOT / "config" / "universe.yaml")
    src_rows = []
    for s in cfg.get("sources", []):
        kind = s.get("kind")
        src_rows.append({
            "id": s.get("id"), "kind": kind,
            "enabled": bool(s.get("enabled", True)),
            "network": kind in _NETWORK_KINDS,
            "detail": s.get("file") or s.get("url") or "",
        })
    seeds, by_class, sample = [], {}, []
    seed_dir = ROOT / "data" / "seed"
    for path in sorted(seed_dir.glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        seeds.append({"file": path.name, "count": len(rows)})
        for r in rows:
            ac = (r.get("asset_class") or "?").strip() or "?"
            by_class[ac] = by_class.get(ac, 0) + 1
        if len(sample) < 12 and rows and rows[0].get("symbol"):
            for r in rows[:2]:
                sample.append({"symbol": r.get("symbol"), "name": r.get("name"),
                               "asset_class": r.get("asset_class"), "venue": r.get("venue")})
    return {
        "rebuild_cadence_days": cfg.get("rebuild_cadence_days"),
        "sources": src_rows,
        "sources_enabled": sum(1 for s in src_rows if s["enabled"]),
        "sources_total": len(src_rows),
        "seeds": seeds,
        "seed_total": sum(s["count"] for s in seeds),
        "by_asset_class": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "sample": sample,
        "active_symbols": _SYMS,
    }


_SECTOR_CONSTITUENTS = {
    "Technologie": ["NVDA", "MSFT", "AAPL", "AVGO", "AMD"],
    "Énergie": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Finance": ["JPM", "BAC", "GS", "MS", "BLK"],
    "Santé": ["LLY", "UNH", "JNJ", "MRK", "PFE"],
    "Conso. discrétionnaire": ["AMZN", "TSLA", "HD", "NKE", "MCD"],
    "Conso. de base": ["PG", "KO", "PEP", "COST", "WMT"],
    "Industrie": ["CAT", "BA", "GE", "HON", "UPS"],
    "Services publics": ["NEE", "DUK", "SO", "AEP", "D"],
}


def _setup_label(mom: float, trend: float) -> str:
    if mom > 0.05 and trend > 0.02:
        return "tendance haussière confirmée"
    if mom > 0.05 and trend <= 0.02:
        return "momentum naissant"
    if mom < -0.05 and trend < -0.02:
        return "tendance baissière"
    if trend > 0.02 and mom <= 0.05:
        return "rebond au-dessus de la MM50"
    return "neutre / range"


def _themes_section(start) -> dict:
    """Thèmes de marché : performance YTD par secteur (bullish/bearish) + meilleurs setups.

    Génère des trajectoires synthétiques (reproductibles) avec un drift différencié par
    secteur pour produire une dispersion réaliste, puis classe les secteurs par YTD et,
    dans chaque secteur, les actifs au meilleur setup (momentum + tendance vs MM50).
    """
    import numpy as np

    from packages.data import data_providers

    sectors_in = list(_SECTOR_CONSTITUENTS.items())
    # drift étalé de baissier à haussier, attribué de façon déterministe aux secteurs
    drifts = np.linspace(-0.14, 0.24, len(sectors_in))
    out_sectors = []
    for (sector, tickers), drift in zip(sectors_in, drifts):
        prov = data_providers.create("synthetic", seed=11, drift=float(drift), annual_vol=0.16)
        assets = []
        for sym in tickers:
            bars = prov.fetch_ohlcv(sym, "1d", start, start + timedelta(days=365))
            close = np.array([b.close for b in bars], float)
            if close.size < 60:
                continue
            ytd = float(close[-1] / close[0] - 1.0)
            mom = float(close[-1] / close[-63] - 1.0)            # ~3 mois
            sma50 = float(close[-50:].mean())
            trend = float((close[-1] - sma50) / sma50)
            setup = 0.6 * mom + 0.4 * trend
            assets.append({"symbol": sym, "ytd": round(ytd, 4), "momentum": round(mom, 4),
                           "trend": round(trend, 4), "setup_score": round(setup, 4),
                           "setup": _setup_label(mom, trend)})
        if not assets:
            continue
        ytd_sec = sum(a["ytd"] for a in assets) / len(assets)
        mom_sec = sum(a["momentum"] for a in assets) / len(assets)
        stance = "bullish" if ytd_sec > 0.05 else "bearish" if ytd_sec < -0.05 else "neutral"
        top = sorted(assets, key=lambda a: a["setup_score"], reverse=True)[:3]
        out_sectors.append({
            "sector": sector, "ytd": round(ytd_sec, 4), "momentum": round(mom_sec, 4),
            "stance": stance, "n": len(assets), "top_assets": top,
        })
    out_sectors.sort(key=lambda s: s["ytd"], reverse=True)
    return {
        "as_of": (start + timedelta(days=365)).isoformat(),
        "sectors": out_sectors,
        "bullish": [s["sector"] for s in out_sectors if s["stance"] == "bullish"],
        "bearish": [s["sector"] for s in out_sectors if s["stance"] == "bearish"],
    }


def _data_section(data: dict) -> dict:
    """Vue DONNÉES : collecte (providers, barres, qualité) + couches de base de données."""
    import pandas as pd

    from packages.storage.quality import validate_ohlcv

    collection = []
    for s in _SYMS:
        bars = data[s]
        collection.append({
            "symbol": s, "bars": len(bars),
            "start": bars[0].ts.isoformat(), "end": bars[-1].ts.isoformat(),
            "last_close": round(bars[-1].close, 2),
        })
    bars = data[_SYMS[0]]
    df = pd.DataFrame(
        [{"open": b.open, "high": b.high, "low": b.low,
          "close": b.close, "volume": b.volume} for b in bars],
        index=pd.DatetimeIndex([b.ts for b in bars]))
    rep = validate_ohlcv(df, _SYMS[0], "1d", max_gap_ratio=0.5)
    src_cfg = load_yaml(ROOT / "config" / "data_sources.yaml")
    return {
        "provider": "synthetic",
        "fallback_order": src_cfg.get("ohlcv", {}).get("fallback_order", []),
        "fundamentals_provider": src_cfg.get("fundamentals", {}).get("provider"),
        "cache": src_cfg.get("ohlcv", {}).get("cache"),
        "collection": collection,
        "total_bars": sum(c["bars"] for c in collection),
        "quality": {"symbol": rep.symbol, "n_rows": rep.n_rows, "ok": rep.ok,
                    "errors": rep.errors, "warnings": rep.warnings},
        "layers": [
            {"name": "Bronze — barres brutes", "store": "bars_repo · duckdb_bars_repo",
             "desc": "OHLCV ingéré par symbole/timeframe, validé par contrats qualité"},
            {"name": "Silver — features", "store": "feature_store",
             "desc": "indicateurs & facteurs calculés, versionnés (anti-fuite)"},
            {"name": "Gold — journal & univers", "store": "journal · universe_repo · macro_store",
             "desc": "trades clôturés, snapshots d'univers datés, macro point-in-time"},
            {"name": "Sauvegardes", "store": "backup",
             "desc": "sauvegarde / restauration des stores"},
        ],
    }


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
    all_trades = eng.journal.all()
    trade_stats = PL.trade_stats_payload(all_trades)
    # axe temporel réel (horodatage de chaque pas d'equity) — partagé courbe/benchmarks
    ts_list = [data["AAPL"][i].ts for i in range(60, n)]
    dates = [ts.isoformat() for ts in ts_list]
    return {
        "dashboard": {
            "regime": PL.regime_payload(regime, expo),
            "metrics": PL.metrics_payload(equity),
            "equity": PL.equity_series(equity, ts_list),
            "dates": dates,
            "positions": comp["rows"], "totals": comp["totals"],
            "trade_stats": trade_stats,
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
        "trades": [PL.trade_payload(t) for t in all_trades[:200]],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "universe": _universe_section(),
        "data": _data_section(data),
        "themes": _themes_section(start),
    }
