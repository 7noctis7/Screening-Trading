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

from datetime import UTC, datetime

import pytest

from packages.core.models import Order, OrderType, Side
from packages.execution.costs import CostModel
from packages.execution.fills import charge_du_roundtrip
from packages.execution.sim_broker import SimBroker

_TS = datetime(2026, 9, 10, tzinfo=UTC)


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


# ── le broker et le journal doivent sortir au MÊME prix ─────────────────────

def _position_ouverte(costs: CostModel):
    """Une position longue de 10 titres à 100, prête à être fermée."""
    from packages.execution.fills import fill_produit
    from packages.storage.journal import TradeJournal
    b = SimBroker(cash=100_000.0, costs=costs)
    j = TradeJournal()
    b.mark("X", 100.0)
    b.submit(Order("X", Side.LONG, 10.0, OrderType.MARKET))
    # `entry_price` = le PRIX DE FILL, comme le fait la vraie boucle
    # (`open_t[s] = {"entry_price": pos.avg_price, ...}`) — pas le prix marqué.
    ot = {"entry_price": b.position("X").avg_price, "qty": 10.0, "entry_ts": _TS,
          "stop": 95.0, "target": 130.0,
          "reason": "test", "features": {}, "mfe": 0.0, "mae": 0.0,
          "hh": 100.0, "fill_entree": fill_produit(b, 0)}
    return b, j, ot, b.cash


def test_une_sortie_sur_STOP_encaisse_le_prix_du_STOP():
    """Mesuré le 10/09 : le journal sortait au stop (95) pendant que le broker
    encaissait la CLÔTURE de la barre (80) — 150 $ d'écart sur un seul trade, à coûts
    nuls. `_sortie` rend un prix de stop ou de cible, jamais la clôture ; `submit`
    encaissait au dernier prix marqué, qui est la clôture."""
    from packages.backtest.fast_swing import _close
    from packages.core.models import AssetClass
    costs = CostModel(fee_bps=0.0, slippage_bps=0.0)
    b, j, ot, cash_apres_achat = _position_ouverte(costs)
    b.mark("X", 80.0)                       # la barre clôture LOIN sous le stop
    _close(b, j, "X", ot, 95.0, _TS, "stop_hit", costs, 1, AssetClass.EQUITY)
    trade = j.all()[0]
    assert trade.exit_price == pytest.approx(95.0)
    assert b.cash - cash_apres_achat == pytest.approx(95.0 * 10.0)


def test_une_sortie_sur_CIBLE_encaisse_le_prix_de_la_CIBLE():
    from packages.backtest.fast_swing import _close
    from packages.core.models import AssetClass
    costs = CostModel(fee_bps=0.0, slippage_bps=0.0)
    b, j, ot, cash_apres_achat = _position_ouverte(costs)
    b.mark("X", 118.0)                      # la barre clôture SOUS la cible touchée
    _close(b, j, "X", ot, 130.0, _TS, "target_hit", costs, 1, AssetClass.EQUITY)
    assert b.cash - cash_apres_achat == pytest.approx(130.0 * 10.0)


def test_le_pnl_du_journal_EXPLIQUE_le_cash_du_broker():
    """Le contrôle qui compte : avec des coûts réels, la variation de cash sur
    l'aller-retour doit égaler le `pnl_net` journalisé, au centime."""
    from packages.backtest.fast_swing import _close
    from packages.core.models import AssetClass
    costs = CostModel(fee_bps=5.0, slippage_bps=2.0)
    b, j, ot, _ = _position_ouverte(costs)
    b.mark("X", 80.0)
    _close(b, j, "X", ot, 95.0, _TS, "stop_hit", costs, 1, AssetClass.EQUITY)
    assert b.cash - 100_000.0 == pytest.approx(j.all()[0].pnl_net, abs=1e-6)
