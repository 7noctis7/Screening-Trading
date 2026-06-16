"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.api import payloads as PL
from packages.backtest.fast_swing import fast_swing_backtest
from packages.common import load_yaml
from packages.data import data_providers
from packages.execution import CostModel
from packages.portfolio import (attribution, correlation_matrix, cluster, expert_review,
                                monte_carlo, relative_metrics, risk_metrics_fn)
from packages.portfolio.metrics import returns_from_equity
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.storage import MacroStore

ROOT = Path(__file__).resolve().parents[2]
_NETWORK_KINDS = {"wikipedia", "ishares_holdings", "nasdaq_trader", "coingecko"}
_HISTORY_DAYS = 1700        # ~4,6 ans d'historique jusqu'à aujourd'hui


def _seed_universe() -> list[dict]:
    """Univers COMPLET dédupliqué (par symbole) à partir des seeds — source unique."""
    seen: dict[str, dict] = {}
    for path in sorted((ROOT / "data" / "seed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sym = (r.get("symbol") or "").strip()
                if sym and sym not in seen:
                    seen[sym] = {
                        "symbol": sym, "name": r.get("name") or "",
                        "asset_class": (r.get("asset_class") or "equity").strip() or "equity",
                        "venue": r.get("venue") or "", "currency": r.get("currency") or "",
                        "sector": r.get("sector") or "", "source": path.stem,
                    }
    return list(seen.values())


def _universe_section(instruments: list[dict]) -> dict:
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
    by_class, by_venue = {}, {}
    for r in instruments:
        ac = (r.get("asset_class") or "?").strip() or "?"
        by_class[ac] = by_class.get(ac, 0) + 1
        ven = (r.get("venue") or "?").strip() or "?"
        by_venue[ven] = by_venue.get(ven, 0) + 1
    seeds = []
    for path in sorted((ROOT / "data" / "seed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            cnt = sum(1 for _ in csv.DictReader(f))
        seeds.append({"file": path.name, "count": cnt,
                      "as_of": datetime.fromtimestamp(path.stat().st_mtime,
                                                      timezone.utc).isoformat()})
    rows = sorted(instruments, key=lambda r: (r["asset_class"], r["symbol"]))
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "rebuild_cadence_days": cfg.get("rebuild_cadence_days"),
        "sources": src_rows,
        "sources_enabled": sum(1 for s in src_rows if s["enabled"]),
        "sources_total": len(src_rows),
        "seeds": seeds,
        "seed_total": len(instruments),
        "by_asset_class": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "by_venue": dict(sorted(by_venue.items(), key=lambda kv: -kv[1])[:12]),
        "instruments": rows,                  # UNIVERS COMPLET (pas un échantillon)
        "instruments_total": len(rows),
    }


# Thèmes structurels (4ᵉ révolution industrielle, K. Schwab) + secteurs classiques.
# Chaque thème : panier de proxies + biais de drift/vol thématique (synthétique, reproductible).
_SECTORS = {
    # --- 4ᵉ révolution industrielle ---
    "Intelligence artificielle":     {"tickers": ["NVDA", "MSFT", "GOOGL", "PLTR", "SNOW"], "drift": 0.30, "vol": 0.24},
    "Semi-conducteurs":              {"tickers": ["NVDA", "TSM", "AVGO", "AMD", "ASML"],    "drift": 0.26, "vol": 0.26},
    "Crypto & Blockchain":           {"tickers": ["COIN", "MSTR", "MARA", "RIOT", "HUT"],   "drift": 0.22, "vol": 0.45},
    "Cloud & Datacenters":           {"tickers": ["MSFT", "AMZN", "GOOGL", "EQIX", "DLR"],  "drift": 0.19, "vol": 0.18},
    "Cybersécurité":                 {"tickers": ["CRWD", "PANW", "ZS", "FTNT", "S"],       "drift": 0.17, "vol": 0.22},
    "Espace & Défense":              {"tickers": ["LMT", "RTX", "BA", "NOC", "RKLB"],       "drift": 0.12, "vol": 0.20},
    "Robotique & Automatisation":    {"tickers": ["ABB", "ISRG", "ROK", "TER", "FANUY"],    "drift": 0.10, "vol": 0.18},
    "Véhicules électriques":         {"tickers": ["TSLA", "RIVN", "LCID", "BYDDY", "NIO"],  "drift": 0.04, "vol": 0.40},
    "Fintech & Paiements":           {"tickers": ["V", "MA", "PYPL", "SQ", "ADYEY"],        "drift": 0.06, "vol": 0.20},
    "Biotech & Génomique":           {"tickers": ["LLY", "VRTX", "REGN", "CRSP", "MRNA"],   "drift": 0.03, "vol": 0.24},
    "Énergie propre & Transition":   {"tickers": ["ENPH", "FSLR", "NEE", "PLUG", "BE"],     "drift": -0.04, "vol": 0.30},
    # --- secteurs GICS classiques ---
    "Énergie (fossile)":             {"tickers": ["XOM", "CVX", "COP", "SLB", "EOG"],       "drift": 0.09, "vol": 0.18},
    "Industrie":                     {"tickers": ["CAT", "GE", "HON", "UPS", "DE"],         "drift": 0.06, "vol": 0.16},
    "Conso. de base":                {"tickers": ["PG", "KO", "PEP", "COST", "WMT"],        "drift": 0.05, "vol": 0.12},
    "Finance":                       {"tickers": ["JPM", "BAC", "GS", "MS", "BLK"],         "drift": 0.03, "vol": 0.18},
    "Services publics":              {"tickers": ["DUK", "SO", "AEP", "D", "EXC"],          "drift": 0.01, "vol": 0.12},
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

    out_sectors = []
    for sector, cfg in _SECTORS.items():
        tickers = cfg["tickers"]
        prov = data_providers.create("synthetic", seed=11, drift=float(cfg["drift"]),
                                     annual_vol=float(cfg.get("vol", 0.18)))
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


def _data_section(data: dict, acmap: dict[str, str]) -> dict:
    """Vue DONNÉES : collecte (providers, barres, qualité) + couches de base de données."""
    import pandas as pd

    from packages.storage.quality import validate_ohlcv

    symbols = list(data)
    collection = []
    for s in symbols:
        bars = data[s]
        collection.append({
            "symbol": s, "asset_class": acmap.get(s, ""), "bars": len(bars),
            "start": bars[0].ts.isoformat(), "end": bars[-1].ts.isoformat(),
            "last_close": round(bars[-1].close, 2),
        })
    first = symbols[0]
    bars = data[first]
    df = pd.DataFrame(
        [{"open": b.open, "high": b.high, "low": b.low,
          "close": b.close, "volume": b.volume} for b in bars],
        index=pd.DatetimeIndex([b.ts for b in bars]))
    rep = validate_ohlcv(df, first, "1d", max_gap_ratio=0.5)
    src_cfg = load_yaml(ROOT / "config" / "data_sources.yaml")
    return {
        "as_of": data[first][-1].ts.isoformat(),
        "symbols_total": len(symbols),
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
    # --- univers COMPLET + fenêtre jusqu'à AUJOURD'HUI ---
    instruments = _seed_universe()
    symbols = [m["symbol"] for m in instruments]
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    names = {m["symbol"]: m["name"] for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    prov = data_providers.create("synthetic", seed=seed, drift=0.08)
    data = {s: prov.fetch_ohlcv(s, "1d", start, end) for s in symbols}  # seed/symbole stable
    n = max(len(b) for b in data.values())

    # --- backtest swing VECTORISÉ sur TOUT l'univers (positions laissées ouvertes) ---
    broker, journal, equity, ts_list = fast_swing_backtest(
        data, cash=100_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.20, max_capital_frac=0.06, max_positions=20, max_pct=0.06,
        close_at_end=False)

    # régime macro point-in-time (couvre toute la fenêtre)
    months = int(_HISTORY_DAYS / 30) + 4
    ms = MacroStore(":memory:"); ms.upsert(synthetic_macro(start, months=months))
    regime = MacroRegimeClassifier(ms).classify(end - timedelta(days=2))
    impact = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))
    expo = impact.exposure_multiplier(regime)

    # ranking / screener sur TOUT l'univers
    ranker = RankingEngine(load_yaml(ROOT / "config" / "factors.yaml"), acmap)
    ranked = ranker.rank(data, t=n - 1, regime=regime, top_n=12)

    # benchmarks synthétiques INDÉPENDANTS (rebasés 100) sur la même fenêtre
    def _series(name, drift, vol):
        return [b.close for b in data_providers.create(
            "synthetic", seed=101, drift=drift, annual_vol=vol).fetch_ohlcv(name, "1d", start, end)]
    bench_px = _series("S&P 500", 0.09, 0.16)
    benches = {"S&P 500": bench_px, "NASDAQ 100": _series("NASDAQ 100", 0.13, 0.20),
               "BTC": _series("BTC", 0.25, 0.55)}

    # --- analyse de portefeuille (mesures relatives, corrélation, risque, revue) ---
    rel = relative_metrics(equity, bench_px)
    rets = returns_from_equity(equity)
    rm = risk_metrics_fn(rets)
    mc = monte_carlo(rets, seed=1)
    # corrélation sur les actifs les plus tradés (matrice lisible)
    traded = [s for s, _ in _top_traded(journal, 8)] or symbols[:8]
    rets_by = {s: returns_from_equity([b.close for b in data[s]]) for s in traded}
    syms, corr = correlation_matrix({k: list(v) for k, v in rets_by.items()})
    clusters = cluster(syms, corr, 0.7)
    all_trades = journal.all()
    attr = attribution.attribute(all_trades, "strategy")
    agg = {**PL.metrics_payload(equity), **rel, **rm, **mc}

    marks = {s: data[s][-1].close for s in symbols}
    meta_pos = {s: {"asset_class": acmap.get(s), "name": names.get(s)} for s in symbols}
    comp = PL.composition_payload(broker.positions(), marks, meta_pos)
    trade_stats = PL.trade_stats_payload(all_trades)
    # 300 trades les plus récents (couvre la récence + de nombreux actifs)
    recent = sorted(all_trades, key=lambda t: t.entry_ts, reverse=True)[:300]
    dates = [t.isoformat() for t in ts_list]
    now = datetime.now(timezone.utc)
    last_bar = ts_list[-1]
    return {
        "meta": {
            "generated_at": now.isoformat(),
            "last_bar": last_bar.isoformat(),
            "period_start": start.isoformat(),
            "delay_minutes": 15,                 # flux différé 15 min (EOD/synthétique)
            "mode": "synthetic",
            "strategy": "swing",
            "universe_size": len(symbols),
            "traded_assets": len({t.instrument for t in all_trades}),
            "n_trades": len(all_trades),
        },
        "dashboard": {
            "as_of": last_bar.isoformat(),
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
        "trades": [PL.trade_payload(t) for t in recent],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "universe": _universe_section(instruments),
        "data": _data_section(data, acmap),
        "themes": _themes_section(end - timedelta(days=365)),   # YTD = 12 derniers mois
    }


def _top_traded(journal, k: int) -> list[tuple[str, int]]:
    """k symboles les plus tradés (pour une matrice de corrélation lisible)."""
    counts: dict[str, int] = {}
    for t in journal.all():
        counts[t.instrument] = counts.get(t.instrument, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
