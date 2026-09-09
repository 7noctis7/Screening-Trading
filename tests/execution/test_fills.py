"""Le contrat d'exécution : ce qu'un ordre a RÉELLEMENT coûté.

Le test qui compte ici est `test_le_shortfall_ne_se_retranche_PAS_du_pnl`. Le slippage
est déjà contenu dans le prix de fill — il a été payé à l'exécution et il est déjà dans
un P&L calculé sur des prix de fill. Le retrancher une seconde fois compterait deux fois
le même coût. Mesuré le 09/09 sur le journal réel : 66 fills portent les deux prix, donc
66 occasions de faire l'erreur.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.models import Fill, Order, OrderType, Side
from packages.execution.costs import CostModel
from packages.execution.fills import fill_de_l_ordre, shortfall_bps
from packages.execution.sim_broker import SimBroker

_TS = datetime(2026, 9, 9, tzinfo=UTC)


def _fill(**kw) -> Fill:
    """Passe par le VRAI constructeur : un helper qui court-circuiterait
    `fill_de_l_ordre` testerait un objet que la production ne fabrique jamais."""
    base = dict(reference_price=100.0, fill_price=100.0, commission=0.0, fees_other=0.0)
    return fill_de_l_ordre(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET),
                           **{**base, **kw})


# ── la convention de signe ──────────────────────────────────────────────────

def test_un_achat_plus_cher_que_la_reference_coute():
    assert shortfall_bps(100.0, 100.05, Side.LONG) == pytest.approx(5.0)


def test_une_vente_moins_chere_que_la_reference_coute_AUSSI():
    """Le signe ne dépend pas du sens : positif = défavorable, toujours."""
    assert shortfall_bps(100.0, 99.95, Side.SHORT) == pytest.approx(5.0)


def test_un_fill_favorable_est_negatif_dans_les_deux_sens():
    assert shortfall_bps(100.0, 99.95, Side.LONG) == pytest.approx(-5.0)
    assert shortfall_bps(100.0, 100.05, Side.SHORT) == pytest.approx(-5.0)


def test_sans_ecart_le_shortfall_est_exactement_zero():
    for sens in (Side.LONG, Side.SHORT):
        assert shortfall_bps(100.0, 100.0, sens) == 0.0


def test_sans_reference_le_shortfall_est_INCONNU_pas_nul():
    """Un zéro se lit « exécution parfaite ». Une référence absente n'est pas ça."""
    assert shortfall_bps(None, 100.0, Side.LONG) is None
    assert shortfall_bps(0.0, 100.0, Side.LONG) is None
    assert shortfall_bps(-1.0, 100.0, Side.LONG) is None


# ── LA règle : le shortfall est descriptif, jamais une charge ───────────────

def test_le_shortfall_ne_se_retranche_PAS_du_pnl():
    """Référence 100, exécution 100,05, commission 1 $ sur 10 titres.

    Le portefeuille sort 10 × 100,05 + 1 = 1 001,50 $. PAS 1 001,50 + 0,50 : les
    0,50 $ de slippage SONT les 10 × 0,05 déjà payés dans le prix.
    """
    f = _fill(fill_price=100.05, commission=1.0)
    assert f.notional == pytest.approx(1000.5)
    assert f.charge == pytest.approx(1.0)            # la commission SEULE
    assert f.cout_total_portefeuille == pytest.approx(1001.5)


def test_le_shortfall_reste_RENSEIGNE_meme_s_il_n_est_pas_une_charge():
    """Descriptif ne veut pas dire absent : on doit pouvoir le lire et le publier."""
    f = _fill(fill_price=100.05, commission=1.0)
    assert f.shortfall_bps == pytest.approx(5.0)
    assert f.shortfall_amount == pytest.approx(0.5)


def test_la_charge_ignore_le_shortfall_quel_qu_il_soit():
    """Sabotage : un shortfall énorme ne doit RIEN changer à la charge."""
    petit = _fill(fill_price=100.01, commission=2.0, fees_other=0.5)
    enorme = _fill(fill_price=180.0, commission=2.0, fees_other=0.5)
    assert petit.charge == enorme.charge == pytest.approx(2.5)


