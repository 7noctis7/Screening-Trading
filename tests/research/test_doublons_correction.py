"""Doublons de fermeture — les six cas RÉELS (AVAX ×3, LINK ×2, LTC ×3) du 05/09
comme régression, plus les deux négatifs qui ont failli être mal classés.
"""
from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.doublons_correction import archive, identifier


def _t(ident: str, sym: str, qty: float, exit_date: str, exit_price: float, *,
       motif: str) -> TradeRecord:
    return TradeRecord(
        id=ident, instrument=sym, asset_class=AssetClass.CRYPTO, venue="Alpaca",
        side=Side.LONG, qty=qty,
        entry_ts=datetime(2026, 7, 7, tzinfo=UTC), entry_price=7.0, avg_price=7.0,
        exit_ts=datetime.fromisoformat(exit_date).replace(tzinfo=UTC),
        exit_price=exit_price, pnl_net=0.0,
        entry_reason="", exit_reason=motif)


# ── AVAX : 3 doublons réels (08-27, 08-28, 08-31), 2 non-doublons (09-01, 09-02) ──

def _avax():
    return [
        _t("C-AVAX-R2", "AVAX/USD", 106.849229, "2026-08-27", 7.4933,
           motif="reconciliation-journal:e7f3a341-f941-4640-9f7a-332e7127d816"),
        _t("P-AVAX-X1", "AVAX/USDC", 104.651712, "2026-08-27", 7.4933,
           motif="reconciliation paper (reduce/close)"),
        _t("C-AVAX-R3", "AVAX/USD", 121.487848, "2026-08-28", 7.2388,
           motif="reconciliation-journal:8368d6ac-22a5-4193-a38c-e996bb3ba759"),
        _t("P-AVAX-X2", "AVAX/USDC", 118.914420, "2026-08-28", 7.2388,
           motif="reconciliation paper (reduce/close)"),
        _t("C-AVAX-R4", "AVAX/USD", 109.714445, "2026-08-31", 7.2043,
           motif="reconciliation-journal:c6908e0a-f8ec-4ab6-8307-ee2925b5d93a"),
        _t("P-AVAX-X3", "AVAX/USDC", 107.366956, "2026-08-31", 7.2043,
           motif="reconciliation paper (reduce/close)"),
        # PAS des doublons : aucune correction nommée à ces dates.
        _t("P-AVAX-X4", "AVAX/USDC", 125.068355, "2026-09-01", 7.2070,
           motif="reconciliation paper (reduce/close)"),
        _t("P-AVAX-X5", "AVAX/USDC", 128.581908, "2026-09-02", 7.1621,
           motif="reconciliation paper (reduce/close)"),
        # PAS un doublon : les DEUX citent le MÊME uuid (multi-lot légitime).
        _t("C-AVAX-R1", "AVAX/USD", 124.753697, "2026-09-03", 7.5200,
           motif="reconciliation-journal:a9125983-90db-4db8-945f-8d4dd0cf9f9a"),
        _t("P-AVAX-09-03", "AVAX/USDC", 0.0, "2026-09-03", 7.5200,
           motif="reconciliation-journal:a9125983-90db-4db8-945f-8d4dd0cf9f9a"),
    ]


def test_avax_trois_doublons_reels_detectes():
    doublons = {d.doublon.id for d in identifier(_avax())}
    assert doublons == {"P-AVAX-X1", "P-AVAX-X2", "P-AVAX-X3"}


def test_avax_dates_sans_correction_nommee_non_signalees():
    doublons = {d.doublon.id for d in identifier(_avax())}
    assert "P-AVAX-X4" not in doublons and "P-AVAX-X5" not in doublons


def test_avax_meme_uuid_des_deux_cotes_non_signale():
    """Le piège LINK du 04/09 : deux enregistrements citant LE MÊME ordre ne sont
    pas un doublon, c'est une fermeture multi-lots légitime."""
    doublons = {d.doublon.id for d in identifier(_avax())}
    assert "P-AVAX-09-03" not in doublons


# ── LINK : 2 doublons réels (08-27, 08-28) ──

