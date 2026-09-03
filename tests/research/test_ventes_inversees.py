"""Une vente écrite à l'endroit d'une entrée : ce qu'on a le droit de retirer.

Ces tests verrouillent la seule chose qui rend un outil de RETRAIT acceptable : qu'il
ne retire que ce qu'une preuve désigne, et qu'il emporte la preuve avec la ligne.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.ventes_inversees import (
    archive,
    lots_a_annuler,
    signature,
    ventes_du_courtier,
)


def _lot(sym, qty, prix, jour=23, ferme=False):
    return TradeRecord(
        id=f"LEG-{sym}-{jour}", instrument=sym, asset_class=AssetClass.EQUITY,
        venue="Alpaca", side=Side.LONG, qty=qty,
        entry_ts=datetime(2026, 6, jour, tzinfo=UTC), entry_price=prix, avg_price=prix,
        exit_ts=datetime(2026, 7, 1, tzinfo=UTC) if ferme else None)


def _vente(sym, qty, prix, ident="v1"):
    return {"symbol": sym, "side": "sell", "qty": qty, "price": prix,
            "date": "2026-06-23T15:00:00Z", "id": ident}


def test_le_lot_qui_copie_une_vente_est_designe():
    """Le cas ICLN : lot « ouvert » de 301,600106 @ 20,83, jour et prix de la vente."""
    lot = _lot("ICLN", 301.600106, 20.83)
    ventes = ventes_du_courtier([_vente("ICLN", 301.600106, 20.83, "f-icln")])
    out = lots_a_annuler([lot], ventes)
    assert len(out) == 1
    assert out[0]["lot"].id == lot.id
    assert out[0]["fill"]["id"] == "f-icln"


def test_un_achat_reel_n_est_jamais_designe():
    """Même titre, même quantité, prix DIFFÉRENT : c'est une entrée."""
    lot = _lot("ICLN", 301.600106, 21.51)
    ventes = ventes_du_courtier([_vente("ICLN", 301.600106, 20.83)])
    assert lots_a_annuler([lot], ventes) == []


def test_une_quantite_differente_n_est_pas_designee():
    lot = _lot("ICLN", 300.0, 20.83)
    ventes = ventes_du_courtier([_vente("ICLN", 301.600106, 20.83)])
    assert lots_a_annuler([lot], ventes) == []


def test_un_lot_deja_ferme_est_hors_champ():
    """On ne retire que des lots OUVERTS : un round-trip fermé a sa contrepartie."""
    lot = _lot("ICLN", 301.600106, 20.83, ferme=True)
    ventes = ventes_du_courtier([_vente("ICLN", 301.600106, 20.83)])
    assert lots_a_annuler([lot], ventes) == []


def test_les_achats_du_courtier_ne_designent_rien():
    """Seuls les fills de VENTE peuvent désigner un lot. Un achat est une entrée."""
    achat = {"symbol": "ICLN", "side": "buy", "qty": 301.600106, "price": 20.83,
             "date": "2026-06-23", "id": "a1"}
    assert ventes_du_courtier([achat]) == {}
    assert lots_a_annuler([_lot("ICLN", 301.600106, 20.83)], {}) == []


def test_convention_de_nommage_differente_apparie_quand_meme():
    """« AVAX/USDC » au journal, « AVAXUSD » chez le courtier : même instrument."""
    lot = _lot("AVAX/USDC", 40.0, 20.0)
    ventes = ventes_du_courtier([_vente("AVAXUSD", 40.0, 20.0)])
    assert len(lots_a_annuler([lot], ventes)) == 1


def test_la_signature_tolere_les_arrondis_de_serialisation():
    """Au-delà de 4 décimales les deux sources divergent et rien ne s'apparierait."""
    assert signature("ICLN", 301.60001, 20.83000004) == signature("ICLN", 301.6, 20.83)


def test_l_archive_emporte_la_preuve():
    """Une ligne retirée sans la preuve qui l'a désignée n'est pas rejugeable."""
    lot = _lot("ICLN", 301.600106, 20.83)
    ventes = ventes_du_courtier([_vente("ICLN", 301.600106, 20.83, "f-icln")])
    ligne = archive(lots_a_annuler([lot], ventes)[0])
    assert ligne["id"] == lot.id
    assert ligne["qty"] == 301.600106
    assert ligne["preuve_vente"]["id"] == "f-icln"
    assert ligne["preuve_vente"]["date"] == "2026-06-23T15:00:00Z"
