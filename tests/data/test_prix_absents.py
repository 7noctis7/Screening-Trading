"""open/high/low à 0 : une valeur absente, jamais un prix — et jamais inventée."""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.data import prix_absents
from packages.data.audit import audit_series
from packages.data.providers.db_provider import DBPriceProvider

DDL = ("CREATE TABLE prices (symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
       "close REAL, adj_close REAL, volume REAL, PRIMARY KEY (symbol, date))")
LIGNES = [
    ("NDX", "2026-06-12", 0.0, 0.0, 0.0, 21000.0, 21000.0, 0.0),     # Yahoo : clôture seule
    ("AAVE-USD", "2020-10-02", 0.0, 60.0, 0.0, 52.0, 52.0, 1e6),     # 1re barre d'un jeton
    ("CL=F", "2020-04-20", 17.7, 17.9, -40.3, 1.0, 1.0, 1e5),        # terme : négatif légitime
    ("CL=F", "2020-04-21", 0.0, 1.0, 0.5, 0.9, 0.9, 1e5),            # mais le ZÉRO reste absent
    ("ABC", "2021-01-04", -1.0, 11.0, 9.0, 10.0, 10.0, 1e3),         # action : négatif = corrompu
    ("SAIN", "2021-01-04", 10.0, 11.0, 9.0, 10.5, 10.5, 1e3),        # rien à toucher
    ("MORT", "2021-01-04", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),            # clôture nulle : on n'y touche pas
]


def _base(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "market.db")
    conn.execute(DDL)
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", LIGNES)
    conn.commit()
    return conn


def _ligne(conn, sym, d):
    return conn.execute("SELECT open, high, low, close FROM prices WHERE symbol=? AND date=?",
                        (sym, d)).fetchone()


def test_les_zeros_deviennent_absents_et_la_cloture_ne_bouge_pas(tmp_path):
    conn = _base(tmp_path)
    n = prix_absents.reparer(conn)
    # open : NDX, AAVE, le zéro de CL=F, le négatif d'ABC ; high : NDX ; low : NDX, AAVE
    assert n == {"open": 4, "high": 1, "low": 2}
    assert _ligne(conn, "NDX", "2026-06-12") == (None, None, None, 21000.0)
    assert _ligne(conn, "AAVE-USD", "2020-10-02") == (None, 60.0, None, 52.0)
    assert _ligne(conn, "ABC", "2021-01-04") == (None, 11.0, 9.0, 10.0)


def test_un_terme_garde_son_prix_negatif_mais_pas_son_zero(tmp_path):
    """WTI le 20/04/2020 : −40,3 au plus bas est un fait de marché ; un 0 pile, non."""
    conn = _base(tmp_path)
    prix_absents.reparer(conn)
    assert _ligne(conn, "CL=F", "2020-04-20") == (17.7, 17.9, -40.3, 1.0)
    assert _ligne(conn, "CL=F", "2020-04-21")[0] is None


def test_rien_n_est_invente_ni_touche_ailleurs(tmp_path):
    conn = _base(tmp_path)
    prix_absents.reparer(conn)
    assert _ligne(conn, "SAIN", "2021-01-04") == (10.0, 11.0, 9.0, 10.5)
    assert _ligne(conn, "MORT", "2021-01-04") == (0.0, 0.0, 0.0, 0.0)


def test_idempotent(tmp_path):
    conn = _base(tmp_path)
    prix_absents.reparer(conn)
    assert prix_absents.reparer(conn) == {"open": 0, "high": 0, "low": 0}
    assert prix_absents.compter(conn) == 0


def test_apres_reparation_l_audit_ne_crie_plus_sur_ces_barres(tmp_path):
    """Les 23 critiques du 30/10 étaient exactement ce motif : il doit disparaître."""
    conn = _base(tmp_path)
    avant = _critiques(conn, "NDX")
    prix_absents.reparer(conn)
    assert avant and not _critiques(conn, "NDX")


def _critiques(conn, sym):
    barres = [{"ts": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": 0}
              for r in conn.execute("SELECT date, open, high, low, close FROM prices WHERE "
                                    "symbol=?", (sym,))]
    return [a for a in audit_series(sym, barres, min_bars=1) if a.severity == "critical"]


def test_le_lecteur_de_barres_ne_rend_jamais_un_zero_en_ouverture():
    """Base NON réparée (YAHOO.db local) : la barre retombe sur la clôture, pas sur 0."""
    b = DBPriceProvider._mk_bar("NDX", "1d", ("2026-06-12", 0.0, 0.0, 0.0, 21000.0, 0.0))
    assert (b.open, b.high, b.low, b.close) == (21000.0, 21000.0, 21000.0, 21000.0)
    t = DBPriceProvider._mk_bar("CL=F", "1d", ("2020-04-20", 17.7, 17.9, -40.3, 1.0, 1e5))
    assert t.low == -40.3 and isinstance(t.ts, datetime)


def test_le_script_repare_les_deux_bases_et_ignore_l_absente(tmp_path):
    from scripts.reparer_prix_absents import reparer_base
    _base(tmp_path).close()
    assert sum(reparer_base(tmp_path / "market.db").values()) == 7
    assert reparer_base(tmp_path / "absente.db") is None


def test_une_base_normalisee_n_est_pas_modifiee(tmp_path):
    """Format NORMALISÉ (YAHOO.db : tables par identifiant) : rien n'est réécrit — le
    lecteur de barres neutralise les zéros à la lecture, quel que soit le schéma."""
    from scripts.reparer_prix_absents import reparer_base
    conn = sqlite3.connect(tmp_path / "YAHOO.db")
    conn.execute("CREATE TABLE P_1D (id INTEGER, date TEXT, open REAL, close REAL)")
    conn.execute("INSERT INTO P_1D VALUES (1, '2026-06-12', 0.0, 21000.0)")
    conn.commit(); conn.close()
    assert reparer_base(tmp_path / "YAHOO.db") is None
    conn = sqlite3.connect(tmp_path / "YAHOO.db")
    assert conn.execute("SELECT open FROM P_1D").fetchone() == (0.0,)
