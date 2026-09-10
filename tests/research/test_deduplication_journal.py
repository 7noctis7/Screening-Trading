"""Déduplication du journal — supprimer SEULEMENT ce qui est prouvé redondant.

Le journal réel portait `P-20260707-Alpaca-AAVE/USDC`, `-R1` et `-R2` : trois lignes
pour un événement. `build_open` génère pourtant un identifiant DÉTERMINISTE
(`P-{jour}-{courtier}-{symbole}`) dont l'UPSERT rend le re-run idempotent — un script de
réparation ajoutait un suffixe et contournait cette garantie. Mesuré : 15 doublons sur
66, qui faisaient passer le slippage moyen de −0,16 à +11,97 bps.

RÈGLE FAIL-CLOSED. On ne supprime une ligne suffixée QUE si la ligne de BASE existe et
que leur économie est identique au centime. Au moindre écart — quantité, prix, date,
sortie — on garde tout et on le dit. Une réparation qui « nettoie » un lot légitime
détruit une position réelle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.deduplication import doublons_suffixes

_T0 = datetime(2026, 7, 7, tzinfo=UTC)


def _t(tid: str, *, qty: float = 10.0, prix: float = 88.98,
       sortie: float | None = None) -> TradeRecord:
    return TradeRecord(
        id=tid, instrument="AAVE/USDC", asset_class=AssetClass.CRYPTO, venue="Alpaca",
        side=Side.LONG, qty=qty, entry_ts=_T0, entry_price=prix, avg_price=prix,
        exit_ts=_T0 + timedelta(days=1) if sortie else None, exit_price=sortie)


def test_le_cas_reel_est_detecte():
    base = "P-20260707-Alpaca-AAVE/USDC"
    lot = [_t(base), _t(f"{base}-R1"), _t(f"{base}-R2")]
    d = doublons_suffixes(lot)
    assert sorted(d["supprimables"]) == [f"{base}-R1", f"{base}-R2"]
    assert d["conserves"] == [base]
    assert d["ambigus"] == []


def test_sans_ligne_de_BASE_on_ne_supprime_RIEN():
    """Le suffixé pourrait être la seule trace de la position. On ne l'efface pas."""
    d = doublons_suffixes([_t("P-20260707-Alpaca-AAVE/USDC-R1")])
    assert d["supprimables"] == []
    assert d["ambigus"] == ["P-20260707-Alpaca-AAVE/USDC-R1"]


def test_une_QUANTITE_differente_rend_le_doublon_AMBIGU():
    """Deux quantités = potentiellement deux vrais achats. On garde et on signale."""
    base = "P-20260707-Alpaca-AAVE/USDC"
    d = doublons_suffixes([_t(base, qty=10.0), _t(f"{base}-R1", qty=7.0)])
    assert d["supprimables"] == []
    assert d["ambigus"] == [f"{base}-R1"]


def test_un_PRIX_different_rend_le_doublon_AMBIGU():
    base = "P-20260707-Alpaca-AAVE/USDC"
    d = doublons_suffixes([_t(base, prix=88.98), _t(f"{base}-R1", prix=91.10)])
    assert d["supprimables"] == [] and d["ambigus"] == [f"{base}-R1"]


def test_une_SORTIE_differente_rend_le_doublon_AMBIGU():
    """Un suffixé fermé alors que la base est ouverte porte une information réelle."""
    base = "P-20260707-Alpaca-AAVE/USDC"
    d = doublons_suffixes([_t(base), _t(f"{base}-R1", sortie=95.0)])
    assert d["supprimables"] == [] and d["ambigus"] == [f"{base}-R1"]


def test_un_journal_SAIN_ne_propose_aucune_suppression():
    """Garde-fou : sans suffixe de réparation, rien ne doit s'allumer."""
    d = doublons_suffixes([_t("P-20260707-Alpaca-AAVE/USDC"),
                           _t("P-20260708-Alpaca-BTC/USDC")])
    assert d["supprimables"] == [] and d["ambigus"] == [] and d["conserves"] == []


def test_les_tranches_X_ne_sont_JAMAIS_touchees():
    """`-X1`, `-X2` sont des tranches légitimes d'une vente en plusieurs fois."""
    base = "P-20260707-Alpaca-AAVE/USDC"
    d = doublons_suffixes([_t(base), _t(f"{base}-X1"), _t(f"{base}-X2")])
    assert d["supprimables"] == [] and d["ambigus"] == []


# ── le script CLI : simulation par défaut, fail-closed ─────────────────────

def test_le_script_SIMULE_par_defaut(tmp_path, capsys, monkeypatch):
    """Aucune réparation de ce dépôt n'écrit sans qu'on le lui demande."""
    import sys
    from packages.storage.journal_sqlite import SqliteTradeJournal
    base = tmp_path / "j.db"
    j = SqliteTradeJournal(base)
    bid = "P-20260707-Alpaca-AAVE/USDC"
    j.append(_t(bid), legacy=False)
    j.append(_t(f"{bid}-R1"), legacy=False)
    avant = len(j.all(legacy=False))

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
    from scripts.dedupliquer_journal import main
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(base)])
    assert main() == 0
    assert "SIMULATION" in capsys.readouterr().out
    assert len(SqliteTradeJournal(base).all(legacy=False)) == avant


def test_le_script_APPLIQUE_et_sauvegarde(tmp_path, monkeypatch):
    import sys
    from packages.storage.journal_sqlite import SqliteTradeJournal
    base = tmp_path / "j.db"
    j = SqliteTradeJournal(base)
    bid = "P-20260707-Alpaca-AAVE/USDC"
    for suffixe in ("", "-R1", "-R2"):
        j.append(_t(f"{bid}{suffixe}"), legacy=False)

    from scripts.dedupliquer_journal import main
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(base), "--appliquer"])
    assert main() == 0
    restants = [t.id for t in SqliteTradeJournal(base).all(legacy=False)]
    assert restants == [bid], "la ligne de base doit survivre, les doublons partir"
    assert list(tmp_path.glob("j.avant-dedup-*.db")), "aucune sauvegarde écrite"
