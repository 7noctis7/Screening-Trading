"""Commission ESTIMÉE en production — un modèle documenté, jamais présenté comme un fait.

Le courtier ne publie pas ses frais dans les réponses que lit `run_live`. Deux mauvaises
réponses : écrire `0.0` (mensonge) ou `None` (muet). La troisième est d'écrire
l'estimation du barème ET de la marquer `estimated`, pour qu'aucun lecteur ne la
confonde plus tard avec un chiffre observé.

L'estimation N'INCLUT PAS le slippage : il est déjà dans les prix de fill. C'est la même
règle que `Fill.charge`, appliquée à l'estimateur.
"""

from __future__ import annotations

import pytest

from packages.execution.costs import BROKER_FEES, broker_charge, broker_fee


def test_la_charge_estimee_EXCLUT_le_slippage():
    """`broker_fee` inclut le slippage (coût total attendu). `broker_charge` ne garde
    que ce qui se DÉBITE en plus du prix — sinon on compterait deux fois."""
    n = 10_000.0
    b = BROKER_FEES["bitmart"]
    attendu_slippage = n * b["slippage_bps"] / 1e4
    assert broker_fee("crypto", n) - broker_charge("crypto", n) == pytest.approx(
        attendu_slippage)


def test_un_courtier_sans_commission_a_une_charge_nulle_a_l_ACHAT():
    """Alpaca actions : 0 commission, et le réglementaire ne frappe qu'à la vente."""
    assert broker_charge("equity", 10_000.0, side="BUY") == 0.0


def test_le_reglementaire_frappe_a_la_VENTE_seulement():
    """SEC/TAF : obligatoire sur actions US même chez un courtier « 0 commission »."""
    vente = broker_charge("equity", 10_000.0, side="SELL")
    assert vente > 0.0
    assert vente == pytest.approx(10_000.0 * BROKER_FEES["alpaca"]["reg_bps"] / 1e4)


def test_le_crypto_paie_une_vraie_commission_dans_les_DEUX_sens():
    for sens in ("BUY", "SELL"):
        assert broker_charge("crypto", 10_000.0, side=sens) == pytest.approx(
            10_000.0 * BROKER_FEES["bitmart"]["commission_bps"] / 1e4)


def test_le_minimum_par_ordre_domine_les_petits_ordres(monkeypatch):
    """IBKR : 1 $ minimum. Sur 100 $ de notionnel, c'est le minimum qui s'applique."""
    monkeypatch.setenv("QUANT_BROKER_EQUITY", "ibkr")
    assert broker_charge("equity", 100.0, side="BUY") == pytest.approx(1.0)


def test_un_notionnel_nul_ne_facture_RIEN():
    """Un ordre sans notionnel n'a pas de minimum à payer — il n'a pas eu lieu."""
    assert broker_charge("equity", 0.0) == 0.0
    assert broker_charge("crypto", 0.0) == 0.0


# ── le journal doit porter la MARQUE, et migrer sans casser l'existant ──────

def test_le_journal_MIGRE_une_base_ancienne_sans_la_casser(tmp_path):
    """`journal.db` en production a été créé AVANT `fees_source`. Le schéma ne fait que
    `CREATE TABLE IF NOT EXISTS` : sans migration, tout INSERT échouerait sur une base
    existante — et la journalisation de production s'arrêterait silencieusement."""
    import sqlite3
    from datetime import UTC, datetime

    from packages.core.models import AssetClass, Side, TradeRecord
    from packages.storage.journal_sqlite import SqliteTradeJournal

    base = tmp_path / "ancien.db"
    con = sqlite3.connect(base)
    con.executescript("""
        CREATE TABLE trades (
            id TEXT PRIMARY KEY, instrument TEXT NOT NULL, asset_class TEXT NOT NULL,
            venue TEXT NOT NULL, side TEXT NOT NULL, qty REAL NOT NULL,
            entry_ts TEXT NOT NULL, entry_price REAL NOT NULL, avg_price REAL NOT NULL,
            exit_ts TEXT, exit_price REAL, fees REAL DEFAULT 0, slippage REAL DEFAULT 0,
            entry_reason TEXT DEFAULT '', exit_reason TEXT DEFAULT '', regime TEXT,
            strategy TEXT, features_snapshot TEXT DEFAULT '{}', pnl_gross REAL,
            pnl_net REAL, pnl_pct REAL, r_multiple REAL, is_win INTEGER,
            duration_s REAL, mfe REAL, mae REAL,
            legacy INTEGER NOT NULL DEFAULT 0, ingested_at TEXT NOT NULL);""")
    con.commit(); con.close()

    j = SqliteTradeJournal(base)                       # doit migrer, pas exploser
    j.append(TradeRecord(id="t1", instrument="QQQ", asset_class=AssetClass.EQUITY,
                         venue="Alpaca", side=Side.LONG, qty=1.0,
                         entry_ts=datetime(2026, 9, 10, tzinfo=UTC),
                         entry_price=100.0, avg_price=100.0,
                         fees=1.25, fees_source="estimated"))
    relu = j.all()[0]
    assert relu.fees == pytest.approx(1.25)
    assert relu.fees_source == "estimated"


def test_l_ouverture_de_production_ESTIME_et_le_MARQUE():
    from packages.execution.live_journal import build_open
    tr = build_open("BTC/USDC", venue="Alpaca", asset_class="crypto",
                    fill={"avg_price": 100.0, "qty": 50.0}, features={})
    assert tr is not None
    assert tr.fees is not None and tr.fees > 0, "le crypto paie une vraie commission"
    assert tr.fees_source == "estimated", "une estimation non marquée devient un fait"
    assert tr.slippage is None, "le slippage n'est pas estimable sans prix de référence"


def test_une_action_chez_un_courtier_sans_commission_estime_ZERO_et_le_MARQUE():
    """Zéro estimé n'est pas zéro inconnu : la marque fait toute la différence."""
    from packages.execution.live_journal import build_open
    tr = build_open("QQQ", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 100.0, "qty": 10.0}, features={})
    assert tr is not None and tr.fees == 0.0 and tr.fees_source == "estimated"
