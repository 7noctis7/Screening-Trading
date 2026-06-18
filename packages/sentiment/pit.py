"""Point-in-time des news (Griffin/López de Prado : zéro look-ahead, zéro data leakage).

Une news publiée à 16:01 ne peut PAS influencer une décision datée du close de 16:00. On n'autorise
l'usage d'une news que si elle est publiée AVANT le timestamp de décision, moins un embargo (le temps
que l'info soit exploitable sans devancer les HFT). On modélise aussi l'**alpha decay** : un signal
news perd sa valeur exponentiellement avec le temps écoulé.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta


def usable_at(news_ts: datetime, decision_ts: datetime, embargo_minutes: float = 1.0) -> bool:
    """True si la news est exploitable à `decision_ts` (publiée + embargo ≤ décision)."""
    if news_ts is None or decision_ts is None:
        return False
    return news_ts + timedelta(minutes=embargo_minutes) <= decision_ts


def filter_pit(news: list[dict], decision_ts: datetime, ts_key: str = "ts",
               embargo_minutes: float = 1.0) -> list[dict]:
    """Ne garde que les news antérieures (anti-fuite). `news[i][ts_key]` = datetime de publication."""
    return [n for n in news if usable_at(n.get(ts_key), decision_ts, embargo_minutes)]


def alpha_decay_weight(news_ts: datetime, decision_ts: datetime, half_life_min: float = 30.0) -> float:
    """Poids ∈ (0,1] décroissant : w = 0.5^(Δt / demi-vie). Le signal news s'évapore vite face au HFT.

    half_life_min ≈ 30 min : une surprise est largement arbitrée en moins d'une heure.
    """
    if news_ts is None or decision_ts is None:
        return 0.0
    dt_min = max(0.0, (decision_ts - news_ts).total_seconds() / 60.0)
    return float(0.5 ** (dt_min / max(1e-6, half_life_min)))
