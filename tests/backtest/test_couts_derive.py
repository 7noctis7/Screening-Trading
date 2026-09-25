"""QML-013 — `preset_backtest` facture le turnover RÉEL, à la convention du rejeu.

Deux défauts de sens opposés, corrigés ensemble pour ne pas choisir celui qui arrange :
  * l'aller-retour (`round_trip_bps`) était facturé sur CHAQUE jambe de |Δw| — un achat et
    une vente comptés deux allers-retours : double comptage ;
  * le turnover se mesurait contre les poids CIBLES du pas précédent, alors que le
    portefeuille détenu avait DÉRIVÉ avec les prix : turnover sous-estimé.
Convention commune désormais (rejeu, ledger) : coût ALLER SIMPLE × |poids cible − poids détenu|.
"""

import numpy as np
import pytest


def test_les_poids_derivent_avec_les_prix():
    from packages.backtest.preset_core import deriver
    w = np.array([0.5, 0.3])                      # 20 % de cash
    d = deriver(w, np.array([0.10, -0.10]))
    valeur = 0.2 + 0.5 * 1.1 + 0.3 * 0.9
    assert d == pytest.approx([0.5 * 1.1 / valeur, 0.3 * 0.9 / valeur])


def test_rendements_nuls_poids_inchanges():
    from packages.backtest.preset_core import deriver
    w = np.array([0.4, 0.4])
    assert deriver(w, np.zeros(2)) == pytest.approx(w)


def test_cout_aller_simple():
    from packages.backtest.preset_core import couts_univers
    from packages.execution.costs import CostModel
    rt = couts_univers(["A"], {"A": "equity"})
    assert rt[0] == pytest.approx(CostModel.for_asset_class("equity").round_trip_bps / 2e4)
