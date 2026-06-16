"""Démo bout-en-bout — assemble toute la chaîne et la fait tourner (offline, seedé).

Lance :  python scripts/demo_backtest.py
Prouve la parité d'architecture : data → régime → stratégie → risque → sizing →
broker paper → journal → métriques. Reproductible (seed). Aucune donnée réseau.

Tout est branché via les REGISTRIES (plugins) et la config YAML — changer de
stratégie/sizer = changer une chaîne de caractères, sans toucher au moteur.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.backtest import BacktestEngine  # noqa: E402
from packages.common import get_logger, load_yaml  # noqa: E402
from packages.data import data_providers  # noqa: E402
from packages.execution import CostModel, SimBroker  # noqa: E402
from packages.portfolio import metrics  # noqa: E402
from packages.regime import RegimeClassifier  # noqa: E402
from packages.risk import RiskEngine, risk_rules  # noqa: E402
from packages.portfolio.sizing import sizers  # noqa: E402
from packages.storage import (  # noqa: E402
    SqliteBarsRepository,
    UniverseRepository,
    enforce,
    validate_ohlcv,
)
from packages.data.universe import UniverseBuilder  # noqa: E402
from packages.core.models import AssetClass  # noqa: E402
from packages.strategies import strategies  # noqa: E402

log = get_logger("demo")
TIMEFRAME = "1d"  # socle daily (cf. politique data) ; 1h/4h réservés à l'intraday
_BACKTEST_CLASSES = {AssetClass.EQUITY, AssetClass.ETF}


def select_for_backtest(instruments, n=12):
    """Échantillon tradable (equity/ETF) pour une démo rapide. En prod : tout l'univers."""
    pool = [i for i in instruments if i.asset_class in _BACKTEST_CLASSES]
    return pool[:n]


def ingest_to_storage(instruments, repo: SqliteBarsRepository, years=4):
    """Pipeline medallion : provider → bronze (brut) → validation → silver (propre)."""
    import pandas as pd

    provider = data_providers.create("synthetic", seed=7, annual_vol=0.28, drift=0.08)
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=365 * years)
    for inst in instruments:
        bars = provider.fetch_ohlcv(inst.symbol, TIMEFRAME, start, end)
        repo.upsert(bars, layer="bronze")  # brut immuable
        df = pd.DataFrame(
            [{"ts": b.ts, "open": b.open, "high": b.high, "low": b.low,
              "close": b.close, "volume": b.volume} for b in bars]
        ).set_index("ts")
        enforce(validate_ohlcv(df, inst.symbol, TIMEFRAME))  # bloque si KO
        repo.upsert(bars, layer="silver")  # validé


def build_universe_data(repo, instruments):
    """Lecture depuis silver → dict {symbol: [Bar]} pour le backtest."""
    return {i.symbol: repo.read(i.symbol, TIMEFRAME, layer="silver") for i in instruments}


def build_risk_engine(cfg):
    p = cfg["portfolio"]
    rules = [
        risk_rules.create("reward_risk", min_rr=cfg["per_trade"]["min_reward_risk"]),
        risk_rules.create("max_positions", max_positions=p["max_positions"]),
        risk_rules.create("max_exposure_per_asset",
                          max_pct=p["max_exposure_per_asset_pct"]),
    ]
    return RiskEngine(rules, max_daily_drawdown_pct=p["max_daily_drawdown_pct"])


def main() -> int:
    risk_cfg = load_yaml(ROOT / "config" / "risk.yaml")
    builder = UniverseBuilder(ROOT / "config" / "universe.yaml", allow_network=False)
    built = builder.build()
    UniverseRepository(":memory:").save_snapshot(built.instruments, built.as_of)
    selection = select_for_backtest(built.instruments, n=12)
    log.info("univers", extra={"extra": {
        "total_offline": len(built.instruments),
        "reseau_sautees": built.skipped,
        "backtest_sample": [i.symbol for i in selection]}})

    repo = SqliteBarsRepository(":memory:")
    ingest_to_storage(selection, repo)
    log.info("storage", extra={"extra": {
        "bronze_rows": repo.count("bronze"), "silver_rows": repo.count("silver")}})
    data = build_universe_data(repo, selection)

    strategy = strategies.create("ma_crossover", fast=20, slow=50, atr_stop=2.0, rr=2.5)
    # Le sizer dimensionne DANS la limite d'expo par actif ; le risk engine reste
    # le backstop dur (défense en profondeur).
    sizer = sizers.create("vol_target",
                          target_annual_vol=risk_cfg["sizing"]["target_annual_vol"],
                          max_capital_frac=risk_cfg["portfolio"]["max_exposure_per_asset_pct"])
    broker = SimBroker(cash=100_000.0, costs=CostModel(fee_bps=5, slippage_bps=2))
    risk = build_risk_engine(risk_cfg)
    regime = RegimeClassifier(trend_window=100, vol_window=20)

    engine = BacktestEngine(strategy, sizer, risk, broker, regime_classifier=regime)
    result = engine.run(data)

    summ = metrics.summary(result.equity_curve, result.journal.pnls())
    print("\n" + "=" * 56)
    print(f" BACKTEST — strat={strategy.name} sizer={sizer.name}")
    print("=" * 56)
    print(f" Capital initial : 100,000")
    print(f" Equity finale   : {result.equity_curve[-1]:,.0f}")
    print(f" Rendement total : {summ['total_return']:+.1%}")
    print(f" Sharpe          : {summ['sharpe']:.2f}")
    print(f" Sortino         : {summ['sortino']:.2f}")
    print(f" Calmar          : {summ['calmar']:.2f}")
    print(f" Max drawdown    : {summ['max_drawdown']:.1%}")
    print(f" Trades          : {summ['n']}")
    print(f" Win rate        : {summ['win_rate']:.0%}")
    pf = summ["profit_factor"]
    print(f" Profit factor   : {'inf' if pf == float('inf') else f'{pf:.2f}'}")
    print(f" Expectancy/trade: {summ['expectancy']:+,.0f}")
    print(f" Frais payés      : {broker.fees_paid:,.0f}")
    print("=" * 56)

    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    result.journal.to_csv(out / "trades.csv")
    (out / "equity_curve.csv").write_text(
        "ts,equity\n" + "\n".join(
            f"{ts.isoformat()},{e:.2f}"
            for ts, e in zip(result.timestamps, result.equity_curve)),
        encoding="utf-8")
    print(f" Exports → {out}/trades.csv , {out}/equity_curve.csv\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
