"""Score quotidien des actifs les plus cités dans les comptes X déjà suivis.

Ce n'est PAS « les 20 plus recherchés » ni « le plus gros volume de X ». Le dépôt
ne reçoit pas ces deux mesures : l'API gratuite ne les donne pas. Ici, le rang
est le nombre de messages des comptes ingérés qui ne parlent que de cet actif.

Un texte sans mot de sentiment ne vote pas. Il ne devient pas neutre : neutre,
c'est un avis mesuré qui ne penche pas. Zéro message directionnel → `n/d`.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from packages.sentiment.lexicon import label_of, score_detail
from packages.social.modele import Publication

TOP = 20
SOURCE = "comptes suivis : mentions, pas le volume ni la recherche X"
CRYPTOS = frozenset({
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BNB", "AVAX", "DOT",
    "LINK", "MATIC", "SHIB", "TON", "TRX", "NEAR", "APT", "SUI", "PEPE",
})
_OUTILS = frozenset({"USD", "USDT", "USDC", "THE", "FOR", "AND", "ETF", "API"})

_DDL = """
CREATE TABLE IF NOT EXISTS sentiment_jour (
    jour TEXT NOT NULL, ticker TEXT NOT NULL, classe TEXT NOT NULL,
    mentions INTEGER NOT NULL, mentions_scorees INTEGER NOT NULL,
    score REAL, label TEXT NOT NULL,
    n_bullish INTEGER NOT NULL, n_bearish INTEGER NOT NULL,
    n_neutral INTEGER NOT NULL, source TEXT NOT NULL,
    PRIMARY KEY (jour, ticker)
);
"""


def assurer(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def jour_de(ts: datetime) -> str:
    d = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).date().isoformat()


def retenir(ticker: str) -> bool:
    """Crypto connue, ou ticker d'action US (1 à 5 lettres). Le reste sort."""
    t = ticker.upper()
    if t in CRYPTOS:
        return True
    if t in _OUTILS or not t.isalpha():
        return False
    return 1 <= len(t) <= 5


def _scores(posts: list[Publication]) -> list[float]:
    out = []
    for p in posts:
        detail = score_detail(p.texte)
        if detail["n_terms"]:
            out.append(float(detail["score"]))
    return out


def _ligne(ticker: str, posts: list[Publication], jour: str) -> dict:
    scores = _scores(posts)
    if not scores:
        score, label = None, "n/d"
        comptes = {"bullish": 0, "bearish": 0, "neutral": 0}
    else:
        score = round(sum(scores) / len(scores), 4)
        label = label_of(score)
        comptes = {k: sum(1 for s in scores if label_of(s) == k)
                   for k in ("bullish", "bearish", "neutral")}
    return {
        "jour": jour, "ticker": ticker,
        "classe": "crypto" if ticker in CRYPTOS else "action_us",
        "mentions": len(posts), "mentions_scorees": len(scores),
        "score": score, "label": label,
        "n_bullish": comptes["bullish"], "n_bearish": comptes["bearish"],
        "n_neutral": comptes["neutral"], "source": SOURCE,
    }


def agreger(publications: list[Publication], jour: str) -> list[dict]:
    """Au plus 20 lignes, les plus citées ce jour-là. Moins s'il y en a moins."""
    seaux: dict[str, list[Publication]] = {}
    for p in publications:
        if not p.ticker or jour_de(p.ts) != jour or not retenir(p.ticker):
            continue
        seaux.setdefault(p.ticker.upper(), []).append(p)
    lignes = [_ligne(t, ps, jour) for t, ps in seaux.items()]
    lignes.sort(key=lambda r: (-r["mentions"], r["ticker"]))
    return lignes[:TOP]


def enregistrer(conn: sqlite3.Connection, publications: list[Publication],
                jour: str) -> int:
    """Réécrit le jour. Idempotent : un second passage ne duplique pas."""
    assurer(conn)
    lignes = agreger(publications, jour)
    conn.execute("DELETE FROM sentiment_jour WHERE jour = ?", (jour,))
    conn.executemany(
        "INSERT INTO sentiment_jour (jour,ticker,classe,mentions,mentions_scorees,"
        "score,label,n_bullish,n_bearish,n_neutral,source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(r["jour"], r["ticker"], r["classe"], r["mentions"], r["mentions_scorees"],
          r["score"], r["label"], r["n_bullish"], r["n_bearish"], r["n_neutral"],
          r["source"]) for r in lignes])
    conn.commit()
    return len(lignes)


def pour_ml(conn: sqlite3.Connection, ticker: str, jour: str) -> dict:
    """Pour le ML : inconnu reste inconnu, jamais un score 0 « neutre »."""
    assurer(conn)
    row = conn.execute(
        "SELECT score, label, mentions FROM sentiment_jour "
        "WHERE jour = ? AND ticker = ?",
        (jour, ticker.upper())).fetchone()
    if row is None or row[1] == "n/d":
        return {"connu": False, "score": None, "label": "n/d",
                "mentions": 0 if row is None else int(row[2])}
    return {"connu": True, "score": row[0], "label": row[1], "mentions": int(row[2])}
