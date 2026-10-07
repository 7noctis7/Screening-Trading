"""OHLC bruts immuables + ajustement à la lecture (AXE 1, correctif F1).

La table `prices` reste le chemin de production (Yahoo déjà ajusté). Ces deux
tables ne la remplacent pas : on les archive pour qu'un run daté ne réécrive
plus 2015 quand un split tombe aujourd'hui.

`ohlcv_raw` et `corporate_action` sont en INSERT OR IGNORE. Une révision
ultérieure de Yahoo n'écrase pas la première ligne vue.

`kt_quality = INFERRED_LAG` : Yahoo ne donne pas l'heure d'annonce. On date
l'action au jour ex — le marché voit le saut ce jour-là, pas avant.
`F(t | T)` n'utilise qu'une action avec `ex_date > t`, `ex_date <= T` et
`knowledge_time <= T`.
"""

from __future__ import annotations

import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS ohlcv_raw (
  symbol TEXT NOT NULL, date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, volume REAL,
  PRIMARY KEY (symbol, date));
CREATE TABLE IF NOT EXISTS corporate_action (
  symbol TEXT NOT NULL, ex_date TEXT NOT NULL, action_type TEXT NOT NULL,
  ratio REAL, cash_amount REAL, close_veille REAL,
  knowledge_time TEXT NOT NULL, kt_quality TEXT NOT NULL,
  PRIMARY KEY (symbol, ex_date, action_type, knowledge_time));
"""


def assurer(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def inserer_barre(conn: sqlite3.Connection, symbol: str, date: str,
                  o, h, lo, c, volume) -> None:
    """N'écrit que la première version. Un cours déjà là ne bouge pas."""
    conn.execute(
        "INSERT OR IGNORE INTO ohlcv_raw VALUES (?,?,?,?,?,?,?)",
        (symbol, date, o, h, lo, c, volume))


def inserer_action(conn: sqlite3.Connection, symbol: str, ex_date: str,
                   action_type: str, *, ratio: float | None = None,
                   cash_amount: float | None = None,
                   close_veille: float | None = None,
                   knowledge_time: str | None = None,
                   kt_quality: str = "INFERRED_LAG") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO corporate_action VALUES (?,?,?,?,?,?,?,?)",
        (symbol, ex_date, action_type, ratio, cash_amount, close_veille,
         knowledge_time or ex_date, kt_quality))


def _compte(action: dict, date_barre: str, as_of: str) -> bool:
    if action.get("kt_quality") == "UNKNOWN":
        return False
    ex = action["ex_date"]
    kt = str(action.get("knowledge_time") or ex)[:10]
    return date_barre < ex <= as_of and kt <= as_of


def facteur_prix(actions: list[dict], date_barre: str, as_of: str) -> float:
    """Produit des facteurs de split et de dividende cash postérieurs à la barre."""
    f = 1.0
    for a in actions:
        if not _compte(a, date_barre, as_of):
            continue
        if a["action_type"] == "SPLIT" and a.get("ratio") and a["ratio"] > 0:
            f *= 1.0 / float(a["ratio"])
        elif a["action_type"] == "CASH_DIV":
            cash, veille = a.get("cash_amount"), a.get("close_veille")
            if cash and veille and veille > cash > 0:
                f *= 1.0 - float(cash) / float(veille)
    return f


def facteur_volume(actions: list[dict], date_barre: str, as_of: str) -> float:
    """Splits seulement. Un dividende ne change pas le nombre de titres."""
    f = 1.0
    for a in actions:
        if (_compte(a, date_barre, as_of) and a["action_type"] == "SPLIT"
                and a.get("ratio") and a["ratio"] > 0):
            f *= float(a["ratio"])
    return f


def close_ajuste(close: float, actions: list[dict], date_barre: str,
                 as_of: str) -> float:
    return float(close) * facteur_prix(actions, date_barre, as_of)


def _flottant(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _ecrire_serie(conn, symbol: str, df) -> tuple[int, dict[str, float]]:
    n, closes = 0, {}
    for ts, row in df.iterrows():
        date = ts.strftime("%Y-%m-%d")
        c = _flottant(row.get("Close"))
        inserer_barre(conn, symbol, date, _flottant(row.get("Open")),
                      _flottant(row.get("High")), _flottant(row.get("Low")),
                      c, _flottant(row.get("Volume")))
        if c is not None and c > 0:
            closes[date] = c
        n += 1
    return n, closes


def _veille(closes: dict[str, float], ex: str) -> float | None:
    avant = [d for d in closes if d < ex]
    return closes[max(avant)] if avant else None


def _ecrire_actions(conn, symbol: str, splits, divs, closes: dict) -> int:
    n = 0
    if splits is not None:
        for ts, ratio in splits.items():
            r = _flottant(ratio)
            if r and r > 0 and r != 1:
                inserer_action(conn, symbol, ts.strftime("%Y-%m-%d"), "SPLIT",
                               ratio=r)
                n += 1
    if divs is not None:
        for ts, cash in divs.items():
            csh = _flottant(cash)
            ex = ts.strftime("%Y-%m-%d")
            if csh and csh > 0:
                inserer_action(conn, symbol, ex, "CASH_DIV", cash_amount=csh,
                               close_veille=_veille(closes, ex))
                n += 1
    return n


def archiver_yahoo(conn: sqlite3.Connection, symbol: str, ysym: str | None,
                   start: str, end: str) -> tuple[int, int] | None:
    """Archive le brut Yahoo. `None` = échec (la table `prices` n'est pas touchée)."""
    try:
        import yfinance as yf
        t = yf.Ticker(ysym or symbol)
        df = t.history(start=start, end=end, auto_adjust=False, actions=False)
        if df is None or df.empty:
            return 0, 0
        assurer(conn)
        n, closes = _ecrire_serie(conn, symbol, df)
        n_act = _ecrire_actions(conn, symbol, t.splits, t.dividends, closes)
        conn.commit()
        return n, n_act
    except Exception:  # noqa: BLE001 — l'archive ne casse pas l'ingest ajusté
        return None
