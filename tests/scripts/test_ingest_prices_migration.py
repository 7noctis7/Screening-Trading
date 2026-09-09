"""Migration du schéma `prices` — cas RÉEL du 04/09 : base HF tirée à un schéma
antérieur (7 colonnes, sans `adj_close`) plantait sur l'INSERT positionnel à 8
valeurs. `CREATE TABLE IF NOT EXISTS` ne répare rien sur une table déjà là."""
import sqlite3

from scripts.ingest_prices import _COLONNES, _migrer_schema


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


def test_insert_positionnel_fonctionne_apres_migration():
    conn = sqlite3.connect(":memory:")
    _table_ancienne(conn)
    _migrer_schema(conn)
    conn.execute("INSERT INTO prices VALUES(?,?,?,?,?,?,?,?)",
                 ("AAPL", "2026-09-04", 1.0, 2.0, 0.5, 1.5, 1.5, 1000.0))
    row = conn.execute("SELECT * FROM prices").fetchone()
    assert row == ("AAPL", "2026-09-04", 1.0, 2.0, 0.5, 1.5, 1.5, 1000.0)


def test_schema_deja_a_jour_est_un_no_op():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""CREATE TABLE prices(
        symbol TEXT NOT NULL, date TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume REAL,
        PRIMARY KEY(symbol, date));""")
    _migrer_schema(conn)                       # ne doit pas lever (ALTER sur colonne existante)
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(prices)")}
    assert colonnes == set(_COLONNES)
