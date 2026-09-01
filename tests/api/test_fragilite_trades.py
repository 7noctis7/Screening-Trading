"""Un profit factor de 1,01 ne dit pas s'il y a un avantage ou un hasard.

Constat du 31/08 : le panneau « qualité des trades » affichait espérance +1 $, payoff
2,53, profit factor 1,01 — des chiffres cohérents entre eux, et muets sur l'essentiel.
Un payoff ne se lit JAMAIS seul : il se compare au seuil de rentabilité imposé par le taux de
réussite, (1 − p) / p. Et une espérance positive portée par trois trades n'est pas un
avantage, c'est une loterie.
"""

from dataclasses import dataclass

import pytest

from apps.api.payloads import trade_stats_payload


@dataclass
class T:
    pnl_net: float
    pnl_pct: float = 0.0


def test_le_seuil_de_rentabilite_est_publie():
    """À 25 % de réussite, il faut un payoff de 3,0 pour ne RIEN gagner."""
    d = trade_stats_payload([T(300.0)] * 25 + [T(-100.0)] * 75)
    assert d["payoff"] == 3.0
    assert d["payoff_seuil"] == 3.0
    assert d["marge_payoff_pct"] == 0.0
    assert d["profit_factor"] == 1.0


def test_une_marge_NEGATIVE_est_visible():
    """Un payoff flatteur sous son seuil perd de l'argent — il faut que ça se voie."""
    d = trade_stats_payload([T(250.0)] * 25 + [T(-100.0)] * 75)
    assert d["marge_payoff_pct"] < 0
    assert d["profit_factor"] < 1.0


def test_une_marge_POSITIVE_est_visible():
    d = trade_stats_payload([T(400.0)] * 25 + [T(-100.0)] * 75)
    assert d["marge_payoff_pct"] > 0
    assert d["profit_factor"] > 1.0


def test_la_LOTERIE_est_demasquee():
    """Le test qui compte. 99 gagnants minuscules, 1 gagnant énorme, 100 perdants :
    profit factor flatteur, mais UN SEUL trade couvre toutes les pertes."""
    trades = [T(10_000.0)] + [T(1.0)] * 99 + [T(-40.0)] * 100
    d = trade_stats_payload(trades)
    assert d["profit_factor"] > 2, "l'exemple doit paraître rentable"
    assert d["n_gagnants_couvrant_les_pertes"] == 1, d
    assert d["part_top5_du_gain_brut_pct"] > 98


def test_un_avantage_REPARTI_ne_declenche_pas_l_alerte():
    """Contrepartie : l'instrument ne doit pas crier au hasard sur un système sain."""
    d = trade_stats_payload([T(300.0)] * 50 + [T(-100.0)] * 50)
    assert d["n_gagnants_couvrant_les_pertes"] >= 15, d
    assert d["part_top5_du_gain_brut_pct"] < 40


def test_pertes_jamais_couvertes_rend_None():
    """Une stratégie perdante n'a PAS de nombre de gagnants couvrant les pertes —
    renvoyer 0 ou le total laisserait croire à une couverture."""
    d = trade_stats_payload([T(10.0)] * 5 + [T(-1000.0)] * 50)
    assert d["n_gagnants_couvrant_les_pertes"] is None


def test_aucun_gagnant_ne_casse_rien():
    d = trade_stats_payload([T(-100.0)] * 10)
    assert d["count"] == 10 and "payoff" not in d


def test_aucun_perdant_ne_casse_rien():
    """Division par zéro sur les pertes : le payoff n'existe pas, on se tait."""
    d = trade_stats_payload([T(100.0)] * 10)
    assert d["count"] == 10 and "payoff" not in d


def test_les_champs_historiques_sont_preserves():
    """Non-régression : le front lit déjà ces clés."""
    d = trade_stats_payload([T(300.0)] * 25 + [T(-100.0)] * 75)
    for k in ("count", "wins", "losses", "win_rate", "pnl_total",
              "avg_win", "avg_loss", "profit_factor", "best", "worst"):
        assert k in d, k


def test_le_payoff_publie_egale_avg_win_sur_avg_loss():
    """Cohérence avec ce que le front affiche déjà (gain moyen / perte moyenne)."""
    d = trade_stats_payload([T(400.0)] * 30 + [T(-158.0)] * 70)
    assert d["payoff"] == pytest.approx(abs(d["avg_win"] / d["avg_loss"]), abs=0.01)
