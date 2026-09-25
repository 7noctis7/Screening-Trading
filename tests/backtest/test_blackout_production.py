"""QML-010 — le blackout post-choc AGIT en production et dans la courbe du tableau de bord.

`_erc_blackout` ne l'appliquait que s'il restait au moins `min_names` lignes. Or le panel de
production (`aligner_sans_trous`) contient EXACTEMENT `min_names` séries : le moindre titre
écarté faisait tomber sous le seuil, et le garde-fou ne se déclenchait jamais. Démontré le
25/09 : choc de +30 % en deux séances, poids inchangé à 10 %.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _panel(n=20, jours=600, graine=5):
    rng = np.random.default_rng(graine)
    d0 = datetime(2019, 1, 1, tzinfo=UTC)
    return {f"S{k:02d}": [Bar(f"S{k:02d}", "1d", d0 + timedelta(days=i), p, p, p, p, 1e6)
                          for i, p in enumerate(40 * np.exp(np.cumsum(
                              rng.normal(0.0003, 0.012, jours))))]
            for k in range(n)}


def _choc(data, sym, facteur=1.3):
    b = data[sym][-1]
    p = b.close * facteur
    data[sym] = data[sym][:-1] + [Bar(b.instrument, "1d", b.ts, p, p, p, p, 1e6)]


def test_un_choc_de_30_pct_met_le_poids_de_production_a_zero():
    from packages.backtest.preset_weights import preset_latest_weights_explique
    data = _panel()
    q = {s: float(i) for i, s in enumerate(sorted(data))}
    victime = sorted(q, key=q.get, reverse=True)[0]
    _choc(data, victime)
    w, _ = preset_latest_weights_explique(data, q, top_k=12, regime_gate=False,
                                          breadth_gate=False, min_weight=0.0)
    assert w.get(victime, 0.0) == 0.0


def test_le_blackout_ne_vide_pas_le_portefeuille():
    """Si le choc touchait plus de la moitié du panel, on garde l'ERC : un blackout qui
    viderait le portefeuille serait une sortie de marché, pas un filtre d'entrée."""
    from packages.backtest.preset_weights import _erc_blackout
    A = np.ones((4, 10))
    A[:3, -1] = 1.5                                       # 3 titres sur 4 en choc
    w = _erc_blackout(A, np.eye(4) * 0.04, 9, 0.12, 4)
    assert (w > 0).sum() == 4


def test_un_seul_titre_en_choc_est_ecarte_meme_si_le_panel_vaut_min_names():
    from packages.backtest.preset_weights import _erc_blackout
    A = np.ones((12, 10))
    A[0, -1] = 1.3
    w = _erc_blackout(A, np.eye(12) * 0.04, 9, 0.12, 12)
    assert w[0] == 0.0 and abs(w.sum() - 1.0) < 1e-12
