"""Réconciliation du journal : apparier aux fills RÉELS, ne jamais inventer une sortie.

Le plan est testé SÉPARÉMENT de son application — c'est ce qui permet de le relire avant
de toucher au registre, et c'est aussi ce qui rend ces tests possibles sans base ni
courtier.
"""

from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from scripts.reconcilier_journal import _plan


def _lot(sym: str, qty: float, prix: float, jour: int = 1) -> TradeRecord:
    """Un VRAI TradeRecord : `_close_record` en dérive un enregistrement fermé par
    `dataclasses.replace`, donc un objet factice trop maigre ferait passer les tests
    du plan et échouer ceux de l'écriture — exactement ce qui s'est produit."""
    return TradeRecord(
        id=f"{sym}-{jour}", instrument=sym, asset_class=AssetClass.EQUITY,
        venue="Alpaca", side=Side.LONG, qty=qty,
        entry_ts=datetime(2026, 8, jour, tzinfo=UTC),
        entry_price=prix, avg_price=prix)


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


# ── Écriture : le drapeau et l'identité doivent survivre ─────────────────────────

class JournalFactice:
    """Journal minimal en mémoire, qui reproduit l'UPSERT sur `id` du vrai."""

    def __init__(self, lots):
        self.lots = {t.id: (t, False) for t in lots}
        self.ecritures = []

    def all(self, *, legacy=None):
        if legacy is None:
            return [t for t, _ in self.lots.values()]
        return [t for t, lg in self.lots.values() if lg == legacy]

    def append(self, trade, *, legacy=False):
        self.ecritures.append((trade.id, legacy))
        self.lots[trade.id] = (trade, legacy)          # UPSERT : même id → écrase


def test_la_fermeture_d_un_lot_legacy_reste_legacy():
    """Sinon on assainit le registre en polluant le chiffre qu'on veut assainir.

    Un fill importé n'a jamais eu de features de décision : sa fermeture n'a rien à
    faire dans les statistiques affichées, qui portent sur des décisions évaluables.
    """
    from scripts.reconcilier_journal import _appliquer
    lot = _lot("AAPL", 10.0, 200.0)
    j = JournalFactice([lot])
    ventes = [{"symbol": "AAPL", "qty": 10.0, "price": 250.0, "date": "2026-08-15"}]
    fermetures, _ = _plan([lot], ventes)
    _appliquer(j, fermetures, ids_vivants=set())        # le lot n'est PAS non-legacy
    assert all(lg is True for _, lg in j.ecritures)


def test_la_fermeture_d_un_lot_vivant_reste_vivante():
    from scripts.reconcilier_journal import _appliquer
    lot = _lot("AAPL", 10.0, 200.0)
    j = JournalFactice([lot])
    ventes = [{"symbol": "AAPL", "qty": 10.0, "price": 250.0, "date": "2026-08-15"}]
    fermetures, _ = _plan([lot], ventes)
    _appliquer(j, fermetures, ids_vivants={lot.id})
    assert all(lg is False for _, lg in j.ecritures)


def test_deux_ventes_partielles_ne_se_marchent_pas_dessus():
    """LE défaut du 03/09 : les deux scissions portaient l'id `-R1`, donc l'UPSERT
    n'en gardait qu'une et une fermeture disparaissait sans bruit."""
    from scripts.reconcilier_journal import _appliquer
    lot = _lot("QQQ", 100.0, 400.0)
    j = JournalFactice([lot])
    ventes = [{"symbol": "QQQ", "qty": 30.0, "price": 600.0, "date": "2026-08-10"},
              {"symbol": "QQQ", "qty": 40.0, "price": 650.0, "date": "2026-08-20"}]
    fermetures, _ = _plan([lot], ventes)
    assert len(fermetures) == 2
    _appliquer(j, fermetures, ids_vivants={lot.id})
    suffixes = [i for i, _ in j.ecritures if "-R" in i]
    assert len(set(suffixes)) == len(suffixes)          # aucun id en double
