"""Compter les passages du robot, et chiffrer ce qu'un passage de trop a coûté.

L'invariant testé ici est celui de `packages.execution.passages` : `run_live._reconcile`
envoie AU PLUS UN ordre par symbole. Deux ordres de sens opposé sur un symbole le même jour
sont donc deux passages qui se contredisent — pas une stratégie.

Les séries sont SYNTHÉTIQUES (autorisé en tests pour valider la math) sauf le scénario de
référence, qui reprend les fills réels du 15/09.
"""

from datetime import date

import pytest

from packages.execution.passages import (
    allers_retours,
    instant,
    passages,
    rapport,
)

J = date(2026, 9, 15)


def _o(iso, sym, side, qty, px):
    return {"date": iso, "symbol": sym, "side": side, "qty": qty,
            "price": px, "notional": qty * px}


# ─── Découpage en passages ─────────────────────────────────────────────────────────────

def test_un_paquet_serre_est_un_seul_passage():
    """Treize ordres en une seconde, c'est UNE réconciliation (mesuré le 15/09)."""
    o = [_o(f"2026-09-15T18:32:4{i % 10}+00:00", f"S{i}", "buy", 1, 100)
         for i in range(13)]
    assert len(passages(o)) == 1


def test_trente_deux_minutes_separent_deux_passages():
    o = [_o("2026-09-15T18:32:44+00:00", "VEEV", "buy", 7.41, 270.73),
         _o("2026-09-15T19:04:15+00:00", "VEEV", "sell", 7.41, 269.64)]
    ps = passages(o)
    assert len(ps) == 2
    assert ps[0]["jour"] == ps[1]["jour"] == "2026-09-15"


def test_le_seuil_de_coupure_est_reglable():
    o = [_o("2026-09-15T18:00:00+00:00", "A", "buy", 1, 100),
         _o("2026-09-15T18:06:00+00:00", "A", "sell", 1, 100)]
    assert len(passages(o, ecart_max_s=300)) == 2      # 6 min > 5 min
    assert len(passages(o, ecart_max_s=600)) == 1      # 6 min < 10 min


def test_les_ordres_non_remplis_ne_comptent_pas():
    o = [dict(_o("2026-09-15T18:00:00+00:00", "A", "buy", 0, 100), qty=0.0)]
    assert passages(o) == []


def test_horodatage_illisible_ignore():
    assert instant("n'importe quoi") is None
    assert passages([_o("pas une date", "A", "buy", 1, 100)]) == []


def test_les_passages_sortent_dans_l_ordre_chronologique():
    o = [_o("2026-09-15T19:04:15+00:00", "B", "sell", 1, 100),
         _o("2026-09-15T18:32:44+00:00", "A", "buy", 1, 100)]
    ps = passages(o)
    assert [p["debut"][11:19] for p in ps] == ["18:32:44", "19:04:15"]


# ─── Allers-retours : le cas RÉEL du 15/09 ─────────────────────────────────────────────

def test_les_sept_lignes_du_15_09():
    """Achetées à 18:32, soldées à 19:04, à la quantité près. Prix du relevé Alpaca."""
    reels = [("VEEV", 7.41221008, 270.731668, 269.64),
             ("TYL", 6.27606728, 357.92, 356.536813),
             ("SWKS", 33.28650542, 88.48, 87.70),
             ("SNOW", 9.16030606, 321.516549, 321.41),
             ("PLTR", 10.53971696, 175.24, 174.90),
             ("OSCR", 86.28256206, 32.63, 32.78),
             ("ASST", 62.01927883, 28.01, 27.62)]
    o = []
    for s, q, pa, pv in reels:
        o.append(_o("2026-09-15T18:32:44+00:00", s, "buy", q, pa))
        o.append(_o("2026-09-15T19:04:15+00:00", s, "sell", q, pv))
    ar = allers_retours(o, J)
    assert ar["n_lignes"] == 7
    assert ar["pnl"] == pytest.approx(-58.54, abs=0.05)
    assert ar["notionnel"] == pytest.approx(33_027, rel=1e-3)   # 16 542 achetés + 16 485 vendus


def test_un_seul_sens_n_est_pas_un_aller_retour():
    """Un achat seul est une ouverture, pas du churn — même répété."""
    o = [_o("2026-09-15T18:32:44+00:00", "AAPL", "buy", 10, 100),
         _o("2026-09-15T19:04:15+00:00", "AAPL", "buy", 5, 101)]
    assert allers_retours(o, J)["n_lignes"] == 0


def test_seule_la_quantite_APPARIEE_compte():
    """Acheter 10 puis vendre 4 : quatre ont fait l'aller-retour, six sont restées."""
    o = [_o("2026-09-15T18:00:00+00:00", "AAPL", "buy", 10, 100.0),
         _o("2026-09-15T19:00:00+00:00", "AAPL", "sell", 4, 110.0)]
    ar = allers_retours(o, J)
    assert ar["lignes"][0]["qte_appariee"] == 4
    assert ar["pnl"] == pytest.approx(40.0)          # 4 × (110 − 100)


