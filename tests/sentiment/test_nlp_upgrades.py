"""Upgrades NLP : lexique LM étendu, Δsentiment, event-study, sources."""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from packages.sentiment.history import record_and_delta
from packages.sentiment.lexicon import score_text
from packages.sentiment.news_backtest import sentiment_event_study
from packages.sentiment.sources import sources_available


def test_extended_lexicon_covers_lm_words():
    assert score_text("strong breakthrough, robust margins") > 0
    assert score_text("impairment and litigation, dilutive writedown") < 0


def test_delta_sentiment_first_call_zero_then_reacts(tmp_path, monkeypatch):
    import packages.sentiment.history as H
    monkeypatch.setattr(H, "_F", tmp_path / "h.json")
    d0 = H.record_and_delta({"AAA": 0.5}, today="2024-01-01")
    assert d0["by_symbol"]["AAA"] == 0.0                 # pas d'historique → Δ = 0
    d1 = H.record_and_delta({"AAA": 0.9}, today="2024-01-02")
    assert d1["by_symbol"]["AAA"] > 0                    # sentiment en hausse → Δ > 0


@dataclass
class Bar:
    ts: datetime
    close: float


def _bars(n=120, drift=0.0):
    t0 = datetime(2023, 6, 1, tzinfo=timezone.utc)
    return [Bar(t0 + timedelta(days=i), 100 * math.exp(drift * i)) for i in range(n)]


def test_event_study_needs_min_events():
    data = {"AAA": _bars()}
    news = [{"symbol": "AAA", "date": date(2023, 7, 1), "headline": "strong beat"}]
    assert sentiment_event_study(data, news)["available"] is False   # < 20 événements


def test_sources_available_reports_rss():
    s = sources_available()
    assert s["rss"] is True and "openbb" in s
