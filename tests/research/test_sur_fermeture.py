"""Décomposition du manque — synthétique UNIQUEMENT pour valider l'arithmétique.

Les valeurs d'AVAX viennent du `diag-journal` RÉEL du 05/09 : c'est le cas que le
module doit savoir décomposer, pas un exemple inventé pour lui plaire.
"""
from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.sur_fermeture import (
    EcartSymbole,
    ordre_reference,
    par_ordre,
    par_symbole,
)


def _t(ident: str, sym: str, qty: float, *, ferme: str | None = None,
       motif: str = "") -> TradeRecord:
    return TradeRecord(
        id=ident, instrument=sym, asset_class=AssetClass.CRYPTO, venue="Alpaca",
        side=Side.LONG, qty=qty,
        entry_ts=datetime(2026, 7, 7, tzinfo=UTC), entry_price=7.0, avg_price=7.0,
        exit_ts=None if ferme is None
        else datetime.fromisoformat(ferme).replace(tzinfo=UTC),
        exit_price=None if ferme is None else 7.5,
        entry_reason="", exit_reason=motif)


def _vente(oid: str, sym: str, qty: float) -> dict:
    return {"id": oid, "symbol": sym, "side": "sell", "qty": qty}


def _achat(oid: str, sym: str, qty: float) -> dict:
    return {"id": oid, "symbol": sym, "side": "buy", "qty": qty}


def test_uuid_extrait_du_motif():
    assert ordre_reference("reconciliation-journal:e7f3a341-f941-4640") == \
        "e7f3a341-f941-4640"
    assert ordre_reference("reconciliation paper (reduce/close)") is None
    assert ordre_reference(None) is None


def test_plusieurs_lots_pour_une_vente_ne_sont_PAS_un_exces():
    """Le piège LINK du 04/09 : 125,613741 + 147,511643 = 273,125384, la quantité
    RÉELLE de l'ordre. FIFO multi-lots légitime — j'avais posé un P0 sans l'addition."""
    trades = [_t("C-LINK-R1", "LINK/USD", 125.613741, ferme="2026-07-08",
                 motif="reconciliation-journal:ee481ad2"),
              _t("P-LINK", "LINK/USDC", 147.511643, ferme="2026-07-08",
                 motif="reconciliation-journal:ee481ad2")]
    (e,) = par_ordre(trades, [_vente("ee481ad2", "LINK/USD", 273.12538382)])
    assert not e.surferme and abs(e.exces) < 1e-6
    assert len(e.lots) == 2                       # deux lots, une vente : normal


def test_exces_reel_est_signale():
    trades = [_t("A", "AVAX/USD", 100.0, ferme="2026-08-27",
                 motif="reconciliation-journal:abc"),
              _t("B", "AVAX/USDC", 60.0, ferme="2026-08-27",
                 motif="reconciliation-journal:abc")]
    (e,) = par_ordre(trades, [_vente("abc", "AVAX/USD", 150.0)])
    assert e.surferme and abs(e.exces - 10.0) < 1e-9


def test_sortie_sans_ordre_cite_n_est_imputee_a_rien():
    """`reconciliation paper (reduce/close)` ne nomme aucun fill : l'imputer d'office
    fabriquerait l'excédent qu'on cherche."""
    trades = [_t("X", "AVAX/USD", 999.0, ferme="2026-08-27",
                 motif="reconciliation paper (reduce/close)")]
    assert par_ordre(trades, [_vente("abc", "AVAX/USD", 1.0)]) == []


def test_decomposition_avax_du_05_09():
    """Chiffres RÉELS : acheté 1367,3599 · journal fermé 1089,2990 · ouvert 3,653247 ·
    le courtier détient 335,500501. Donc vendu = 1367,3599 − 335,500501."""
    vendu = 1367.3599 - 335.500501
    e = EcartSymbole(symbole="AVAX", achete=1367.3599, vendu=vendu,
                     ferme_journal=1089.2990, ouvert_journal=3.653247)
    assert abs(e.detenu_attendu - 335.500501) < 1e-6
    assert abs(e.manque_ouvert - 331.847254) < 1e-6      # l'écart du diag-journal
    assert abs(e.achats_non_journalises - 274.407653) < 1e-6
    assert abs(e.sur_fermeture - 57.439601) < 1e-6
    assert e.identite_verifiee()                     # les deux causes s'additionnent


def test_identite_se_referme_sur_des_valeurs_quelconques():
    """L'identité est algébrique : elle ne doit dépendre d'aucun jeu de chiffres."""
    for a, v, f, o in [(100, 40, 55, 5), (0, 0, 0, 0), (7.5, 9.25, 3.125, -1.0),
                       (1e6, 999_999.5, 12.25, 0.0)]:
        assert EcartSymbole("X", a, v, f, o).identite_verifiee()


def test_par_symbole_agrege_les_alias_du_meme_actif():
    """« AVAX/USDC », « AVAX-USD » et « AVAX/USD » sont le MÊME actif."""
    ordres = [_achat("1", "AVAX/USD", 800.0), _achat("2", "AVAX-USD", 567.3599),
              _vente("3", "AVAX/USDC", 1031.859399)]
    trades = [_t("f", "AVAX/USDC", 1089.2990, ferme="2026-08-27"),
              _t("o", "AVAX/USD", 3.653247)]
    (e,) = par_symbole(trades, ordres)
    assert abs(e.achete - 1367.3599) < 1e-9 and abs(e.sur_fermeture - 57.439601) < 1e-6
    assert e.identite_verifiee()
