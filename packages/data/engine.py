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


def ledoit_wolf_shrinkage(mat: Any) -> tuple[Any, float]:
    """Shrinkage analytique de Ledoit-Wolf (2004) vers une cible à corrélation constante — pur numpy.

    La covariance empirique est instable quand n_actifs ≈ n_observations (cas top-30) : l'ERC y
    surréagit (turnover, poids extrêmes). On régularise S vers F (même variances, corrélation moyenne)
    avec une intensité δ* optimale estimée sur les données. `mat` : n×T (lignes = actifs).
    Renvoie (Σ régularisée n×n, δ utilisé ∈ [0,1])."""
    import numpy as np
    A = np.asarray(mat, dtype=float)
    n = A.shape[0]
    if n < 2 or A.shape[1] < 2:
        return (np.cov(A) if A.size else np.zeros((n, n))), 0.0
    X = A.T                                                   # (T, n) : observations en lignes
    t = X.shape[0]
    X = X - X.mean(axis=0, keepdims=True)
    S = (X.T @ X) / t                                         # cov empirique (diviseur T)
    var = np.diag(S)
    std = np.sqrt(np.clip(var, 1e-300, None))
    outer = np.outer(std, std)
    r_bar = (float((S / outer).sum()) - n) / (n * (n - 1))   # corrélation moyenne hors diagonale
    F = r_bar * outer                                        # cible : corrélation constante
    np.fill_diagonal(F, var)
    # π̂ : somme des variances asymptotiques des éléments de S
    Y = X ** 2
    pi_mat = (Y.T @ Y) / t - S ** 2
    pi = float(pi_mat.sum())
    # ρ̂ : termes diagonaux + contribution des termes croisés (modèle corrélation constante)
    term = (X ** 3).T @ X / t - var[:, None] * S            # θ_ij
    np.fill_diagonal(term, 0.0)
    rho = float(np.diag(pi_mat).sum()) + r_bar * float(((outer / outer.T) * term).sum())
    # γ̂ : distance de Frobenius² entre cible et empirique
    gamma = float(((F - S) ** 2).sum())
    kappa = (pi - rho) / gamma if gamma > 0 else 0.0
    delta = max(0.0, min(1.0, kappa / t))                    # intensité optimale bornée [0,1]
    sigma = delta * F + (1.0 - delta) * S
    return sigma, delta


# Cache de covariance incrémental : clé = (symboles ordonnés, dernière obs de chaque série, params).
# Le snapshot recalcule l'ERC sur plusieurs sleeves (preset/crypto) avec les MÊMES rendements →
# on évite les recalculs identiques. Mémoire bornée (LRU manuel), pur stdlib, jamais bloquant.
# Persistance disque optionnelle (.cache/cov/) : survit aux redémarrages API / runs cron → le
# premier build du matin réutilise la covariance de la veille pour les séries inchangées.
import hashlib

_COV_CACHE: dict[Any, tuple[list[str], Any]] = {}
_COV_CACHE_MAX = 64
_COV_DISK_DIR = _ROOT / ".cache" / "cov"


def _cov_cache_key(returns_by_symbol: dict[str, list[float]], annualize: int, shrink: bool) -> Any:
    parts = []
    for s in sorted(returns_by_symbol):
        r = returns_by_symbol[s]
        if r and len(r) >= 2:
            parts.append((s, len(r), round(float(r[-1]), 10), round(float(r[0]), 10)))
    return (tuple(parts), annualize, shrink)


def _cov_disk_path(key: Any) -> Path:
    h = hashlib.sha1(repr(key).encode()).hexdigest()[:24]    # signature compacte, stable
    return _COV_DISK_DIR / f"{h}.npz"


# Compteurs de hit-rate du cache (mesure réelle du gain en prod ; signale une signature instable
# si les misses explosent). Pur stdlib, jamais bloquant.
_COV_STATS: dict[str, int] = {"hits": 0, "disk_hits": 0, "misses": 0}


def cov_cache_stats() -> dict[str, Any]:
    """Statistiques du cache de covariance : hits mémoire, hits disque, misses + taux global."""
    s = dict(_COV_STATS)
    total = s["hits"] + s["disk_hits"] + s["misses"]
    s["hit_rate"] = round((s["hits"] + s["disk_hits"]) / total, 4) if total else 0.0
    return s


def purge_cov_disk_cache(max_age_days: float = 14.0) -> int:
    """Purge les covariances persistées plus vieilles que `max_age_days` (les nouvelles barres
    quotidiennes rendent les anciennes signatures obsolètes → évite l'accumulation infinie).
    Appelée une fois par build. Best-effort, ne lève jamais. Renvoie le nombre de fichiers purgés."""
    try:
        import os
        import time
        if not _COV_DISK_DIR.exists():
            return 0
        cutoff = time.time() - max_age_days * 86400.0
        n = 0
        for p in _COV_DISK_DIR.glob("*.npz"):
            try:
                if p.stat().st_mtime < cutoff:
                    os.remove(p)
                    n += 1
            except OSError:
                continue
        return n
    except Exception:  # noqa: BLE001 — purge non critique
        return 0


