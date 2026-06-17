"""Risque factoriel par ACP (PCA) — décomposition systématique vs idiosyncratique.

Best practice (modèles type Barra/statistiques) : la majeure partie du risque d'un portefeuille
provient de quelques facteurs communs. L'ACP sur la matrice de covariance des rendements donne
la part de variance expliquée par les premiers facteurs (= risque systématique). Numpy pur.
"""

from __future__ import annotations

import numpy as np


def pca_risk(returns_by_asset: dict[str, list[float]], top: int = 3) -> dict:
    """% de variance expliquée par les premiers facteurs + concentration systématique."""
    syms = list(returns_by_asset)
    if len(syms) < 2:
        return {"available": False}
    n = min(len(v) for v in returns_by_asset.values())
    if n < 5:
        return {"available": False}
    M = np.array([returns_by_asset[s][-n:] for s in syms], dtype=float)
    cov = np.cov(M)
    vals = np.linalg.eigvalsh(cov)            # valeurs propres (croissantes, sym.)
    vals = np.clip(vals[::-1], 0, None)       # décroissantes, positives
    total = float(vals.sum()) or 1.0
    ratio = (vals / total)
    k = min(top, len(vals))
    return {"available": True, "n_assets": len(syms),
            "explained": [round(float(x), 4) for x in ratio[:k]],
            "systematic_pct": round(float(ratio[0]), 4),          # 1er facteur (marché)
            "top_k_pct": round(float(ratio[:k].sum()), 4),
            "effective_factors": round(float((ratio.sum() ** 2) / (ratio ** 2).sum()), 1)}
