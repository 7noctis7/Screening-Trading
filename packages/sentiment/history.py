"""Historique du sentiment → Δsentiment (révision). En EOD, la VARIATION de sentiment sur quelques
jours prédit mieux que le niveau absolu (le niveau est déjà dans le prix). On persiste le sentiment
quotidien (un point par date) et on calcule l'écart au sentiment moyen récent. stdlib pure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "sentiment_history.json"


def _load() -> list[dict]:
    try:
        return json.loads(_F.read_text()) if _F.exists() else []
    except Exception:  # noqa: BLE001
        return []


def record_and_delta(scores: dict[str, float], window: int = 20,
                     today: str | None = None) -> dict:
    """Enregistre les scores du jour et renvoie le Δsentiment par actif (vs moyenne des `window`
    derniers jours, hors aujourd'hui). Au premier appel, Δ = 0 (pas d'historique).

    Renvoie `{by_symbol: {sym: delta}, mood_delta: float, history_days: int}`.
    """
    today = today or datetime.now(timezone.utc).date().isoformat()
    hist = [h for h in _load() if h.get("date") != today]      # dédoublonne la date du jour
    prior = hist[-window:]
    by_symbol: dict[str, float] = {}
    for sym, sc in scores.items():
        past = [h["scores"][sym] for h in prior if sym in h.get("scores", {})]
        base = sum(past) / len(past) if past else sc
        by_symbol[sym] = round(sc - base, 4)
    cur_mood = sum(scores.values()) / len(scores) if scores else 0.0
    past_moods = [sum(h["scores"].values()) / len(h["scores"])
                  for h in prior if h.get("scores")]
    mood_base = sum(past_moods) / len(past_moods) if past_moods else cur_mood
    # persiste (best effort) — alimenté quotidiennement par le cron
    try:
        hist.append({"date": today, "scores": {k: round(v, 4) for k, v in scores.items()}})
        _F.parent.mkdir(parents=True, exist_ok=True)
        _F.write_text(json.dumps(hist[-120:]))                 # garde ~4 mois
    except Exception:  # noqa: BLE001
        pass
    return {"by_symbol": by_symbol, "mood_delta": round(cur_mood - mood_base, 4),
            "history_days": len(prior)}
