"""OverlayStore — pont MCP → API/front. Persistance JSON locale, écriture ATOMIQUE.

Le serveur MCP (appelé par l'agent IA) ÉCRIT les overlays ; l'API FastAPI les LIT pour le front
(lightweight-charts). Fichier sous `.cache/` (gitignored, jamais commité). Verrou inter-thread +
`os.replace` atomique pour éviter les lectures partielles. Tolérant : fichier absent/corrompu → {}.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from packages.mcp_tradingview.models import (
    BlackoutZone,
    ChartMarker,
    Overlay,
    RiskBand,
)

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / ".cache" / "tv_overlays.json"
_LOCK = threading.RLock()


class OverlayStore:
    """Lecture/écriture des overlays par ticker (dict ticker → Overlay)."""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path) if path else _DEFAULT_PATH

    # --- bas niveau ---------------------------------------------------------
    def _read_raw(self) -> dict:
        try:
            with self.path.open(encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _write_raw(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.path)                     # atomique → pas de lecture partielle
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # --- API publique -------------------------------------------------------
    def get(self, ticker: str) -> dict:
        """Overlay d'un ticker (dict prêt pour le front) ou structure vide si absent."""
        key = str(ticker).strip().upper()
        with _LOCK:
            raw = self._read_raw()
        return raw.get(key) or {"ticker": key, "markers": [], "bands": [], "blackouts": []}

    def all(self) -> dict:
        with _LOCK:
            return self._read_raw()

    def set_overlay(self, overlay: Overlay) -> dict:
        """Remplace COMPLÈTEMENT l'overlay d'un ticker (validé)."""
        ov = overlay.validate()
        with _LOCK:
            raw = self._read_raw()
            raw[ov.ticker] = ov.to_dict()
            self._write_raw(raw)
        return raw[ov.ticker]

    def set_markers(self, ticker: str, markers: list[ChartMarker], source: str = "mcp") -> dict:
        ov = Overlay(ticker=ticker, markers=markers, source=source)
        ov.validate()
        with _LOCK:
            raw = self._read_raw()
            cur = raw.get(ov.ticker, {})
            cur.update({"ticker": ov.ticker, "source": source, "as_of": ov.as_of,
                        "markers": [m.to_dict() for m in markers]})
            cur.setdefault("bands", []); cur.setdefault("blackouts", [])
            raw[ov.ticker] = cur
            self._write_raw(raw)
        return raw[ov.ticker]

    def set_bands(self, ticker: str, bands: list[RiskBand], source: str = "mcp") -> dict:
        ov = Overlay(ticker=ticker, bands=bands, source=source)
        ov.validate()
        with _LOCK:
            raw = self._read_raw()
            cur = raw.get(ov.ticker, {})
            cur.update({"ticker": ov.ticker, "source": source, "as_of": ov.as_of,
                        "bands": [b.to_dict() for b in ov.bands]})
            cur.setdefault("markers", []); cur.setdefault("blackouts", [])
            raw[ov.ticker] = cur
            self._write_raw(raw)
        return raw[ov.ticker]

    def set_blackouts(self, ticker: str, blackouts: list[BlackoutZone], source: str = "mcp") -> dict:
        ov = Overlay(ticker=ticker, blackouts=blackouts, source=source)
        ov.validate()
        with _LOCK:
            raw = self._read_raw()
            cur = raw.get(ov.ticker, {})
            cur.update({"ticker": ov.ticker, "source": source, "as_of": ov.as_of,
                        "blackouts": [z.to_dict() for z in blackouts]})
            cur.setdefault("markers", []); cur.setdefault("bands", [])
            raw[ov.ticker] = cur
            self._write_raw(raw)
        return raw[ov.ticker]

    def clear(self, ticker: str | None = None) -> None:
        with _LOCK:
            if ticker is None:
                self._write_raw({})
                return
            raw = self._read_raw()
            raw.pop(str(ticker).strip().upper(), None)
            self._write_raw(raw)
