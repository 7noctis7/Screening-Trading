"""Ingestion des PRIX CRYPTO réels (top-N par market cap) → data/crypto.db.

La crypto n'est PAS dans YAHOO.db (actions only) → la poche Bitmart tournait en synthétique
(donc écartée). Ce script récupère l'OHLCV réel via yfinance (BTC-USD, ETH-USD, …) pour les
cryptos de ton univers et l'écrit dans une base SIDECAR `data/crypto.db` (format long, lue en
plus de YAHOO.db). Résultat : sleeve crypto, cœur crypto, graphes & comparaison sur du RÉEL.

On n'écrit JAMAIS dans YAHOO.db (4 Go, lecture seule) → base dédiée, non destructive.

  python scripts/ingest_crypto.py            # top 50 cryptos
  python scripts/ingest_crypto.py --top 100
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _bases_univers(top: int) -> list[str]:
    """Bases crypto uniques de l'univers, plafonnées à `top`, ordre du classement."""
    from apps.api.snapshot import _seed_universe
    inst = [m for m in _seed_universe() if m.get("asset_class") == "crypto"]
    bases: list[str] = []
    for m in inst:
        # normalise vers la base : BTC/USDT → BTC, BTC-USD → BTC, BTC → BTC (évite le suffixe
        # ajouté en double « BTC-USD-USD » quand l'univers stocke déjà le format yfinance).
        raw = m["symbol"].upper().split("/")[0]
        base = raw[:-4] if raw.endswith("-USD") else (raw[:-5] if raw.endswith("-USDT") else raw)
        if base and base not in bases:
            bases.append(base)
    return bases[:top]


# Bases dont le symbole court Yahoo désigne un AUTRE jeton : `{base}-USD` y ramène la
# série d'un homonyme, propre de forme et fausse de bout en bout. Chaque entrée est
# MESURÉE — corrélation des rendements contre Binance, `make diag-source-crypto`,
# 09/09 — et non supposée. Deux confirmations indépendantes par ligne : la corrélation
# quasi nulle, et une date de début antérieure à l'existence du jeton.
SOURCE_FORCEE: dict[str, str] = {
    # Premier lot, RÉPARÉ ET VÉRIFIÉ : après bascule, les cinq ressortent CONFORMES avec
    # corr +1,00. Le début de série change du tout au tout, ce qui achève la preuve —
    # `ARB` passe de 2017-11 (impossible) à 2023-03, `APT` de 2021-11 à 2022-10.
    "TON": "binance",   # corr −0,08 / 691 j · Yahoo depuis 2020-08 → Binance 2024-08
    "UNI": "binance",   # corr +0,25 / 490 j · Yahoo depuis 2019-10 → Binance 2020-09
    "APT": "binance",   # corr +0,11 / 556 j · Yahoo depuis 2021-11 → Binance 2022-10
    "ARB": "binance",   # corr +0,04 / 994 j · Yahoo depuis 2017-11 → Binance 2023-03
    "STX": "binance",   # corr +0,00 / 496 j · Yahoo depuis 2019-10 → Binance 2019-10
    # Second lot, trouvé une fois l'univers complet ingéré (les 52 bases manquantes
    # contenaient leurs propres homonymes). Même signature : corrélation nulle contre
    # la référence, et un début de série qui précède de plusieurs années le jeton.
    "SUI": "binance",   # corr +0,06 / 173 j · Yahoo depuis 2022-03, arrêtée en 2024-06
    "TIA": "binance",   # corr −0,01 / 998 j · Yahoo depuis 2022-02
    "JUP": "binance",   # corr −0,00 / 950 j · Yahoo depuis 2017-11
    "STRK": "binance",  # corr +0,08 / 930 j · Yahoo depuis 2021-04
    "APE": "binance",   # corr +0,00 / 998 j · Yahoo depuis 2020-10, figée 154 séances
}


def ticker_yahoo(base: str) -> str:
    """Symbole sous lequel la série est STOCKÉE en base, quelle que soit sa source.

    On garde la convention Yahoo (`BTC-USD`) même pour les séries venues de Binance :
    c'est ce que `_yahoo_aliases` cherche à la lecture, et fabriquer une seconde
    convention obligerait chaque lecteur à connaître la provenance de chaque ligne.
    """
    return f"{base.upper()}-USD"


def source_de(base: str) -> str:
    """« yahoo » par défaut ; « binance » pour les bases où Yahoo a été mesuré faux."""
    return SOURCE_FORCEE.get(base.upper(), "yahoo")


def _lignes_yahoo(base: str, start, end) -> tuple[list, str]:
    """(lignes prêtes à écrire, cause d'échec). L'une des deux est toujours vide."""
    import yfinance as yf
    ysym = ticker_yahoo(base)
    try:
        df = yf.Ticker(ysym).history(start=start.date().isoformat(),
                                     end=end.date().isoformat())
    except Exception as e:  # noqa: BLE001
        return [], f"réseau/yfinance : {type(e).__name__}"
    if df is None or len(df) < 250:
        return [], f"historique trop court ({0 if df is None else len(df)} barres)"
    lignes = [(ysym, d.date().isoformat(), float(r.Open), float(r.High), float(r.Low),
               float(r.Close), float(r.Volume or 0))
              for d, r in df.iterrows() if r.Close == r.Close and r.Close > 0]
    return lignes, "" if lignes else "aucune clôture valide"


