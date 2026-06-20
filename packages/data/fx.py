"""Taux de change GRATUITS (yfinance) avec cache disque — best-effort, jamais bloquant.

Sert à convertir les états financiers d'un ADR (devise locale, ex. TWD) dans la devise de son cours
(ex. USD) afin que la valorisation (multiples, DCF) soit cohérente. Hors-ligne / paire inconnue →
renvoie None et l'appelant retombe sur le comportement « valorisation masquée »."""

from __future__ import annotations

import json
import time
from pathlib import Path

_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "fx" / "rates.json"
_TTL = 86_400.0     # 24 h : un taux journalier suffit pour une note fondamentale


def _load() -> dict:
    try:
        if _CACHE.exists() and time.time() - _CACHE.stat().st_mtime < _TTL:
            return json.loads(_CACHE.read_text())
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save(d: dict) -> None:
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(d))
    except Exception:  # noqa: BLE001
        pass


def rate(base: str, quote: str = "USD") -> float | None:
    """1 unité de `base` = ? `quote` (ex. rate('TWD','USD') ≈ 0.031). None si indisponible/hors-ligne.
    Identité si base == quote. Cache disque 24 h ; source yfinance `BASEQUOTE=X`."""
    base = (base or "").upper().strip()
    quote = (quote or "USD").upper().strip()
    if not base or not quote or base == quote:
        return 1.0 if base == quote and base else None
    cache = _load()
    key = f"{base}{quote}"
    if key in cache:
        try:
            return float(cache[key])
        except (TypeError, ValueError):
            pass
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{base}{quote}=X").history(period="5d")
        if hist is None or getattr(hist, "empty", True):
            return None
        val = float(hist["Close"].dropna().iloc[-1])
        if val > 0:
            cache[key] = val
            _save(cache)
            return val
    except Exception:  # noqa: BLE001
        return None
    return None
