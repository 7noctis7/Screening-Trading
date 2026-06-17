"""Sentiment & news financier — moteur unifié, **hors-ligne par défaut**.

Ordre de préférence (dégrade proprement) :
  1. **FinBERT** (HuggingFace) si `transformers` + modèle présents → meilleure qualité ;
  2. sinon **lexique** finance (stdlib, toujours dispo, déterministe).

`analyze()` score des textes ; `news_sentiment()` récupère des titres RSS (gratuit, sans clé)
et les agrège par actif. Aucun réseau requis pour les tests (le lexique suffit).
"""

from __future__ import annotations

from . import finbert, rss
from .lexicon import label_of, score_text


def engine_name() -> str:
    """Nom du moteur réellement utilisé (pour affichage UI)."""
    return "FinBERT" if finbert.finbert_available() else "lexique"


def analyze(texts: list[str]) -> list[dict]:
    """Score une liste de textes → `[{text, score, label}]` (FinBERT si dispo, sinon lexique)."""
    if not texts:
        return []
    if finbert.finbert_available():
        try:
            scores = finbert.score_texts(texts)
        except Exception:  # noqa: BLE001 — modèle absent/échec → repli lexical
            scores = [score_text(t) for t in texts]
    else:
        scores = [score_text(t) for t in texts]
    return [{"text": t, "score": round(s, 4), "label": label_of(s)} for t, s in zip(texts, scores)]


def aggregate(items: list[dict]) -> dict:
    """Agrège des scores `[{score,label,...}]` → `{score, label, n}` (moyenne signée)."""
    if not items:
        return {"score": 0.0, "label": "neutral", "n": 0}
    avg = sum(i["score"] for i in items) / len(items)
    return {"score": round(avg, 4), "label": label_of(avg), "n": len(items)}


def news_sentiment(symbol: str, limit: int = 12, per_ticker: bool = True) -> dict:
    """Sentiment d'un actif à partir de titres RSS Yahoo (gratuit). Hors-ligne → n=0.

    Renvoie `{symbol, score, label, n, headlines:[{title, link, score, label}]}`.
    """
    feeds = [rss.yahoo_feed(symbol)] if per_ticker else None
    heads = rss.fetch_headlines(feeds, limit=limit)
    scored = analyze([h["title"] for h in heads])
    for h, s in zip(heads, scored):
        h.update(score=s["score"], label=s["label"])
    agg = aggregate(scored)
    return {"symbol": symbol, **agg, "headlines": heads[:limit]}
