"""Pont **FinBERT** (HuggingFace) optionnel — sentiment financier de qualité si `transformers`
+ un modèle local sont présents. Sinon on tombe proprement sur le lexique (cf. `__init__`).

Modèles recommandés (gratuits) : `ProsusAI/finbert`, `yiyanghkust/finbert-tone`.
Import 100 % paresseux → aucun coût ni dépendance tant que ce n'est pas explicitement utilisé,
donc testable hors-ligne sans `transformers`/`torch`.
"""

from __future__ import annotations

import os
from functools import lru_cache

_MODEL = os.environ.get("FINBERT_MODEL", "ProsusAI/finbert")
# Mappe les labels FinBERT → score signé
_MAP = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


def finbert_available() -> bool:
    """True si `transformers` est importable (le modèle est chargé à la 1re utilisation)."""
    try:
        import transformers  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=1)
def _pipe():
    from transformers import pipeline  # import local
    return pipeline("sentiment-analysis", model=_MODEL, top_k=None)


def score_texts(texts: list[str]) -> list[float]:
    """Score ∈ [-1, 1] par texte via FinBERT (espérance signée sur les 3 classes).

    Lève si `transformers`/modèle indisponible : l'appelant gère le repli lexical.
    """
    if not texts:
        return []
    out: list[float] = []
    for res in _pipe()(list(texts)):
        rows = res if isinstance(res, list) else [res]
        out.append(round(sum(_MAP.get(r["label"].lower(), 0.0) * float(r["score"]) for r in rows), 4))
    return out