def test_les_frais_autres_SONT_une_charge():
    assert _fill(commission=1.0, fees_other=0.28).charge == pytest.approx(1.28)


# ── construction depuis un ordre ────────────────────────────────────────────

def test_fill_de_l_ordre_calcule_le_shortfall_et_marque_la_source():
    o = Order("QQQ", Side.LONG, 10.0, OrderType.MARKET)
    f = fill_de_l_ordre(o, reference_price=100.0, fill_price=100.05, commission=1.0)
    assert f.instrument == "QQQ" and f.qty == 10.0
    assert f.shortfall_bps == pytest.approx(5.0)
    assert f.source == "estimated"


def test_une_source_observee_se_declare():
    o = Order("BTC/USD", Side.LONG, 1.0, OrderType.MARKET)
    f = fill_de_l_ordre(o, reference_price=100.0, fill_price=101.0,
                        commission=0.1, source="observed")
    assert f.source == "observed"


def test_une_source_inconnue_est_REFUSEE():
    """Deux valeurs, pas trois : « observed » ou « estimated ». Rien d'autre ne doit
    pouvoir se glisser silencieusement entre les deux."""
    o = Order("QQQ", Side.LONG, 1.0, OrderType.MARKET)
    with pytest.raises(ValueError):
        fill_de_l_ordre(o, reference_price=100.0, fill_price=100.0, source="peut-être")


# ── le broker simulé émet des fills ─────────────────────────────────────────

def test_le_broker_simule_emet_un_fill_par_ordre():
    b = SimBroker(cash=100_000.0, costs=CostModel(fee_bps=5.0, slippage_bps=2.0))
    b.mark("QQQ", 100.0)
    b.submit(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET))
    assert len(b.fills) == 1
    assert b.fills[0].instrument == "QQQ" and b.fills[0].side is Side.LONG


def test_le_shortfall_du_broker_EGALE_le_slippage_de_son_modele():
    """Une seule définition : si les deux divergent, l'une des deux est fausse."""
    b = SimBroker(cash=100_000.0, costs=CostModel(fee_bps=0.0, slippage_bps=7.0))
    b.mark("QQQ", 100.0)
    b.submit(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET))
    assert b.fills[0].shortfall_bps == pytest.approx(7.0)


def test_la_somme_des_charges_EGALE_les_frais_du_broker():
    b = SimBroker(cash=100_000.0,
                  costs=CostModel(fee_bps=5.0, slippage_bps=2.0))
    for sym, px in (("QQQ", 100.0), ("SPY", 50.0)):
        b.mark(sym, px)
        b.submit(Order(sym, Side.LONG, 10.0, OrderType.MARKET))
    assert sum(f.charge for f in b.fills) == pytest.approx(b.fees_paid)


def test_le_cash_du_broker_est_reconcilie_par_les_fills():
    """La variation de cash s'explique ENTIÈREMENT par notionnel + charge."""
    b = SimBroker(cash=100_000.0,
                  costs=CostModel(fee_bps=5.0, slippage_bps=2.0))
    b.mark("QQQ", 100.0)
    b.submit(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET))
    f = b.fills[0]
    assert 100_000.0 - b.cash == pytest.approx(f.notional + f.charge)


def test_un_ordre_refuse_n_emet_AUCUN_fill():
    """Pas de prix connu → rejet. Un rejet n'est pas une exécution à coût nul."""
    b = SimBroker(cash=100_000.0)
    b.submit(Order("INCONNU", Side.LONG, 1.0, OrderType.MARKET))
    assert b.fills == []


def test_un_retry_idempotent_n_emet_pas_un_SECOND_fill():
    """Le garde-fou d'idempotence existait pour le cash. Il doit valoir pour les coûts :
    un retry qui re-facturerait la commission inventerait une charge."""
    b = SimBroker(cash=100_000.0, costs=CostModel(fee_bps=5.0, slippage_bps=2.0))
    b.mark("QQQ", 100.0)
    for _ in range(3):
        b.submit(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET, client_id="abc"))
    assert len(b.fills) == 1