def _lignes_binance(base: str, start) -> tuple[list, str]:
    """Idem depuis Binance, pour les bases où Yahoo désigne un autre jeton."""
    from packages.data.crypto_binance import historique
    ysym = ticker_yahoo(base)
    barres = historique(base, depuis=start.date().isoformat())
    if len(barres) < 250:
        return [], f"historique Binance trop court ({len(barres)} barres)"
    return [(ysym, j, o, h, b, c, v) for j, o, h, b, c, v in barres], ""


def _purger(conn: sqlite3.Connection, base: str) -> int:
    """Efface les lignes existantes d'une base dont la source change.

    Sans cela, les jours que la nouvelle source ne couvre pas garderaient les prix de
    l'homonyme : une série cousue de deux actifs, pire que l'une ou l'autre, et
    indétectable ensuite. On l'annonce — on ne touche jamais à des données de marché
    en silence.
    """
    ysym = ticker_yahoo(base)
    n = conn.execute("SELECT COUNT(*) FROM prices WHERE symbol=?",
                     (ysym,)).fetchone()[0]
    if n:
        conn.execute("DELETE FROM prices WHERE symbol=?", (ysym,))
        conn.commit()
    return int(n)


def _ingerer(conn: sqlite3.Connection, bases: list[str], start,
             end) -> tuple[int, list]:
    """Récupère chaque base via yfinance, écrit ce qui répond.

    Renvoie (nb réussi, échecs) où chaque échec est (base, ticker, cause). La première
    version renvoyait le seul compte des succès et avalait tout le reste en silence :
    une source cassée ne laissait AUCUNE trace, et c'est comme ça que cinq séries
    `/USDC` sont restées inexploitables sans que rien ne le signale. Un ingest qui ne
    dit pas ce qu'il n'a pas pu faire donne l'illusion d'un univers complet.
    """
    ok, echecs = 0, []
    for i, base in enumerate(bases, 1):
        source = source_de(base)
        if source == "binance":
            efface = _purger(conn, base)
            print(f"  {base} : source forcée sur Binance (Yahoo mesuré faux)"
                  + (f" — {efface} lignes de l'homonyme effacées" if efface else ""))
            lignes, cause = _lignes_binance(base, start)
        else:
            lignes, cause = _lignes_yahoo(base, start, end)
        if cause or not lignes:
            echecs.append((base, ticker_yahoo(base), cause or "aucune ligne"))
            continue
        conn.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", lignes)
        conn.commit()
        ok += 1
        if i % 10 == 0:
            print(f"  … {i}/{len(bases)} ({ok} avec données)")
    return ok, echecs


def main() -> None:
    ap = argparse.ArgumentParser()
    # Défaut 0 = TOUT l'univers crypto. L'ancien défaut de 50 laissait 52 bases sur 102
    # sans la moindre barre en base (mesuré le 09/09 : la frontière tombait exactement
    # au 50ᵉ symbole), sans que rien ne le dise. Le périmètre est défini par l'univers,
    # pas par un nombre rond.
    ap.add_argument("--top", type=int, default=0,
                    help="nb de cryptos à ingérer (0 = tout l'univers)")
    ap.add_argument("--days", type=int, default=3650, help="profondeur d'historique (jours)")
    a = ap.parse_args()

    bases = _bases_univers(a.top or 10_000)
    if not bases:
        print("Aucune crypto dans l'univers (data/seed/crypto_*.csv)."); return
    print(f"{len(bases)} cryptos à ingérer (yfinance) : {', '.join(bases[:15])}…\n")

    try:
        import yfinance  # noqa: F401
    except Exception:  # noqa: BLE001
        print("yfinance indisponible — uv pip install yfinance."); return

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=a.days)
    db = ROOT / "data" / "crypto.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")          # lecteurs API + écriture sans 'database is locked'
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("CREATE TABLE IF NOT EXISTS prices (symbol TEXT, date TEXT, open REAL, high REAL, "
                 "low REAL, close REAL, volume REAL, PRIMARY KEY (symbol, date))")
    ok, echecs = _ingerer(conn, bases, start, end)
    conn.close()
    if echecs:
        print(f"\n⚠  {len(echecs)} base(s) sans données — l'univers n'est PAS complet :")
        for base, ysym, cause in echecs[:20]:
            print(f"     · {base:8s} (interrogé « {ysym} ») — {cause}")
        if len(echecs) > 20:
            print(f"     … et {len(echecs) - 20} autre(s)")
        print("   Une série absente vaut mieux qu'une série fausse, mais elle doit se voir.")
        print("   Confronter les séries écrites à une référence : make diag-source-crypto")
    if ok == 0:
        print("Aucune donnée crypto récupérée (réseau ?)."); return
    print(f"\n✅ {ok} cryptos écrites → {db}")
    print("   Relance le site (make api) : sleeve crypto, cœur crypto, graphes & comparaison sont")
    print("   maintenant sur des prix RÉELS. Backtest cœur crypto : make crypto-core.")


if __name__ == "__main__":
    main()