def test_un_aller_retour_gagnant_est_compte_comme_tel():
    """La mesure n'est pas un réquisitoire : OSCR a gagné 12,94 $ le 15/09."""
    o = [_o("2026-09-15T18:32:44+00:00", "OSCR", "buy", 86.28256206, 32.63),
         _o("2026-09-15T19:04:15+00:00", "OSCR", "sell", 86.28256206, 32.78)]
    assert allers_retours(o, J)["pnl"] == pytest.approx(12.94, abs=0.01)


def test_les_jours_voisins_ne_se_melangent_pas():
    o = [_o("2026-09-14T19:00:00+00:00", "A", "buy", 1, 100),
         _o("2026-09-15T19:00:00+00:00", "A", "sell", 1, 110)]
    assert allers_retours(o, J)["n_lignes"] == 0
    assert allers_retours(o, date(2026, 9, 14))["n_lignes"] == 0


def test_notionnel_reconstruit_quand_il_manque():
    """Certains courtiers ne renvoient pas `notional` : quantité × prix suffit."""
    o = [{"date": "2026-09-15T18:00:00+00:00", "symbol": "A", "side": "buy",
          "qty": 2, "price": 50.0},
         {"date": "2026-09-15T19:00:00+00:00", "symbol": "A", "side": "sell",
          "qty": 2, "price": 55.0}]
    assert allers_retours(o, J)["pnl"] == pytest.approx(10.0)


# ─── Rapport : DEPUIS QUAND ────────────────────────────────────────────────────────────

def test_le_rapport_nomme_la_premiere_date_a_doublon():
    """Le total intéresse moins que la DATE : c'est elle qui dit à partir d'où la courbe
    d'equity porte du churn qu'aucune stratégie n'a décidé."""
    o = [_o("2026-09-10T19:05:00+00:00", "A", "buy", 1, 100),      # 1 passage
         _o("2026-09-12T18:30:00+00:00", "B", "buy", 1, 100),      # 2 passages
         _o("2026-09-12T19:05:00+00:00", "B", "sell", 1, 90),
         _o("2026-09-14T18:30:00+00:00", "C", "buy", 1, 100),
         _o("2026-09-14T19:05:00+00:00", "C", "sell", 1, 95)]
    r = rapport(o)
    assert r["n_jours"] == 3
    assert r["jours_a_doublon"] == ["2026-09-12", "2026-09-14"]
    assert r["depuis"] == "2026-09-12"
    assert r["pnl_churn"] == pytest.approx(-15.0)


def test_sans_doublon_le_rapport_le_dit_clairement():
    o = [_o("2026-09-10T19:05:00+00:00", "A", "buy", 1, 100),
         _o("2026-09-11T19:05:00+00:00", "A", "sell", 1, 110)]
    r = rapport(o)
    assert r["depuis"] is None
    assert r["jours_a_doublon"] == []
    assert r["pnl_churn"] == 0.0


def test_historique_vide_ne_casse_rien():
    r = rapport([])
    assert r["n_jours"] == 0 and r["depuis"] is None and r["pnl_churn"] == 0.0


# ─── La lecture du courtier ne fabrique JAMAIS de série ────────────────────────────────

def test_sans_cle_la_lecture_rend_un_motif_pas_une_liste_vide_muette(monkeypatch):
    """Un historique ABSENT n'est pas un historique NUL. Confondre les deux ferait dire
    « aucun doublon » à un outil qui n'a simplement rien pu lire."""
    from packages.execution import historique_courtier as hc
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET", raising=False)
    courtier, motif = hc._alpaca_par_chemin()
    assert courtier is None
    assert "aucune clé" in motif


def test_le_module_de_lecture_n_envoie_aucun_ordre():
    """Ce module lit. Il ne doit contenir aucun chemin d'envoi — c'est ce qui permet de
    l'appeler depuis un brief quotidien sans y réfléchir à deux fois."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "packages" / "execution"
           / "historique_courtier.py").read_text(encoding="utf-8")
    for interdit in ("submit", "close_position", "--live", "cancel"):
        assert interdit not in src, f"chemin d'écriture dans un module de lecture : {interdit}"


def test_le_brief_surveille_les_passages():
    """La dérive doit se voir CHAQUE MATIN, pas se découvrir six semaines plus tard."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
           / "daily_brief.py").read_text(encoding="utf-8")
    assert "_passages_du_robot" in src
    assert "Passages du robot" in src
    # Et il doit nommer les planificateurs à vérifier : un avertissement sans geste à
    # faire se lit une fois, puis se saute.
    assert "crontab -l" in src and "list-timers" in src
