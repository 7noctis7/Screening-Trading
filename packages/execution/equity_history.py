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


def courbe_comparable(hist: list[dict], cles: set[str]) -> list[float]:
    """Totaux des SEULES clés `cles`, sur les points qui les portent toutes (QML-024).

    Un point qui n'a pas tout le périmètre est écarté, jamais compté pour zéro : sinon un
    courtier muet un jour ressemble à une perte, et un solde de bac à sable à un sommet."""
    out = []
    for h in hist:
        if all(isinstance(h.get(k), (int, float)) and h[k] > 0 for k in cles):
            out.append(float(sum(h[k] for k in cles)))
    return out


def record(equities: dict[str, float], today: str | None = None) -> None:
    """Enregistre l'equity réelle du jour par broker (un seul point par date).

    Sans equity Alpaca lisible, RIEN n'est écrit (QML-024) : le compte principal manquant, le
    point ne mesurerait qu'une fraction du portefeuille et passerait pour une chute."""
    if not (equities.get("alpaca") or 0) > 0:
        return
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
