"""Corrections issues de l'audit utilisateur (2026-08-21) :

- le seuil P/S absolu contredisait le filtre de marge (identité P/S = P/E × marge) ;
- un critère manqué peut être compensé par la note globale, SAUF la solvabilité ;
- le travail de risque (corrélation évitée, concentration, ES) doit être VISIBLE.
"""

from datetime import datetime, timezone

import numpy as np
import pytest

from packages.fundamentals.models import Financials
from packages.screening.alpha_pipeline import (Seuils, _viole, marges_sectorielles,
                                               metriques_qualite, ps_max_effectif,
                                               run_pipeline)
from packages.screening.decision_journal import journal_decision, note_ponderee

T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _fin(sym, secteur="Tech", price=100.0, revenue=1000.0, net=200.0, fcf=180.0,
         equity=800.0, debt=300.0, growth=0.20, shares=100.0):
    return Financials(symbol=sym, as_of=T0, sector=secteur, price=price, shares=shares,
                      revenue=revenue, gross_profit=revenue * 0.6, ebit=net * 1.3,
                      ebitda=net * 1.5, net_income=net, total_equity=equity,
                      total_debt=debt, cash=100.0, fcf=fcf, revenue_growth=growth)


def test_identite_comptable_P_sur_S_egale_P_sur_E_fois_marge():
    """La contradiction vient de là : fixer marge et P/E fixe DÉJÀ le P/S."""
    f = _fin("X", price=100.0, revenue=1000.0, net=200.0, shares=100.0)
    m = metriques_qualite(f)
    assert m["price_to_sales"] == pytest.approx(m["price_to_earnings"] * m["net_margin"])
    # contrôle sur les chiffres publiés de GOOGL (arrondis de la source)
    assert 16.92 * 0.548 == pytest.approx(9.25, abs=0.05)


def test_le_plafond_de_P_sur_S_est_deduit_du_secteur_et_non_absolu():
    s = Seuils()
    # secteur à forte marge (55 %) : un P/S de 9 y est NORMAL, pas cher
    forte = [_fin(f"H{i}", secteur="Logiciel", net=548.0, revenue=1000.0) for i in range(5)]
    marges = marges_sectorielles(forte)
    assert marges["Logiciel"] == pytest.approx(0.548, abs=1e-6)
    cap = ps_max_effectif(metriques_qualite(forte[0]), s, marges)
    assert cap == pytest.approx(25.0 * 0.548, rel=1e-9)      # ≈ 13,7 et non 7
    # secteur à faible marge (8 %) : le plafond descend logiquement
    faible = [_fin(f"L{i}", secteur="Distribution", net=80.0, revenue=1000.0) for i in range(5)]
    cap_faible = ps_max_effectif(metriques_qualite(faible[0]),
                                 s, marges_sectorielles(faible))
    assert cap_faible < cap


def test_une_societe_tres_rentable_n_est_plus_rejetee_par_le_seul_P_sur_S():
    """Cas GOOGL : rejeté par l'ancien P/S < 7 alors que son P/E de 16,9 est modéré."""
    s = Seuils()
    # marge 54,8 %, P/E ≈ 16,9 → P/S ≈ 9,25 : au-dessus de 7, en dessous du plafond sectoriel
    googl = _fin("GOOGL", secteur="Logiciel", revenue=1000.0, net=548.0,
                 price=92.5, shares=100.0)
    m = metriques_qualite(googl)
    assert m["price_to_sales"] == pytest.approx(9.25, rel=0.01)
    assert m["price_to_earnings"] == pytest.approx(16.88, rel=0.01)
    marges = marges_sectorielles([googl])
    assert not any("P/S" in v for v in _viole(m, s, marges))   # plus rejeté par le P/S
    # …mais il le serait avec un plafond absolu de 7 :
    assert m["price_to_sales"] > 7.0


