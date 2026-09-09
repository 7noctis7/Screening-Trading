"""Le chemin de PRODUCTION ne doit plus écrire un coût nul qu'il n'a pas mesuré.

Un module qui passe ses tests unitaires mais n'est jamais atteint par le chemin réel
n'est pas terminé. Ces tests vérifient le CÂBLAGE : ce que la production écrit vraiment
dans le journal, et ce que ses sources s'interdisent d'écrire.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from packages.core.models import TradeRecord
from packages.execution.live_journal import build_open

RACINE = Path(__file__).resolve().parents[2]


def test_un_trade_neuf_a_des_frais_INCONNUS_pas_nuls():
    """Le défaut d'origine : `fees: float = 0.0` sur le dataclass. Tout trade créé sans
    coût explicite naissait donc « à frais nuls » — indiscernable d'une mesure."""
    t = TradeRecord(id="x", instrument="QQQ", asset_class="equity", venue="Alpaca",
                    side="long", qty=1.0, entry_ts=datetime(2026, 9, 9, tzinfo=UTC),
                    entry_price=100.0, avg_price=100.0)
    assert t.fees is None
    assert t.slippage is None


def test_l_ouverture_de_production_laisse_les_couts_NON_RENSEIGNES():
    tr = build_open("QQQ", venue="Alpaca", asset_class="equity",
                    fill={"avg_price": 100.0, "qty": 3.0}, features={"x": 1.0})
    assert tr is not None
    assert tr.fees is None, "la production a écrit un coût qu'elle n'a pas mesuré"
    assert tr.slippage is None


def test_la_fermeture_de_production_ne_retranche_PAS_le_slippage():
    """Sabotage de source. Le slippage est déjà dans les deux prix de fill : le
    retrancher de `pnl_net` compterait deux fois le même coût. Ce test tombe si
    quelqu'un ajoute cette soustraction."""
    chemin = RACINE / "packages" / "execution" / "live_roundtrip.py"
    src = chemin.read_text(encoding="utf-8")
    corps = src[src.index("def _close_record"):src.index("def close_sells")]
    # On ne juge que le CODE : un commentaire qui explique la règle a le droit de
    # nommer le slippage — c'est même souhaitable.
    code = [ligne for ligne in corps.splitlines()
            if ligne.strip() and not ligne.lstrip().startswith("#")]
    dans_docstring = False
    executables = []
    for ligne in code:
        if ligne.count('"""') == 1:
            dans_docstring = not dans_docstring
            continue
        if not dans_docstring:
            executables.append(ligne)
    assert not any("slippage" in x for x in executables), (
        "`_close_record` manipule le slippage : il est déjà dans les prix de fill")
    assert any("pnl_net=pnl" in x for x in executables), (
        "le P&L net de production a changé de forme — revérifier la règle")


def test_une_seule_formule_de_shortfall_dans_le_depot():
    """Trois modules calculaient déjà un écart prix/prix. P0-1 en fixe UNE. Ce test
    interdit d'en écrire une quatrième dans l'exécution."""
    exec_dir = RACINE / "packages" / "execution"
    coupables = []
    for f in exec_dir.glob("*.py"):
        if f.name in ("fills.py", "tca.py", "costs.py"):
            continue
        src = f.read_text(encoding="utf-8")
        if "1e4" in src and ("reference_price" in src or "arrival" in src):
            coupables.append(f.name)
    assert not coupables, f"formule de shortfall dupliquée dans {coupables}"
