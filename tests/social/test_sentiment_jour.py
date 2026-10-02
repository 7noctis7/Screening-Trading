"""Le score du jour vient des messages lus, pas d'un volume de X inventé."""

import sqlite3
from datetime import datetime

from packages.social.modele import Publication
from packages.social.sentiment_jour import (
    TOP, agreger, enregistrer, pour_ml, retenir,
)


def _p(i, ticker, texte, jour="2026-10-02"):
    return Publication(
        id=str(i), compte="suivi",
        ts=datetime.fromisoformat(f"{jour}T15:00:00+00:00"),
        texte=texte, ticker=ticker,
    )


def test_le_plus_cite_passe_devant_et_le_texte_vide_ne_vote_pas():
    pubs = [
        _p(1, "AAPL", "$AAPL surge rally bullish beat"),
        _p(2, "AAPL", "$AAPL looks fine today"),
        _p(3, "ETH", "ethereum crash loss fraud bearish"),
    ]
    lignes = agreger(pubs, "2026-10-02")
    assert [r["ticker"] for r in lignes] == ["AAPL", "ETH"]
    assert lignes[0]["label"] == "bullish" and lignes[0]["mentions"] == 2
    assert lignes[0]["mentions_scorees"] == 1
    assert lignes[1]["label"] == "bearish" and lignes[1]["classe"] == "crypto"
    assert "volume" in lignes[0]["source"] and "pas le volume" in lignes[0]["source"]


def test_sans_mot_de_sentiment_l_etiquette_n_est_pas_neutre():
    lignes = agreger([_p(1, "MSFT", "$MSFT hello")], "2026-10-02")
    assert lignes[0]["label"] == "n/d" and lignes[0]["score"] is None


def test_on_garde_vingt_titres_pas_un_de_plus_et_pas_de_remplissage():
    lettres = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    pubs = [_p(i, lettres[i], "surge rally bullish") for i in range(25)]
    assert len(agreger(pubs, "2026-10-02")) == TOP
    assert agreger([], "2026-10-02") == []
    assert retenir("USDT") is False and retenir("BTC") is True


def test_la_table_est_idempotente_et_le_ml_ne_lit_pas_un_trou_comme_zero():
    conn = sqlite3.connect(":memory:")
    pubs = [_p(1, "NVDA", "surge rally bullish beat")]
    assert enregistrer(conn, pubs, "2026-10-02") == 1
    assert enregistrer(conn, pubs, "2026-10-02") == 1
    n = conn.execute("SELECT COUNT(*) FROM sentiment_jour").fetchone()[0]
    assert n == 1
    assert pour_ml(conn, "NVDA", "2026-10-02")["connu"] is True
    assert pour_ml(conn, "NVDA", "2026-10-02")["label"] == "bullish"
    vide = pour_ml(conn, "AAPL", "2026-10-02")
    assert vide["connu"] is False and vide["score"] is None
    hier = _p(2, "AAPL", "hello", jour="2026-10-01")
    enregistrer(conn, [hier], "2026-10-01")
    assert pour_ml(conn, "AAPL", "2026-10-01")["label"] == "n/d"
    assert pour_ml(conn, "AAPL", "2026-10-01")["connu"] is False
