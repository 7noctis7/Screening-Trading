"""`pnl_net` doit mériter son nom — et ne retrancher le coût qu'UNE fois.

Avant ce test, `pnl_net` valait `(prix de sortie − prix d'entrée) × qty` : le slippage y
était (il est dans les prix) mais **pas la commission**, débitée du cash du broker et
jamais imputée au trade. Le P&L journalisé était donc BRUT de commission, sous un nom
qui affirmait le contraire.

Le test de sabotage est `test_le_slippage_seul_ne_change_PAS_le_pnl_net` : avec une
commission nulle et un slippage énorme, `pnl_net` doit rester égal à `pnl_gross`. Il
tombe dès que quelqu'un retranche le shortfall une seconde fois.
"""

from __future__ import annotations

import pytest

from packages.core.models import Order, OrderType, Side
from packages.execution.costs import CostModel
from packages.execution.fills import charge_du_roundtrip
from packages.execution.sim_broker import SimBroker


def _aller_retour(fee_bps: float, slippage_bps: float, prix_sortie: float = 110.0):
    """Un aller-retour complet sur le broker simulé → (fill_entrée, fill_sortie)."""
    b = SimBroker(cash=100_000.0,
                  costs=CostModel(fee_bps=fee_bps, slippage_bps=slippage_bps))
    b.mark("QQQ", 100.0)
    b.submit(Order("QQQ", Side.LONG, 10.0, OrderType.MARKET))
    b.mark("QQQ", prix_sortie)
    b.submit(Order("QQQ", Side.SHORT, 10.0, OrderType.MARKET))
    return b, b.fills[0], b.fills[1]


def test_la_charge_d_un_aller_retour_somme_les_DEUX_jambes():
    b, entree, sortie = _aller_retour(fee_bps=5.0, slippage_bps=0.0)
    assert charge_du_roundtrip(entree, sortie) == pytest.approx(
        entree.commission + sortie.commission)
    assert charge_du_roundtrip(entree, sortie) == pytest.approx(b.fees_paid)


def test_une_jambe_MANQUANTE_rend_None_jamais_zero():
    """Un fill absent n'est pas un fill gratuit — c'est un fill qu'on n'a pas."""
    _, entree, sortie = _aller_retour(fee_bps=5.0, slippage_bps=0.0)
    assert charge_du_roundtrip(entree, None) is None
    assert charge_du_roundtrip(None, sortie) is None
    assert charge_du_roundtrip(None, None) is None


def test_sans_commission_la_charge_est_nulle_et_MESUREE():
    """Zéro mesuré ≠ zéro par défaut : la distinction est tout l'objet de P0-1."""
    _, entree, sortie = _aller_retour(fee_bps=0.0, slippage_bps=3.0)
    assert charge_du_roundtrip(entree, sortie) == 0.0


def test_le_slippage_seul_ne_change_PAS_le_pnl_net():
    """SABOTAGE. Commission nulle, slippage énorme : le shortfall est déjà dans les
    prix de fill, donc `pnl_net` doit rester exactement `pnl_gross`."""
    _, entree, sortie = _aller_retour(fee_bps=0.0, slippage_bps=200.0)
    pnl_gross = (sortie.fill_price - entree.fill_price) * entree.qty
    charge = charge_du_roundtrip(entree, sortie)
    assert charge == 0.0
    assert pnl_gross - charge == pytest.approx(pnl_gross)
    # et le shortfall reste RENSEIGNÉ — descriptif, pas absent
    assert entree.shortfall_bps == pytest.approx(200.0)


def test_la_commission_CREUSE_l_ecart_entre_brut_et_net():
    _, entree, sortie = _aller_retour(fee_bps=10.0, slippage_bps=0.0)
    pnl_gross = (sortie.fill_price - entree.fill_price) * entree.qty
    pnl_net = pnl_gross - charge_du_roundtrip(entree, sortie)
    assert pnl_net < pnl_gross
    assert pnl_gross - pnl_net == pytest.approx(entree.commission + sortie.commission)


def test_le_cash_du_broker_reconcilie_l_aller_retour():
    """La variation de cash s'explique par le P&L net, au centime."""
    b, entree, sortie = _aller_retour(fee_bps=10.0, slippage_bps=4.0)
    pnl_gross = (sortie.fill_price - entree.fill_price) * entree.qty
    pnl_net = pnl_gross - charge_du_roundtrip(entree, sortie)
    assert b.cash - 100_000.0 == pytest.approx(pnl_net)
