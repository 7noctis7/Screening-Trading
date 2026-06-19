"""Suivi de l'equity RÉELLE des comptes (Alpaca/Bitmart) dans le temps → courbes & KPI réels.

Bitmart spot n'expose pas d'historique de valeur de compte ; Alpaca oui (portfolio history). Pour
être broker-agnostique, on enregistre un point/jour de l'equity réelle de chaque compte à chaque
build du snapshot → l'historique réel se constitue (et persiste). stdlib pure, gitignoré (.cache).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_F = Path(__file__).resolve().parents[2] / ".cache" / "equity_history.json"


def _load() -> list[dict]:
    try:
        return json.loads(_F.read_text()) if _F.exists() else []
    except Exception:  # noqa: BLE001
        return []


def record(equities: dict[str, float], today: str | None = None) -> None:
    """Enregistre l'equity réelle du jour par broker (un seul point par date)."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    hist = [h for h in _load() if h.get("date") != today]
    hist.append({"date": today, **{k: round(float(v), 2) for k, v in equities.items()}})
    try:
        _F.parent.mkdir(parents=True, exist_ok=True)
        _F.write_text(json.dumps(hist[-1500:]))
    except Exception:  # noqa: BLE001
        pass


def series(broker: str) -> list[dict]:
    """Courbe {t, v} de l'equity réelle d'un broker (points enregistrés, valeur > 0)."""
    return [{"t": h["date"], "v": h[broker]} for h in _load()
            if broker in h and (h.get(broker) or 0) > 0]
