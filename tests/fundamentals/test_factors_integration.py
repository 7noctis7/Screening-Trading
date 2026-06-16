from datetime import datetime, timedelta, timezone
from packages.core.models import Bar
from packages.data import data_providers
from packages.fundamentals import SyntheticFundamentalsProvider
import packages.fundamentals  # enregistre value/quality
from packages.ranking import RankingEngine, factor_calcs


def _panel(syms, cls_map):
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    p = {}
    for s in syms:
        p[s] = data_providers.create("synthetic", seed=5).fetch_ohlcv(
            s, "1d", start, start + timedelta(days=400))
    return p


def test_value_quality_registered():
    assert {"value", "quality"} <= set(factor_calcs.names())


def test_fundamental_factors_drop_for_crypto():
    # crypto sans fondamental → value/quality NaN → retirés ; momentum/trend restent
    syms = ["BTC", "ETH", "SOL"]
    cls = {s: "crypto" for s in syms}
    panel = _panel(syms, cls)
    cfg = {"weights": {"default": {"momentum": 0.5, "value": 0.5}}}
    ranked = RankingEngine(cfg, cls).rank(panel, fundamentals=None, top_n=3)
    # 'value' absent (pas de fondamental) → seules contributions = momentum
    assert all("value" not in r.contributions for r in ranked)
    assert all("momentum" in r.contributions for r in ranked)


def test_quality_uses_fundamentals_for_equity():
    syms = ["AAPL", "MSFT", "JPM", "XOM"]
    cls = {s: "equity" for s in syms}
    panel = _panel(syms, cls)
    funds = {s: SyntheticFundamentalsProvider().get(s) for s in syms}
    cfg = {"weights": {"default": {"quality": 1.0}}}
    ranked = RankingEngine(cfg, cls).rank(panel, fundamentals=funds, top_n=4)
    assert all("quality" in r.contributions for r in ranked)
    assert ranked[0].score >= ranked[-1].score
