"""Réconciliation du journal : apparier aux fills RÉELS, ne jamais inventer une sortie.

Le plan est testé SÉPARÉMENT de son application — c'est ce qui permet de le relire avant
de toucher au registre, et c'est aussi ce qui rend ces tests possibles sans base ni
courtier.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from scripts.reconcilier_journal import _plan


@dataclass
class Lot:
    id: str
    instrument: str
    qty: float
    entry_price: float
    entry_ts: datetime
    exit_ts: None = None


def _lot(sym: str, qty: float, prix: float, jour: int = 1) -> Lot:
    return Lot(f"{sym}-{jour}", sym, qty, prix,
               datetime(2026, 8, jour, tzinfo=UTC))


def test_une_vente_alpaca_ferme_un_lot_ecrit_sous_l_autre_convention():
    """LE défaut du 03/09 : lots en « AVAX/USDC », ventes en « AVAXUSD »."""
    lots = [_lot("AVAX/USDC", 40.0, 20.0)]
    ventes = [{"symbol": "AVAXUSD", "qty": 40.0, "price": 25.0, "date": "2026-08-15"}]
    fermetures, orphelins = _plan(lots, ventes)
    assert len(fermetures) == 1 and not orphelins
    assert fermetures[0]["prix"] == 25.0
    assert fermetures[0]["date"] == "2026-08-15"     # la date du FILL, pas ce jour


def test_un_lot_sans_vente_correspondante_reste_ouvert():
    """Le fermer « au dernier prix connu » fabriquerait un P&L qui n'a jamais existé."""
    lots = [_lot("AAPL", 47.0, 200.0)]
    fermetures, orphelins = _plan(lots, [])
    assert not fermetures
    assert [x.instrument for x in orphelins] == ["AAPL"]


def test_fifo_le_lot_le_plus_ancien_ferme_d_abord():
    vieux, recent = _lot("QQQ", 10.0, 400.0, jour=1), _lot("QQQ", 10.0, 500.0, jour=20)
    ventes = [{"symbol": "QQQ", "qty": 10.0, "price": 600.0, "date": "2026-08-25"}]
    fermetures, orphelins = _plan([vieux, recent], ventes)
    assert len(fermetures) == 1
    assert fermetures[0]["lot"].entry_price == 400.0     # le plus ancien
    assert orphelins[0].entry_price == 500.0


def test_une_vente_partielle_ne_ferme_que_sa_fraction():
    lots = [_lot("QQQ", 100.0, 400.0)]
    ventes = [{"symbol": "QQQ", "qty": 30.0, "price": 600.0, "date": "2026-08-25"}]
    fermetures, _ = _plan(lots, ventes)
    assert len(fermetures) == 1 and fermetures[0]["qty"] == 30.0


def test_une_vente_qui_depasse_les_lots_n_en_invente_aucun():
    """L'excédent correspond à des positions antérieures au journal : on l'ignore."""
    lots = [_lot("QQQ", 10.0, 400.0)]
    ventes = [{"symbol": "QQQ", "qty": 999.0, "price": 600.0, "date": "2026-08-25"}]
    fermetures, orphelins = _plan(lots, ventes)
    assert len(fermetures) == 1 and fermetures[0]["qty"] == 10.0
    assert not orphelins


def test_les_ventes_sont_appariees_dans_l_ordre_chronologique():
    """Sinon une vente tardive fermerait un lot que la précédente avait déjà soldé."""
    lots = [_lot("QQQ", 10.0, 400.0, jour=1), _lot("QQQ", 10.0, 450.0, jour=2)]
    ventes = [{"symbol": "QQQ", "qty": 10.0, "price": 700.0, "date": "2026-08-28"},
              {"symbol": "QQQ", "qty": 10.0, "price": 500.0, "date": "2026-08-10"}]
    fermetures, _ = _plan(lots, ventes)
    assert fermetures[0]["prix"] == 500.0            # la vente du 10 passe en premier
    assert fermetures[0]["lot"].entry_price == 400.0