def test_link_deux_doublons_reels():
    trades = [
        _t("C-LINK-R3", "LINK/USD", 88.599799, "2026-08-27", 11.8420,
           motif="reconciliation-journal:7458ec87-adb8-4d37-acc0-0b50566418e5"),
        _t("P-LINK-X1", "LINK/USDC", 86.880314, "2026-08-27", 11.8420,
           motif="reconciliation paper (reduce/close)"),
        _t("C-LINK-R4", "LINK/USD", 76.822800, "2026-08-28", 11.3400,
           motif="reconciliation-journal:2cdf4931-24d2-46a6-adac-477ee8418e54"),
        _t("P-LINK-X2", "LINK/USDC", 75.353151, "2026-08-28", 11.3400,
           motif="reconciliation paper (reduce/close)"),
        # 08-31/09-01/09-02 : aucune correction nommée, pas des doublons.
        _t("P-LINK-X3", "LINK/USDC", 73.681089, "2026-08-31", 11.3510,
           motif="reconciliation paper (reduce/close)"),
    ]
    doublons = {d.doublon.id for d in identifier(trades)}
    assert doublons == {"P-LINK-X1", "P-LINK-X2"}


# ── LTC : 3 doublons réels (08-27, 08-28, 08-31) ──

def test_ltc_trois_doublons_reels():
    trades = [
        _t("C-LTC-R2", "LTC/USD", 17.427705, "2026-08-27", 49.8900,
           motif="reconciliation-journal:ce65b566-bb6b-4069-9e2e-e715fdc5cfdb"),
        _t("P-LTC-X1", "LTC/USDC", 17.046890, "2026-08-27", 49.8900,
           motif="reconciliation paper (reduce/close)"),
        _t("C-LTC-R3", "LTC/USD", 23.033444, "2026-08-28", 48.9200,
           motif="reconciliation-journal:67e88255-1e8e-4a43-af23-a769d373093d"),
        _t("P-LTC-X2", "LTC/USDC", 22.524361, "2026-08-28", 48.9200,
           motif="reconciliation paper (reduce/close)"),
        _t("C-LTC-R4", "LTC/USD", 20.945933, "2026-08-31", 48.4810,
           motif="reconciliation-journal:a9f51508-1c36-4cd9-8e30-2d6b2be4af4d"),
        _t("P-LTC-X3", "LTC/USDC", 20.497919, "2026-08-31", 48.4810,
           motif="reconciliation paper (reduce/close)"),
    ]
    doublons = {d.doublon.id for d in identifier(trades)}
    assert doublons == {"P-LTC-X1", "P-LTC-X2", "P-LTC-X3"}


# ── Négatifs génériques ──

def test_lots_encore_ouverts_ignores():
    t = TradeRecord(id="O", instrument="XYZ", asset_class=AssetClass.CRYPTO,
                    venue="Alpaca", side=Side.LONG, qty=1.0,
                    entry_ts=datetime(2026, 7, 7, tzinfo=UTC), entry_price=1.0,
                    avg_price=1.0, entry_reason="", exit_reason="")
    assert identifier([t]) == []


def test_deux_sans_nom_ne_produisent_aucun_doublon():
    """Sans correction NOMMÉE en face, un lot sans nom n'est jamais signalé —
    quel que soit son voisinage."""
    trades = [
        _t("A", "XYZ", 10.0, "2026-08-27", 5.0,
           motif="reconciliation paper (reduce/close)"),
        _t("B", "XYZ", 10.0, "2026-08-27", 5.0,
           motif="reconciliation paper (reduce/close)"),
    ]
    assert identifier(trades) == []


def test_prix_different_le_meme_jour_n_est_pas_un_doublon():
    trades = [
        _t("N", "XYZ", 10.0, "2026-08-27", 5.00,
           motif="reconciliation-journal:abc"),
        _t("S", "XYZ", 10.0, "2026-08-27", 5.50,   # prix différent
           motif="reconciliation paper (reduce/close)"),
    ]
    assert identifier(trades) == []


def test_chaque_doublon_apparie_une_seule_fois():
    """Un lot sans nom ne doit jamais être compté deux fois même si plusieurs
    corrections nommées existent le même jour pour le même symbole."""
    trades = [
        _t("N1", "XYZ", 5.0, "2026-08-27", 5.0, motif="reconciliation-journal:a"),
        _t("N2", "XYZ", 5.0, "2026-08-27", 5.0, motif="reconciliation-journal:b"),
        _t("S", "XYZ", 5.0, "2026-08-27", 5.0,
           motif="reconciliation paper (reduce/close)"),
    ]
    assert len(identifier(trades)) == 1


def test_archive_porte_les_deux_enregistrements():
    trades = _avax()
    d = identifier(trades)[0]
    a = archive(d)
    assert a["doublon"]["id"] == d.doublon.id
    assert a["correction_nommee"]["id"] == d.nomme.id
    assert a["doublon"]["exit_reason"] == "reconciliation paper (reduce/close)"
