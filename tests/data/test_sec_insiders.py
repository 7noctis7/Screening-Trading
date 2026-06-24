"""Tests du scaffold insiders SEC Form 4 (parsing + cluster, hors-ligne)."""

from datetime import date

from packages.data.sec_insiders import (
    _parse_efts,
    fetch_recent_form4,
    insider_cluster_score,
)


def test_parse_efts_extracts_ticker():
    data = {"hits": {"hits": [
        {"_source": {"display_names": ["APPLE INC (AAPL) (CIK 0000320193)"],
                     "file_date": "2026-06-20"}},
        {"_source": {"display_names": ["NO TICKER HERE"], "file_date": "2026-06-20"}},
    ]}}
    out = _parse_efts(data)
    assert len(out) == 1 and out[0]["ticker"] == "AAPL"


def test_parse_efts_empty():
    assert _parse_efts(None) == [] and _parse_efts({}) == []


def test_cluster_score_counts_distinct_filers_in_window():
    filings = [
        {"ticker": "AAPL", "date": "2026-06-20", "who": "CEO"},
        {"ticker": "AAPL", "date": "2026-06-21", "who": "CFO"},
        {"ticker": "AAPL", "date": "2026-06-20", "who": "CEO"},   # doublon déclarant
        {"ticker": "MSFT", "date": "2026-06-20", "who": "CEO"},
        {"ticker": "AAPL", "date": "2026-01-01", "who": "OLD"},   # hors fenêtre
    ]
    score = insider_cluster_score(
        filings, "AAPL", window_days=30, now=date(2026, 6, 25))
    assert score == 2                            # CEO + CFO distincts dans la fenêtre


def test_fetch_offline_safe():
    assert isinstance(fetch_recent_form4(limit=1), list)


_FORM4 = """<ownershipDocument><nonDerivativeTable>
<nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>1000</value></transactionShares>
<transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
</transactionAmounts></nonDerivativeTransaction>
<nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>400</value></transactionShares>
<transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
</transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""


def test_parse_form4_buy_and_sell():
    from packages.data.sec_insiders import parse_form4_xml
    out = parse_form4_xml(_FORM4)
    assert out["available"] and out["acquired"] == 1000.0 and out["disposed"] == 400.0
    assert out["n_buys"] == 1 and out["n_sells"] == 1
    assert out["net_shares"] == 600.0 and out["direction"] == "buy"


def test_parse_form4_garbage():
    from packages.data.sec_insiders import parse_form4_xml
    assert parse_form4_xml("not xml")["available"] is False


def test_net_insider_signal_cluster():
    from packages.data.sec_insiders import net_insider_signal
    parsed = [
        {"available": True, "direction": "buy", "net_shares": 1000.0},
        {"available": True, "direction": "buy", "net_shares": 500.0},
        {"available": True, "direction": "sell", "net_shares": -200.0},
    ]
    out = net_insider_signal(parsed)
    assert out["available"] and out["n_buyers"] == 2 and out["n_sellers"] == 1
    assert out["cluster"] == 1 and out["bullish"] is True


def test_net_insider_signal_empty():
    from packages.data.sec_insiders import net_insider_signal
    assert net_insider_signal([{"available": False}])["available"] is False
