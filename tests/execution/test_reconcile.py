from packages.execution import reconcile
from packages.core.models import Position, Side


def _p(sym, qty): return Position(sym, Side.LONG, qty, 100.0)


def test_in_sync_is_ok():
    r = reconcile([_p("AAPL", 10)], [_p("AAPL", 10)])
    assert r.ok


def test_detects_quantity_divergence():
    r = reconcile([_p("AAPL", 10)], [_p("AAPL", 8)])
    assert not r.ok
    assert r.divergences[0].diff == 2


def test_detects_missing_position():
    r = reconcile([_p("AAPL", 10), _p("MSFT", 5)], [_p("AAPL", 10)])
    syms = {d.instrument for d in r.divergences}
    assert "MSFT" in syms
