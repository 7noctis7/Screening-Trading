"""Moteur de lecture VECTORISÉ des prix — DuckDB + Polars, repli SQLite (stdlib).

Objectif latence (Citadel) : requêtes colonne vectorisées pour alimenter screener + matrice de
covariance ERC en quelques ms, au lieu de lectures SQLite ligne-à-ligne. Les libs lourdes sont
OPTIONNELLES : si `duckdb`/`polars` absents → repli SQLite renvoyant des lignes (dicts), et
`covariance_matrix` reste pur-numpy. Aucune dépendance dure ; ne crashe jamais le pipeline."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def available() -> dict[str, bool]:
    """Disponibilité des accélérateurs (pour log/diagnostic)."""
    def _has(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:  # noqa: BLE001
            return False
    return {"duckdb": _has("duckdb"), "polars": _has("polars"), "numpy": _has("numpy")}


def _resolve_db(db: str | Path) -> Path:
    p = Path(db)
    if p.exists():
        return p
    cand = _ROOT / "data" / (str(db) if str(db).endswith(".db") else f"{db}.db")
    return cand


def _detect_bars_table(con: sqlite3.Connection) -> tuple[str, dict[str, str]]:
    """Repère la table de barres + mappe les colonnes (sym/ts/o/h/l/c/v) de façon tolérante."""
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    pref = [t for t in tables if t.lower() in ("bars", "ohlcv", "prices")] or tables
    for t in pref:
        cols = [r[1].lower() for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()]

        def pick(*opts: str) -> str | None:
            return next((c for c in opts if c in cols), None)
        m = {"symbol": pick("symbol", "ticker", "sym"), "ts": pick("ts", "date", "datetime", "time"),
             "open": pick("open", "o"), "high": pick("high", "h"), "low": pick("low", "l"),
             "close": pick("close", "c", "adj_close"), "volume": pick("volume", "v", "vol")}
        if m["symbol"] and m["ts"] and m["close"]:
            return t, m
    raise ValueError("aucune table de barres exploitable (colonnes symbol/ts/close introuvables)")


def read_prices_rows(db: str | Path, symbols: list[str] | None = None,
                     start: str | datetime | None = None, end: str | datetime | None = None,
                     limit: int = 5_000_000) -> list[dict]:
    """Repli SQLite (toujours dispo) : renvoie des lignes normalisées {symbol,ts,open,high,low,close,volume}."""
    path = _resolve_db(db)
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        t, m = _detect_bars_table(con)
        sel = ", ".join(f'"{m[k]}" AS {k}' for k in ("symbol", "ts", "open", "high", "low", "close", "volume") if m.get(k))
        where, params = [], []
        if symbols:
            where.append(f'"{m["symbol"]}" IN ({",".join("?" * len(symbols))})'); params += list(symbols)
        if start:
            where.append(f'"{m["ts"]}" >= ?'); params.append(str(start)[:10])
        if end:
            where.append(f'"{m["ts"]}" <= ?'); params.append(str(end)[:10])
        sql = f'SELECT {sel} FROM "{t}"' + (f' WHERE {" AND ".join(where)}' if where else "") + f' LIMIT {int(limit)}'
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


def read_prices_polars(db: str | Path, symbols: list[str] | None = None,
                       start: str | None = None, end: str | None = None) -> Any:
    """Lecture VECTORISÉE → DataFrame Polars. Utilise DuckDB (zéro-copie Arrow) si dispo, sinon
    construit le DataFrame Polars depuis le repli SQLite. Lève ImportError si Polars absent."""
    try:
        import polars as pl
    except Exception as e:  # noqa: BLE001
        raise ImportError("polars requis : uv pip install -e \".[data]\"") from e
    # chemin rapide DuckDB (scan colonne directement sur le fichier SQLite)
    try:
        import duckdb
        path = _resolve_db(db)
        con = duckdb.connect()
        con.execute("INSTALL sqlite; LOAD sqlite;")
        con.execute(f"ATTACH '{path}' AS src (TYPE sqlite, READ_ONLY);")
        tbl = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        # réutilise la détection de colonnes
        scon = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            t, m = _detect_bars_table(scon)
        finally:
            scon.close()
        sel = ", ".join(f'"{m[k]}" AS {k}' for k in ("symbol", "ts", "open", "high", "low", "close", "volume") if m.get(k))
        q = f'SELECT {sel} FROM src."{t}"'
        conds = []
        if symbols:
            lst = ",".join("'" + s.replace("'", "''") + "'" for s in symbols)
            conds.append(f'"{m["symbol"]}" IN ({lst})')
        if start:
            conds.append(f'"{m["ts"]}" >= \'{start}\'')
        if end:
            conds.append(f'"{m["ts"]}" <= \'{end}\'')
        if conds:
            q += " WHERE " + " AND ".join(conds)
        return pl.from_arrow(con.execute(q).fetch_arrow_table())
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 — DuckDB indispo/illisible → repli SQLite→Polars
        pass
    return pl.DataFrame(read_prices_rows(db, symbols, start, end))


def covariance_matrix(returns_by_symbol: dict[str, list[float]], annualize: int = 252) -> tuple[list[str], Any]:
    """Matrice de covariance ANNUALISÉE (numpy vectorisé) sur les rendements alignés → entrée ERC.
    Aligne les séries sur la longueur minimale commune. Renvoie (symboles, matrice np.ndarray)."""
    import numpy as np
    syms = [s for s, r in returns_by_symbol.items() if r and len(r) >= 2]
    if len(syms) < 2:
        return syms, np.zeros((len(syms), len(syms)))
    m = min(len(returns_by_symbol[s]) for s in syms)
    mat = np.array([returns_by_symbol[s][-m:] for s in syms], dtype=float)
    cov = np.cov(mat) * annualize
    return syms, cov
