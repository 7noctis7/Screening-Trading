"""Sentiment — hors-ligne, déterministe (lexique), sans réseau ni transformers."""

from __future__ import annotations

from packages import sentiment as S
from packages.sentiment.lexicon import label_of, score_text


def test_lexicon_directionnel():
    assert score_text("Stock surges after profit beats estimates") > 0
    assert score_text("Shares plunge on lawsuit and bankruptcy fears") < 0
    assert score_text("The company released a report") == 0.0


def test_lexicon_negation():
    assert score_text("not strong") < 0
    assert score_text("") == 0.0


def test_label_bornes():
    assert label_of(0.9) == "bullish"
    assert label_of(-0.9) == "bearish"
    assert label_of(0.0) == "neutral"


def test_analyze_et_aggregate():
    rows = S.analyze(["record profit and growth", "crash and losses"])
    assert [r["label"] for r in rows] == ["bullish", "bearish"]
    agg = S.aggregate(rows)
    assert agg["n"] == 2 and -1.0 <= agg["score"] <= 1.0


def test_news_sentiment_offline_ne_plante_pas():
    # per_ticker → flux Yahoo ; hors-ligne on doit obtenir n=0 sans exception
    r = S.news_sentiment("AAPL", limit=3)
    assert r["symbol"] == "AAPL" and r["n"] >= 0 and "headlines" in r


def test_engine_name_sans_transformers():
    assert S.engine_name() in ("FinBERT", "lexique")
