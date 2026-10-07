"""Ajustement à la lecture : un split futur ne réécrit pas le passé (R3)."""

import sqlite3

from packages.data.prix_brut import (
    assurer,
    close_ajuste,
    facteur_volume,
    inserer_action,
    inserer_barre,
)


def _split(ex="2024-06-10", kt="2024-06-10"):
    return {"ex_date": ex, "action_type": "SPLIT", "ratio": 4.0,
            "knowledge_time": kt, "kt_quality": "INFERRED_LAG",
            "cash_amount": None, "close_veille": None}


def test_un_split_apres_as_of_ne_change_pas_le_passe():
    actions = [_split()]
    assert close_ajuste(400.0, actions, "2024-01-02", "2024-06-09") == 400.0


def test_le_meme_as_of_rend_les_deux_dates_comparables():
    actions = [_split()]
    as_of = "2024-12-31"
    avant = close_ajuste(400.0, actions, "2024-01-02", as_of)
    apres = close_ajuste(100.0, actions, "2024-06-11", as_of)
    assert avant == 100.0 and apres == 100.0


def test_le_dividende_n_ajuste_pas_le_volume():
    div = {"ex_date": "2024-06-10", "action_type": "CASH_DIV", "ratio": None,
           "cash_amount": 1.0, "close_veille": 100.0,
           "knowledge_time": "2024-06-10", "kt_quality": "INFERRED_LAG"}
    assert facteur_volume([div, _split()], "2024-01-02", "2024-12-31") == 4.0


def test_une_action_inconnue_est_ignoree():
    a = _split()
    a["kt_quality"] = "UNKNOWN"
    assert close_ajuste(400.0, [a], "2024-01-02", "2024-12-31") == 400.0


def test_le_brut_ne_se_reecrit_pas(tmp_path):
    conn = sqlite3.connect(tmp_path / "m.db")
    assurer(conn)
    inserer_barre(conn, "AAPL", "2024-01-02", 1, 1, 1, 180.0, 10)
    inserer_barre(conn, "AAPL", "2024-01-02", 1, 1, 1, 90.0, 99)
    inserer_action(conn, "AAPL", "2024-06-10", "SPLIT", ratio=2.0)
    inserer_action(conn, "AAPL", "2024-06-10", "SPLIT", ratio=10.0)
    conn.commit()
    close = conn.execute("SELECT close FROM ohlcv_raw").fetchone()[0]
    ratio = conn.execute("SELECT ratio FROM corporate_action").fetchone()[0]
    assert close == 180.0 and ratio == 2.0
