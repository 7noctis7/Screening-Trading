"""P1-4 — ingestion AJUSTÉE : détection de couture post-split (sans réseau).

Un split passé APRÈS le dernier ingest change rétroactivement les closes ajustés →
`_split_drift` doit le voir sur le chevauchement (sinon la série colle deux
référentiels d'ajustement = momentum faux).
"""
from __future__ import annotations

import sqlite3

from scripts.ingest_prices import _split_drift

_ROW = "INSERT INTO prices VALUES(?,?,?,?,?,?,?,?)"
_DDL = ("CREATE TABLE prices(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
        "close REAL, adj_close REAL, volume REAL, PRIMARY KEY(symbol, date))")


def _conn(closes: dict[str, float]) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.execute(_DDL)
    for d, px in closes.items():
        c.execute(_ROW, ("NVDA", d, px, px, px, px, px, 1e6))
    return c


def _fresh(closes: dict[str, float]) -> list[tuple]:
    return [("NVDA", d, px, px, px, px, px, 1e6) for d, px in closes.items()]


def test_no_drift_when_no_split():
    c = _conn({"2026-07-01": 100.0, "2026-07-02": 101.0})
    rows = _fresh({"2026-07-01": 100.0, "2026-07-02": 101.0, "2026-07-03": 102.0})
    assert _split_drift(c, "NVDA", rows) is False


def test_drift_detected_after_split():
    # split 10:1 depuis le dernier ingest → les closes ajustés frais valent ~1/10 des stockés
    c = _conn({"2026-07-01": 1000.0, "2026-07-02": 1010.0})
    rows = _fresh({"2026-07-01": 100.0, "2026-07-02": 101.0, "2026-07-03": 102.0})
    assert _split_drift(c, "NVDA", rows) is True


def test_small_noise_within_tolerance():
    # bruit d'arrondi Yahoo (<0,5 %) ≠ split → pas de re-backfill inutile
    c = _conn({"2026-07-01": 100.00})
    rows = _fresh({"2026-07-01": 100.30})
    assert _split_drift(c, "NVDA", rows) is False


def test_new_dates_only_no_false_positive():
    c = _conn({"2026-07-01": 100.0})
    rows = _fresh({"2026-07-02": 250.0})              # pas de chevauchement → pas de verdict
    assert _split_drift(c, "NVDA", rows) is False
