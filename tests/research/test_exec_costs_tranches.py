"""Une entrée ne doit compter qu'UNE fois, même vendue en plusieurs tranches.

Les tranches d'une vente (`-X1`, `-R1`, …) héritent du prix d'entrée ET du
`decision_price` de leur lot parent : `dataclasses.replace` les recopie. Compter chaque
enregistrement revenait donc à compter le même événement d'entrée N fois.

Mesuré le 10/09 sur le journal réel : ce biais faisait passer le slippage moyen de
−0,16 à +11,97 bps — un signe inversé sur la foi d'un seul lot soldé en six fois.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.exec_costs import measured_slippage

_T0 = datetime(2026, 7, 7, tzinfo=UTC)


class _Journal:
    def __init__(self, trades): self._t = trades
    def all(self, legacy=False): return self._t


def _t(tid: str, *, entree: float, decision: float) -> TradeRecord:
    return TradeRecord(
        id=tid, instrument="AAVE/USDC", asset_class=AssetClass.CRYPTO, venue="Alpaca",
        side=Side.LONG, qty=1.0, entry_ts=_T0, entry_price=entree, avg_price=entree,
        features_snapshot={"decision_price": decision})


def test_les_tranches_d_un_lot_comptent_pour_UNE_observation():
    normaux = [_t(f"L{i}", entree=100.0, decision=100.0) for i in range(25)]
    tranches = [_t(f"AAVE-R{n}", entree=105.0, decision=100.0) for n in range(1, 7)]
    st = measured_slippage(_Journal(normaux + tranches))
    assert st["n"] == 26, "les 6 tranches doivent peser 1, pas 6"


def test_le_biais_mesure_le_10_09_disparait():
    """Le cas réel, reproduit : un lot très défavorable soldé en 6 fois, noyé dans des
    fills sains. Compté 6 fois, il retourne le signe de la moyenne ; compté 1 fois,
    la moyenne redevient négative — exactement ce qu'on a observé (+11,97 → −0,16)."""
    sains = [_t(f"L{i}", entree=99.9, decision=100.0) for i in range(60)]  # −10 bps
    lot = [_t(f"AAVE-R{n}", entree=105.77, decision=100.0) for n in range(1, 7)]
    tous = sains + lot

    brut = [(t.entry_price / t.features_snapshot["decision_price"] - 1) * 1e4
            for t in tous]
    assert sum(brut) / len(brut) > 0, "sans regroupement, la moyenne est positive"

    st = measured_slippage(_Journal(tous))
    assert st["n"] == 61, "6 tranches → 1 observation"
    assert st["mean_bps"] < 0, "avec regroupement, le signe s'inverse"


def test_le_lot_de_BASE_et_ses_tranches_ne_font_qu_un():
    base = [_t("AAVE", entree=105.0, decision=100.0)]
    tranches = [_t(f"AAVE-R{n}", entree=105.0, decision=100.0) for n in range(1, 4)]
    autres = [_t(f"L{i}", entree=100.0, decision=100.0) for i in range(20)]
    assert measured_slippage(_Journal(base + tranches + autres))["n"] == 21


def test_un_journal_sans_tranche_est_INCHANGE():
    """Garde-fou : le regroupement ne doit rien retirer à un journal sain."""
    droits = [_t(f"L{i}", entree=100.5, decision=100.0) for i in range(30)]
    assert measured_slippage(_Journal(droits))["n"] == 30
