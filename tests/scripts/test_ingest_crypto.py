"""Changer la source d'une série est un geste destructif : il doit être exact.

Le symbole court `ARB-USD` chez Yahoo désigne un autre jeton (mesuré : corrélation +0,04
sur 994 jours). Reprendre la série ailleurs impose d'effacer d'abord ce qui était là —
sinon les jours que la nouvelle source ne couvre pas gardent les prix de l'homonyme, et
la série finale est cousue de deux actifs : pire que l'une ou l'autre, et indétectable.
"""

from __future__ import annotations

import sqlite3

from scripts.ingest_crypto import (
    SOURCE_FORCEE,
    _purger,
    source_de,
    ticker_yahoo,
)

DDL = ("CREATE TABLE prices (symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
       "close REAL, volume REAL, PRIMARY KEY (symbol, date))")


def _base() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(DDL)
    return conn


def test_le_symbole_de_stockage_ne_depend_pas_de_la_source() -> None:
    """La lecture cherche `ARB-USD` via `_yahoo_aliases`. Une série venue de Binance
    rangée sous un autre nom serait invisible — présente en base, absente à l'écran."""
    assert ticker_yahoo("ARB") == "ARB-USD"
    assert ticker_yahoo("arb") == "ARB-USD"
    assert ticker_yahoo("BTC") == "BTC-USD"


def test_seules_les_bases_mesurees_fausses_changent_de_source() -> None:
    """Une source forcée sans mesure remplacerait une série fausse par une autre."""
    assert source_de("BTC") == "yahoo"
    assert source_de("ETH") == "yahoo"
    mesurees = {"TON", "UNI", "APT", "ARB", "STX",       # 1er lot, réparé et vérifié
                "SUI", "TIA", "JUP", "STRK", "APE",      # 2e lot, univers complet
                "IMX", "GRT", "GMX", "GMT", "OP",        # 3e lot, référence paginée
                # 4e lot : source inadéquate (arrondi, ou historique trop court)
                "SHIB", "BONK", "XEC", "FLOKI", "COMP", "PEPE",
                "RPL"}                                   # 5e : source qui décroche
    for base in mesurees:
        assert source_de(base) == "binance", base
    assert set(SOURCE_FORCEE) == mesurees


def test_la_purge_efface_toute_la_serie_de_l_homonyme() -> None:
    """LE test. Sans purge, les dates que Binance ne couvre pas — l'histoire du jeton
    AVANT son existence, justement celle qui trahissait l'homonyme — resteraient."""
    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", f"2018-01-{j:02d}", 1, 1, 1, 1, 1)
                      for j in range(1, 21)])
    conn.commit()

    efface = _purger(conn, "ARB")

    assert efface == 20
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0


def test_la_purge_ne_touche_pas_les_autres_series() -> None:
    """Contrôle négatif : une purge trop large détruirait des données saines."""
    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", "2018-01-01", 1, 1, 1, 1, 1),
                      ("BTC-USD", "2018-01-01", 1, 1, 1, 1, 1),
                      ("ARBUSD", "2018-01-01", 1, 1, 1, 1, 1)])
    conn.commit()

    assert _purger(conn, "ARB") == 1
    restants = {r[0] for r in conn.execute("SELECT symbol FROM prices")}
    assert restants == {"BTC-USD", "ARBUSD"}


def test_purger_une_serie_absente_ne_leve_pas() -> None:
    assert _purger(_base(), "ZZZ") == 0


def test_une_source_muette_ne_detruit_pas_la_serie_existante(monkeypatch) -> None:
    """L'ordre destructeur, corrigé le 09/09 avant qu'il ne coûte quelque chose.

    La première version purgeait PUIS interrogeait : si la nouvelle source ne répondait
    pas, la base restait vide, sans rien pour la remplacer. Tant que la liste forcée
    tenait en cinq entrées vérifiées le risque restait théorique. Il cesse de l'être
    dès qu'on y ajoute des bases dont on ignore si la nouvelle source les couvre.
    """
    from scripts import ingest_crypto

    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", f"2024-01-{j:02d}", 1, 1, 1, 1, 1)
                      for j in range(1, 11)])
    conn.commit()
    monkeypatch.setattr(ingest_crypto, "_lignes_binance",
                        lambda *_a, **_k: ([], "historique Binance trop court"))

    ok, echecs = ingest_crypto._ingerer(conn, ["ARB"], None, None)

    assert ok == 0 and len(echecs) == 1
    restant = conn.execute("SELECT COUNT(*) FROM prices WHERE symbol='ARB-USD'")
    assert restant.fetchone()[0] == 10, "la série a été détruite sans remplaçant"


def test_une_source_qui_repond_remplace_bien_l_ancienne(monkeypatch) -> None:
    """Contre-partie : quand la nouvelle source répond, l'ancienne DOIT disparaître.

    Sinon les jours que la nouvelle ne couvre pas gardent les prix de l'homonyme, et la
    série finale est cousue de deux actifs — pire que l'une ou l'autre."""
    from scripts import ingest_crypto

    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", f"2018-01-{j:02d}", 1, 1, 1, 1, 1)
                      for j in range(1, 11)])
    conn.commit()
    neuves = [("ARB-USD", f"2024-01-{j:02d}", 2, 2, 2, 2, 2) for j in range(1, 6)]
    monkeypatch.setattr(ingest_crypto, "_lignes_binance",
                        lambda *_a, **_k: (neuves, ""))

    ok, echecs = ingest_crypto._ingerer(conn, ["ARB"], None, None)

    assert ok == 1 and not echecs
    dates = [r[0] for r in conn.execute(
        "SELECT date FROM prices WHERE symbol='ARB-USD' ORDER BY date")]
    assert dates == [d for _s, d, *_ in neuves], dates
