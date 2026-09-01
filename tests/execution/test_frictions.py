"""Frictions explicites et règle d'inhibition (spec utilisateur 01/09, module 3)."""

import pytest

from packages.execution.frictions import STATUT, Frictions, signal_inhibe


def test_le_module_demarre_en_SHADOW():
    assert STATUT == "SHADOW_UNCALIBRATED"


def test_le_glissement_est_TOUJOURS_defavorable():
    """Modéliser un glissement parfois favorable est l'erreur qui rend un backtest
    optimiste : en moyenne il s'annulerait, alors qu'en réalité il coûte."""
    f = Frictions()
    assert f.prix_execute(50.0, achat=True) > 50.0
    assert f.prix_execute(50.0, achat=False) < 50.0


def test_le_prix_de_vente_ne_devient_jamais_negatif():
    f = Frictions(spread_bps=50_000, slippage_ticks=1e6)
    assert f.prix_execute(1.0, achat=False) == 0.0


def test_la_decomposition_somme_au_total():
    f = Frictions()
    d = f.detail(10_000, 50.0)
    assert d["commission"] + d["spread"] + d["slippage"] == pytest.approx(d["total"])
    assert f.cout_aller_retour(10_000, 50.0) == pytest.approx(d["total"])


def test_la_decomposition_designe_le_levier():
    """Le point du module : agrégées en bps, commission et spread sont indiscernables ;
    séparées, on sait laquelle attaque-t-on. Ici la commission domine → trader MOINS."""
    d = Frictions(commission_pct=0.0005, spread_bps=3.0).detail(10_000, 50.0)
    assert d["commission"] > d["spread"] + d["slippage"]


def test_l_aller_retour_vaut_deux_jambes():
    f = Frictions()
    attendu = 2 * f.cout_jambe(10_000, 50.0)
    assert f.cout_aller_retour(10_000, 50.0) == pytest.approx(attendu)


def test_le_slippage_en_ticks_depend_du_PRIX():
    """Un glissement d'un tick coûte proportionnellement plus cher sur un titre à 5 $
    que sur un titre à 500 $ — à notionnel égal, il y a cent fois plus de titres."""
    f = Frictions()
    assert f.cout_aller_retour(10_000, 5.0) > f.cout_aller_retour(10_000, 500.0)


# ------------------------------------------------------- règle d'inhibition
def test_une_esperance_trop_faible_est_INHIBEE():
    f = Frictions()
    r = signal_inhibe(gain_attendu=30.0, notionnel=10_000, prix_mid=50.0, frictions=f)
    assert r["inhibe"] and "coûte de l'argent" in r["motif"]


def test_une_esperance_confortable_PASSE():
    f = Frictions()
    assert not signal_inhibe(90.0, 10_000, 50.0, f)["inhibe"]


def test_le_seuil_est_bien_TRIPLE_du_cout():
    f = Frictions()
    cout = f.cout_aller_retour(10_000, 50.0)
    assert signal_inhibe(3 * cout + 0.01, 10_000, 50.0, f)["inhibe"] is False
    assert signal_inhibe(3 * cout - 0.01, 10_000, 50.0, f)["inhibe"] is True


def test_le_multiple_est_parametrable():
    f = Frictions()
    cout = f.cout_aller_retour(10_000, 50.0)
    assert not signal_inhibe(1.5 * cout, 10_000, 50.0, f, multiple=1.0)["inhibe"]
    assert signal_inhibe(1.5 * cout, 10_000, 50.0, f, multiple=2.0)["inhibe"]


def test_frictions_negatives_refusees():
    """Une friction négative rendrait le trading rentable par construction."""
    for champ in ("commission_pct", "spread_bps", "slippage_ticks"):
        with pytest.raises(ValueError, match="négatif"):
            Frictions(**{champ: -1.0})


def test_tick_nul_refuse():
    with pytest.raises(ValueError):
        Frictions(tick=0.0)


def test_notionnel_nul_ne_divise_pas_par_zero():
    assert Frictions().detail(0.0, 50.0)["bps_du_notionnel"] is None