# ---------------- note pondérée & véto ---------------------------------------
def test_une_bonne_note_compense_un_critere_manque():
    s = Seuils()
    m = metriques_qualite(_fin("C", net=300.0, growth=0.02, debt=50.0))   # croissance faible
    val = {"available": True, "marge_securite": 0.60, "fragile": False}
    mom = {"available": True, "au_dessus_ema50": True, "tendance_haussiere": True,
           "volume_confirme": True}
    n = note_ponderee(m, val, mom, s)
    assert n["veto"] is False
    assert n["note"] >= s.note_min                       # retenu MALGRÉ la croissance
    assert 0.0 <= n["note"] <= 1.0
    assert set(n["sous_notes"]) == {"qualite", "solvabilite", "valorisation", "momentum"}


def test_aucune_note_ne_compense_un_risque_de_ruine():
    s = Seuils()
    m = metriques_qualite(_fin("D", net=400.0, growth=0.50, equity=100.0, debt=900.0))
    assert m["debt_to_equity"] == pytest.approx(9.0)
    val = {"available": True, "marge_securite": 2.0, "fragile": False}
    mom = {"available": True, "au_dessus_ema50": True, "tendance_haussiere": True,
           "volume_confirme": True}
    n = note_ponderee(m, val, mom, s)
    assert n["veto"] is True and "solvabilité" in n["raison_veto"]


# ---------------- journal de décision ----------------------------------------
def _rets(seed, n=300, base=None):
    rng = np.random.default_rng(seed)
    return rng.normal(0, 0.01, n) if base is None else base + rng.normal(0, 0.0015, n)


def test_le_journal_ecarte_les_doublons_de_correlation_et_le_DIT():
    a = _rets(1)
    prices = {"A": {"returns": a}, "A_BIS": {"returns": _rets(2, base=a)},
              "B": {"returns": _rets(3)}}
    poids = {"A": 0.05, "A_BIS": 0.04, "B": 0.03}
    j = journal_decision(["A", "A_BIS", "B"], poids, prices, corr_max=0.80)
    assert "A_BIS" not in j["conserves"] and {"A", "B"} <= set(j["conserves"])
    ec = j["ecartes_correlation"][0]
    assert ec["symbole"] == "A_BIS" and ec["correle_a"] == "A" and ec["correlation"] > 0.8
    assert any("écarté" in L and "même pari" in L for L in j["lignes"])


def test_le_journal_publie_concentration_et_risque_de_queue():
    prices = {k: {"returns": _rets(i + 10)} for i, k in enumerate("XYZ")}
    j = journal_decision(list("XYZ"), {"X": 0.06, "Y": 0.03, "Z": 0.01}, prices)
    assert j["concentration"]["n_positions"] == 3
    assert 1.0 <= j["concentration"]["effective_n"] <= 3.0
    assert j["es_portefeuille"] > 0
    assert any("Concentration" in L for L in j["lignes"])
    assert any("pires journées" in L and "€" in L for L in j["lignes"])


def test_mode_score_bout_en_bout_et_entonnoir_complet():
    rng = np.random.default_rng(0)
    fins, prices = [], {}
    for i in range(30):
        fins.append(_fin(f"S{i}", net=150.0 + 5 * i, debt=100.0 + 20 * i))
        c = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.015, 400)))
        prices[f"S{i}"] = {"closes": c, "highs": c * 1.01, "lows": c * 0.99,
                           "volumes": np.r_[np.full(399, 1e6), 3e6],
                           "returns": np.diff(np.log(c))}
    r = run_pipeline(fins, prices, mode="score")
    assert r["mode"] == "score"
    couches = [e["couche"] for e in r["entonnoir"]]
    assert any("note pondérée" in c for c in couches)
    assert any("corrélation" in c for c in couches)
    assert "journal_decision" in r and isinstance(r["journal_decision"]["lignes"], list)
    with pytest.raises(ValueError):
        run_pipeline(fins, prices, mode="yolo")
