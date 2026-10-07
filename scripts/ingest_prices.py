"""Ingestion de prix RÉELS → base SQLite locale (append quotidien idempotent).

Alimente data/market.db (table `prices`, format long) à partir de :
  1) yfinance (par défaut, gratuit) ;
  2) FMP en repli si FMP_API_KEY est défini.

Idempotent : clé primaire (symbol, date) + INSERT OR IGNORE → relancer chaque jour n'ajoute
que les nouvelles barres (la barre du jour vient s'empiler sur l'historique de CHAQUE actif).
Le snapshot/API lisent ensuite cette base via QUANT_PRICE_DB (cf. packages/data/providers/db_provider.py).

Exemples :
  python scripts/ingest_prices.py --since 2015-01-01           # backfill complet (univers)
  python scripts/ingest_prices.py --symbols AAPL NVDA PLTR     # quelques tickers
  python scripts/ingest_prices.py --daily                      # mise à jour incrémentale du jour
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data" / "market.db"
_DDL = """CREATE TABLE IF NOT EXISTS prices(
  symbol TEXT NOT NULL, date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
  PRIMARY KEY(symbol, date));
CREATE INDEX IF NOT EXISTS ix_prices_symbol ON prices(symbol);"""


def _universe() -> list[tuple[str, str]]:
    from apps.api.snapshot import _seed_universe
    return [(m["symbol"], m.get("asset_class", "equity")) for m in _seed_universe()]


def _ysym(sym: str, ac: str) -> str | None:
    """Ticker au format Yahoo (None = à ignorer ici). Crypto → géré par ingest_crypto (crypto.db)."""
    from apps.api.snapshot import _yahoo_aliases
    if ac == "crypto":
        return None                                  # crypto = base dédiée (make ingest-crypto)
    if ac in ("equity", "etf", ""):
        return sym
    for a in _yahoo_aliases(sym, ac):                # forex/indice/commodité → alias Yahoo (=X, ^, =F)
        if a.startswith("^") or a.endswith(("=X", "=F", "-USD")):
            return a
    return sym


_COLONNES = ("symbol", "date", "open", "high", "low", "close", "adj_close", "volume")
_INSERT = ("INSERT OR REPLACE INTO prices "
           "(symbol, date, open, high, low, close, adj_close, volume) "
           "VALUES(?,?,?,?,?,?,?,?)")


def _migrer_schema(conn: sqlite3.Connection) -> None:
    """Complète une base `prices` plus ancienne que le schéma courant.

    `CREATE TABLE IF NOT EXISTS` ne touche pas une table déjà là — une base tirée
    du cache HuggingFace public, figée à un schéma antérieur (ex. sans `adj_close`),
    plantait alors sur l'INSERT positionnel avec « N colonnes mais M valeurs ».
    Idempotent : ne fait rien sur un schéma déjà à jour."""
    presentes = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    for col in _COLONNES:
        if col not in presentes:
            conn.execute(f"ALTER TABLE prices ADD COLUMN {col} REAL")


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=120)          # attend le verrou (lecteurs API) au lieu d'échouer
    conn.execute("PRAGMA busy_timeout=120000")       # EN PREMIER → les pragmas suivants attendent le verrou
    try:
        conn.execute("PRAGMA journal_mode=WAL")      # lecteurs + 1 écrivain en parallèle (idéal)
    except sqlite3.OperationalError:
        pass                                         # base tenue par un lecteur → on reste en rollback (busy_timeout gère)
    conn.executescript(_DDL)
    _migrer_schema(conn)
    n = reparer_volumes_inverses(conn)
    if n:
        print(f"volumes inversés réparés : {n} barres "
              "(le close avait été écrit dans volume)")
    perdus = volumes_irrecuperables(conn)
    if perdus:
        print(f"  ⚠ {perdus} barres ont le close en volume sans adj_close pour "
              "le retrouver (cache HF poussé depuis une base croisée ?) — "
              "les réécrire : make ingest")
    return conn


def reparer_volumes_inverses(conn: sqlite3.Connection) -> int:
    """Échange volume et adj_close là où l'INSERT positionnel les a croisés.

    L'ancien schéma avait `volume` puis `adj_close` ajouté au bout. Écrire huit
    valeurs sans nommer les colonnes a mis le close dans `volume` et le nombre
    d'actions dans `adj_close`. Signe : volume = close, ET adj_close ≠ close —
    l'ingest écrit toujours le même close dans close et adj_close, donc une ligne
    saine a adj_close = close. Après l'échange le signe disparaît : idempotent.

    Pas de seuil « adj_close ≫ close » : il laissait le prix en volume là où le
    vrai volume est nul ou faible (forex et indices à volume 0, BRK-A à 300
    titres/jour pour 700 k$ — reproduit le 07/10).
    """
    n = conn.execute(
        f"""UPDATE prices SET volume = adj_close, adj_close = volume
           WHERE close > 0 AND volume IS NOT NULL AND adj_close IS NOT NULL
             AND {_EGAL_CLOSE.format(col="volume")}
             AND NOT {_EGAL_CLOSE.format(col="adj_close")}"""
    ).rowcount
    conn.commit()
    return int(n)


_EGAL_CLOSE = "ABS({col} - close) <= MAX(1e-9, ABS(close) * 1e-9)"


def volumes_irrecuperables(conn: sqlite3.Connection) -> int:
    """Barres dont le volume vaut le close SANS adj_close pour le retrouver.

    Elles viennent d'un `make hf-pull` : si le cache a été poussé depuis une base
    croisée, il porte le close en volume et le vrai volume est perdu. On les compte
    sans les toucher — un nouvel ingest (`--since`) les réécrit correctement."""
    return int(conn.execute(
        f"""SELECT COUNT(*) FROM prices WHERE close > 0 AND adj_close IS NULL
              AND volume IS NOT NULL AND {_EGAL_CLOSE.format(col="volume")}"""
    ).fetchone()[0])


def _last_date(conn, symbol: str) -> str | None:
    r = conn.execute("SELECT MAX(date) FROM prices WHERE symbol=?", (symbol,)).fetchone()
    return r[0] if r and r[0] else None


# CE QUI PEUT SPLITTER. Un split ou un dividende est un acte d'ÉMETTEUR : seules les
# actions et les ETF en ont un. Un future, une paire de devises et un indice n'en ont pas.
#
# CONSTATÉ LE 15/09 dans le log du VPS : `--daily` re-backfillait onze ans d'historique,
# CHAQUE JOUR, pour CL=F BZ=F HO=F RB=F GC=F HG=F ALI=F ZC=F ZW=F ZS=F SB=F KC=F CC=F CT=F
# LE=F, USD/JPY et USD/MXN — « ajustement rétroactif détecté (split/dividende) ». Aucun de
# ces contrats n'a jamais splitté. Ce que le détecteur voyait, c'est le ROULEMENT : les
# tickers `=F` de Yahoo sont des contrats CONTINUS, dont le passé se réécrit à chaque
# changement d'échéance. Le détecteur avait donc raison sur le fait (les prix ont bougé) et
# tort sur la cause — et il en tirait la seule action qu'il connaisse : tout réécrire.
#
# DEUX CONSÉQUENCES, dont la seconde est la grave. L'ingest incrémental passait de quelques
# secondes à 4 min 25 (mesuré : 20 668 barres réinsérées avant même le 75ᵉ symbole sur 929).
# Et surtout, l'historique de ces séries n'était PAS STABLE : le passé de CL=F du jour J
# n'est pas celui du jour J−1. Un backtest relancé donne alors un autre résultat sans qu'une
# ligne de code ait changé — le genre d'instabilité qui se prend pour de l'alpha.
PEUT_SPLITTER = ("equity", "etf", "")


def _split_drift(conn, symbol: str, rows: list[tuple], tol: float = 5e-3) -> bool:
    """True si, sur les dates de chevauchement, le close FRAIS (ajusté) dévie du close STOCKÉ
    (> tol relatif) → un split/dividende est passé depuis le dernier ingest, la série stockée
    n'est plus dans le même référentiel d'ajustement."""
    for r in rows:
        stored = conn.execute("SELECT close FROM prices WHERE symbol=? AND date=?",
                              (symbol, r[1])).fetchone()
        if stored and stored[0] and r[5]:
            if abs(r[5] - stored[0]) > tol * max(1.0, abs(stored[0])):
                return True
    return False


def _fetch_yf(symbol: str, start: str, end: str, ysym: str | None = None) -> list[tuple]:
    """Bougies réelles via Ticker.history (colonnes simples, robuste — évite le multi-index de
    yf.download qui cassait l'extraction). `symbol` = clé stockée ; `ysym` = ticker Yahoo interrogé.

    ⚠️ `auto_adjust=True` (fix P1-4, 2026-07-06) : OHLC AJUSTÉS splits+dividendes. Sans ça, le
    momentum prix-only (sélecteur d'univers du preset depuis P0-1) voyait un split 10:1 comme
    -90 % → faux signal. L'incrémental gère la couture post-split via `_split_drift` (re-backfill)."""
    import yfinance as yf
    df = yf.Ticker(ysym or symbol).history(start=start, end=end, auto_adjust=True)
    if df is None or df.empty:
        return []

    def g(row, k):
        v = row.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if v == v else None                 # NaN → None

    out = []
    for ts, row in df.iterrows():
        out.append((symbol, ts.strftime("%Y-%m-%d"), g(row, "Open"), g(row, "High"), g(row, "Low"),
                    g(row, "Close"), g(row, "Close"), g(row, "Volume")))
    return out


def ingest(symbols: list[tuple[str, str]], since: str, daily: bool) -> None:
    conn = _connect()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    total, ok, fail, skip = 0, 0, 0, 0
    vides: list[str] = []            # ni OK ni échec : le fournisseur a répondu « rien »
    ajour: list[str] = []            # déjà à jour, rien à demander
    for i, (sym, ac) in enumerate(symbols, 1):
        ysym = _ysym(sym, ac)
        if ysym is None:                              # crypto → ignoré (make ingest-crypto)
            skip += 1
            continue
        start = since
        if daily:
            last = _last_date(conn, sym)
            if last:
                # Chevauchement volontaire de 7 j : si un split/dividende est passé depuis le
                # dernier ingest, les closes ajustés divergent des closes stockés → on repart
                # de `since` (re-backfill complet du symbole) au lieu de coller une série cassée.
                start = (datetime.strptime(last, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
                if last >= end[:10]:
                    ajour.append(sym)
                    continue
        try:
            rows = _fetch_yf(sym, start, end, ysym=ysym)
        except Exception as e:  # noqa: BLE001
            fail += 1
            if fail <= 20:
                print(f"[{i}/{len(symbols)}] {sym}: échec ({str(e)[:60]})")
            continue
        if rows:
            if daily and ac in PEUT_SPLITTER and _split_drift(conn, sym, rows):
                print(f"  ↺ {sym}: ajustement rétroactif détecté (split/dividende) → re-backfill")
                rows = _fetch_yf(sym, since, end, ysym=ysym)
                conn.execute("DELETE FROM prices WHERE symbol=?", (sym,))
            conn.executemany(_INSERT, rows)
            conn.commit()
            total += len(rows)
            ok += 1
        else:
            # LE TROU. Un `history()` vide ne lève rien : le symbole n'était donc compté ni
            # en OK ni en échec, et la ligne finale annonçait « 0 échecs » pendant que 91
            # symboles sur 929 ne rendaient aucune donnée (mesuré le 15/09). Un chiffre
            # qu'aucune ligne ne porte n'existe pas — c'est ainsi qu'un univers pourrit.
            vides.append(sym)
        if i % 25 == 0:
            print(f"  … {i}/{len(symbols)} symboles, {ok} OK, {total} barres insérées")
    _bilan(len(symbols), ok, fail, vides, ajour, skip, total)
    conn.close()


def _bilan(n: int, ok: int, fail: int, vides: list, ajour: list, skip: int,
           total: int) -> None:
    print(f"Terminé : {ok} OK · {fail} échecs · {len(vides)} sans donnée · "
          f"{len(ajour)} déjà à jour · {skip} crypto ignorées · {total} barres → {DB}")
    # Le total doit se refermer. Un écart signifierait un chemin de sortie non compté —
    # exactement le défaut que ces compteurs corrigent.
    reste = n - (ok + fail + len(vides) + len(ajour) + skip)
    if reste:
        print(f"  ⚠ {reste} symbole(s) sortis par un chemin non comptabilisé.")
    if vides:
        apercu = ", ".join(vides[:15]) + ("…" if len(vides) > 15 else "")
        print(f"  ⚠ sans donnée ({len(vides)}/{n}) : {apercu}")
        print("     Probablement délistés. Trancher sur VOS prix : make audit-univers")


def _silence_yfinance() -> None:
    """Coupe le bavardage par symbole de yfinance — pas les erreurs du script.

    Le log du cron est le SEUL relevé de ce qui s'est passé la nuit. Le 15/09 il fallait
    filtrer cinquante lignes « possibly delisted » pour atteindre la première ligne utile :
    un journal qu'on ne peut plus lire ne protège de rien. Le symbole muet n'est pas perdu
    pour autant — il est compté et nommé dans le résumé final, ce qui est plus utile qu'une
    ligne par symbole noyée dans le flot. `QUANT_VERBOSE_YF=1` rend le détail.
    """
    import os
    if os.environ.get("QUANT_VERBOSE_YF") == "1":
        return
    import logging
    for nom in ("yfinance", "urllib3", "peewee"):
        logging.getLogger(nom).setLevel(logging.CRITICAL)


if __name__ == "__main__":
    _silence_yfinance()
    ap = argparse.ArgumentParser(description="Ingestion de prix réels vers data/market.db")
    ap.add_argument("--symbols", nargs="*", help="liste de tickers (défaut: univers complet)")
    ap.add_argument("--since", default="2015-01-01", help="date de début du backfill")
    ap.add_argument("--daily", action="store_true", help="incrémental : reprend après la dernière barre")
    a = ap.parse_args()
    syms = [(s, "equity") for s in a.symbols] if a.symbols else _universe()
    print(f"Ingestion de {len(syms)} symboles (since={a.since}, daily={a.daily})…")
    ingest(syms, a.since, a.daily)
