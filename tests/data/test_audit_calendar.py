"""Calendrier de cotation conscient de la classe (crypto 24/7 vs jours ouvrés)."""

from datetime import UTC, datetime, timedelta

from packages.core.models import Bar
from packages.data.audit import _is_crypto, audit_series


def _weekday_bars(symbol="X", n=60):
    """n barres en jours OUVRÉS uniquement (week-ends absents)."""
    bars, d, made = [], datetime(2024, 1, 1, tzinfo=UTC), 0
    while made < n:
        if d.weekday() < 5:
            px = 100.0 + made * 0.1                # ramp léger → évite « prix figé »
            bars.append(Bar(symbol, "1d", d, px, px * 1.01, px * 0.99, px, 1000.0))
            made += 1
        d += timedelta(days=1)
    return bars


def test_is_crypto_detection():
    assert _is_crypto("BTC-USD") and _is_crypto("ETH/USDC") and _is_crypto("SOL/USDT")
    assert not _is_crypto("AAPL") and not _is_crypto("EURUSD=X")


def test_crypto_flags_missing_weekends():
    # une série crypto sans week-ends = ~29% de barres manquantes vs calendrier 365
    out = audit_series("BTC-USD", _weekday_bars(), now=datetime(2024, 6, 1).date())
    comp = [a for a in out if a.kind == "completeness" and "manquantes" in a.detail]
    assert comp and "calendaires" in comp[0].detail


def test_equity_same_dates_not_flagged():
    # mêmes dates, mais en ACTION → calendrier ouvré → pas de trou
    out = audit_series("AAPL", _weekday_bars(), now=datetime(2024, 6, 1).date())
    comp = [a for a in out if a.kind == "completeness" and "manquantes" in a.detail]
    assert not comp
