"""Migration du schéma `prices` — cas RÉEL du 04/09 : base HF tirée à un schéma
antérieur (7 colonnes, sans `adj_close`) plantait sur l'INSERT positionnel à 8
valeurs. `CREATE TABLE IF NOT EXISTS` ne répare rien sur une table déjà là.

Le 07/10, cet INSERT sans noms de colonnes a continué à écrire dans l'ordre
PHYSIQUE (volume avant adj_close) : le close s'est retrouvé dans volume."""
import sqlite3

from scripts.ingest_prices import (
    _COLONNES,
    _INSERT,
    _migrer_schema,
    reparer_volumes_inverses,
    volumes_irrecuperables,
)


def _table_ancienne(conn: sqlite3.Connection) -> None:
    """Reproduit le schéma HF antérieur : sans `adj_close`."""
    conn.execute("""CREATE TABLE prices(
        symbol TEXT NOT NULL, date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        PRIMARY KEY(symbol, date))""")


def test_ajoute_la_colonne_manquante():
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    _migrer_schema(conn)
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    assert colonnes == set(_COLONNES)


def test_insert_nomme_respecte_volume_apres_migration():
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    _migrer_schema(conn)
    conn.execute(_INSERT, ("AAPL", "2026-09-04", 1.0, 2.0, 0.5, 1.5, 1.5, 1000.0))
    lu = conn.execute("SELECT close, adj_close, volume FROM prices").fetchone()
    assert lu == (1.5, 1.5, 1000.0)


def test_repare_le_volume_croise_et_laisse_une_ligne_saine():
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    _migrer_schema(conn)
    conn.execute(
        "INSERT INTO prices (symbol, date, open, high, low, close, volume, adj_close) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("AAPL", "2026-10-06", 330.0, 334.0, 329.0, 333.63, 333.63, 29_565_965.0))
    conn.execute(
        _INSERT,
        ("MSFT", "2026-10-06", 520.0, 530.0, 519.0, 529.0, 529.0, 20_000_000.0))
    assert reparer_volumes_inverses(conn) == 1
    assert reparer_volumes_inverses(conn) == 0
    aapl = conn.execute(
        "SELECT close, adj_close, volume FROM prices WHERE symbol='AAPL'").fetchone()
    msft = conn.execute(
        "SELECT volume FROM prices WHERE symbol='MSFT'").fetchone()
    assert aapl == (333.63, 333.63, 29_565_965.0)
    assert msft == (20_000_000.0,)


def test_schema_deja_a_jour_est_un_no_op():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""CREATE TABLE prices(
        symbol TEXT NOT NULL, date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL,
        adj_close REAL, volume REAL,
        PRIMARY KEY(symbol, date));""")
    _migrer_schema(conn)                       # ne doit pas lever (ALTER sur colonne existante)
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    assert colonnes == set(_COLONNES)


# l'écriture d'avant le 07/10
_POSITIONNEL = "INSERT INTO prices VALUES(?,?,?,?,?,?,?,?)"


def test_repare_aussi_les_volumes_nuls_ou_faibles():
    """Reproduit le 07/10 : le seuil « adj_close > 5 × close » laissait le prix en
    volume quand le vrai volume était nul (forex) ou faible devant le prix (BRK-A)."""
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    _migrer_schema(conn)
    conn.execute(_POSITIONNEL, ("EURUSD=X", "2026-10-06", 1.1, 1.1, 1.09, 1.095,
                                1.095, 0.0))
    conn.execute(_POSITIONNEL, ("BRK-A", "2026-10-06", 7e5, 7.2e5, 7e5, 712_000.0,
                                712_000.0, 310.0))
    assert reparer_volumes_inverses(conn) == 2
    assert reparer_volumes_inverses(conn) == 0
    lu = dict(conn.execute("SELECT symbol, volume FROM prices").fetchall())
    assert lu == {"EURUSD=X": 0.0, "BRK-A": 310.0}


def test_compte_sans_toucher_les_volumes_irrecuperables():
    """Ligne tirée d'un cache HF croisé : close en volume, pas d'adj_close."""
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    conn.execute("INSERT INTO prices VALUES(?,?,?,?,?,?,?)",
                 ("NVDA", "2019-01-02", 3.3, 3.5, 3.2, 3.40, 3.40))
    _migrer_schema(conn)
    assert volumes_irrecuperables(conn) == 1
    assert reparer_volumes_inverses(conn) == 0
    assert conn.execute("SELECT volume FROM prices").fetchone() == (3.40,)
