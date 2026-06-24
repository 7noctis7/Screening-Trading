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
