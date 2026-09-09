"""Historique du sentiment → Δsentiment (révision). En EOD, la VARIATION de sentiment sur quelques
jours prédit mieux que le niveau absolu (le niveau est déjà dans le prix). On persiste le sentiment
quotidien (un point par date) et on calcule l'écart au sentiment moyen récent. stdlib pure.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "sentiment_history.json"


def _load() -> list[dict]:
    try:
        return json.loads(_F.read_text()) if _F.exists() else []
    except Exception:  # noqa: BLE001
        return []


def delta(scores: dict[str, float], window: int = 20,
          today: str | None = None) -> dict:
    """Δsentiment par actif **SANS RIEN ÉCRIRE** — le calcul seul.

    Séparé de `record_and_delta` parce que deux appelants ont des droits différents :
    le snapshot du robot tourne une fois par jour et DOIT alimenter l'historique ;
    l'analyse d'un portefeuille fourni par l'utilisateur est read-only par contrat
    (`/api/portfolio/*` : « aucune persistance »). Un portefeuille de passage qui
    écrirait dans l'historique polluerait la référence du robot avec des symboles
    qu'il ne détient pas — et le Δ du lendemain serait faussé pour TOUT LE MONDE.
    """
    today = today or datetime.now(UTC).date().isoformat()
    prior = [h for h in _load() if h.get("date") != today][-window:]
    by_symbol: dict[str, float] = {}
    avec_historique: list[str] = []
    for sym, sc in scores.items():
        past = [h["scores"][sym] for h in prior if sym in h.get("scores", {})]
        base = sum(past) / len(past) if past else sc
        by_symbol[sym] = round(sc - base, 4)
        if past:
            avec_historique.append(sym)
    cur_mood = sum(scores.values()) / len(scores) if scores else 0.0
    past_moods = [sum(h["scores"].values()) / len(h["scores"])
                  for h in prior if h.get("scores")]
    mood_base = sum(past_moods) / len(past_moods) if past_moods else cur_mood
    # ATTENTION `mood_delta` : il compare la moyenne des scores REÇUS à la moyenne des
    # scores HISTORISÉS, qui ne portent pas forcément sur le même panier. C'est juste
    # pour le snapshot du robot (même univers d'un jour à l'autre) et FAUX pour un
    # portefeuille tiers : voir `portefeuille.analyse`, qui repondère `by_symbol` —
    # chaque actif y est comparé à SON propre passé. `avec_historique` dit lesquels en
    # ont un ; un Δ de 0 sans historique n'est pas « stable », il est « inconnu ».
    return {"by_symbol": by_symbol, "mood_delta": round(cur_mood - mood_base, 4),
            "history_days": len(prior), "avec_historique": avec_historique}


def record_and_delta(scores: dict[str, float], window: int = 20,
                     today: str | None = None) -> dict:
    """Enregistre les scores du jour et renvoie le Δsentiment par actif (vs moyenne
    des `window` derniers jours, hors aujourd'hui). Au premier appel, Δ = 0.

    Renvoie `{by_symbol: {sym: delta}, mood_delta: float, history_days: int}`.
    """
    today = today or datetime.now(UTC).date().isoformat()
    mesure = delta(scores, window=window, today=today)
    try:                                                       # persiste (best effort)
        hist = [h for h in _load() if h.get("date") != today]
        hist.append({"date": today,
                     "scores": {k: round(v, 4) for k, v in scores.items()}})
        _F.parent.mkdir(parents=True, exist_ok=True)
        _F.write_text(json.dumps(hist[-120:]))                 # garde ~4 mois
    except Exception:  # noqa: BLE001
        pass
    return mesure