def _cov_disk_load(key: Any) -> tuple[list[str], Any] | None:
    """Charge une covariance persistée (best-effort). Jamais bloquant."""
    try:
        import numpy as np
        p = _cov_disk_path(key)
        if not p.exists():
            return None
        with np.load(p, allow_pickle=False) as z:
            return list(z["syms"]), z["cov"]
    except Exception:  # noqa: BLE001 — fichier corrompu/illisible → on recalcule
        return None


def _cov_disk_save(key: Any, syms: list[str], cov: Any) -> None:
    """Persiste une covariance (best-effort, écriture atomique). Jamais bloquant."""
    try:
        import os
        import numpy as np
        _COV_DISK_DIR.mkdir(parents=True, exist_ok=True)
        p = _cov_disk_path(key)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, syms=np.asarray(syms, dtype=object).astype(str), cov=np.asarray(cov))
        os.replace(tmp, p)
    except Exception:  # noqa: BLE001 — disque plein/lecture seule → on continue sans persister
        pass


def covariance_diagnostics(cov_raw: Any, cov_used: Any | None = None, delta: float = 0.0) -> dict:
    """Diagnostic de qualité du risque (visibilité institutionnelle) : nombre de condition de la
    matrice de covariance avant/après shrinkage et δ retenu. Pur numpy, ne lève jamais."""
    out: dict[str, Any] = {"delta": round(float(delta), 4)}
    try:
        import numpy as np

        def _cond(C: Any) -> float | None:
            C = np.asarray(C, dtype=float)
            if C.ndim != 2 or C.shape[0] < 2:
                return None
            ev = np.linalg.eigvalsh((C + C.T) / 2.0)
            lo = float(ev.min())
            hi = float(ev.max())
            return round(hi / lo, 1) if lo > 1e-15 else float("inf")
        out["cond_raw"] = _cond(cov_raw)
        out["cond_used"] = _cond(cov_used if cov_used is not None else cov_raw)
        out["n_assets"] = int(np.asarray(cov_raw).shape[0]) if np.asarray(cov_raw).ndim == 2 else 0
    except Exception:  # noqa: BLE001
        pass
    return out


def covariance_matrix(returns_by_symbol: dict[str, list[float]], annualize: int = 252,
                      shrink: bool = False, cache: bool = True) -> tuple[list[str], Any]:
    """Matrice de covariance ANNUALISÉE (numpy vectorisé) sur les rendements alignés → entrée ERC.

    Aligne les séries sur la longueur minimale commune. `shrink=True` applique Ledoit-Wolf
    (covariance stabilisée, recommandé quand n_actifs ≈ n_obs). `cache=True` mémorise le résultat
    par signature (symboles + bornes de série) pour éviter les recalculs identiques dans un build.
    Renvoie (symboles, matrice np.ndarray)."""
    import os

    import numpy as np
    syms = [s for s, r in returns_by_symbol.items() if r and len(r) >= 2]
    if len(syms) < 2:
        return syms, np.zeros((len(syms), len(syms)))
    key = _cov_cache_key(returns_by_symbol, annualize, shrink) if cache else None
    use_disk = cache and os.environ.get("QUANT_COV_DISK_CACHE", "1").lower() not in ("0", "false", "no")
    if key is not None and key in _COV_CACHE:
        _COV_STATS["hits"] += 1
        return _COV_CACHE[key]
    if key is not None and use_disk:                         # cold-start : relit la veille si inchangé
        hit = _cov_disk_load(key)
        if hit is not None:
            _COV_CACHE[key] = hit
            _COV_STATS["disk_hits"] += 1
            return hit
    if cache:
        _COV_STATS["misses"] += 1
    m = min(len(returns_by_symbol[s]) for s in syms)
    mat = np.array([returns_by_symbol[s][-m:] for s in syms], dtype=float)
    if shrink:
        cov, _delta = ledoit_wolf_shrinkage(mat)
        cov = cov * annualize
    else:
        cov = np.cov(mat) * annualize
    if key is not None:
        if len(_COV_CACHE) >= _COV_CACHE_MAX:
            _COV_CACHE.pop(next(iter(_COV_CACHE)))           # éviction FIFO simple (mémoire bornée)
        _COV_CACHE[key] = (syms, cov)
        if use_disk:
            _cov_disk_save(key, syms, cov)
    return syms, cov
