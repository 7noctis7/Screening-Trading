"""Matrice de corrélation + clustering hiérarchique (single-linkage) des positions.

But : éviter la FAUSSE diversification (plusieurs positions en fait très corrélées).
distance = 1 - |corr| ; on regroupe sous un seuil. Pur numpy + union-find.
"""

from __future__ import annotations

import numpy as np


def correlation_matrix(returns_by_symbol: dict[str, list[float]]) -> tuple[list[str], np.ndarray]:
    syms = list(returns_by_symbol)
    n = min((len(v) for v in returns_by_symbol.values()), default=0)
    if n < 2 or len(syms) < 2:
        return syms, np.eye(len(syms))
    M = np.array([returns_by_symbol[s][:n] for s in syms], float)
    return syms, np.corrcoef(M)


def _avg_offdiag(corr: np.ndarray) -> float:
    n = corr.shape[0]
    if n < 2:
        return float("nan")
    return float((corr.sum() - np.trace(corr)) / (n * (n - 1)))


def conditional_correlation(returns_by_symbol: dict[str, list[float]],
                            market: list[float], stress_quantile: float = 0.2) -> dict:
    """Corrélation moyenne inter-actifs en RÉGIME DE STRESS vs CALME.

    Stress = jours où le marché est dans sa pire queue (rendement ≤ `stress_quantile`).
    Démasque la FAUSSE diversification : si la corrélation BONDIT en stress, la
    diversification s'évapore quand on en a besoin. `breakdown=True` si Δ > 0,2.
    """
    syms = list(returns_by_symbol)
    if len(syms) < 2:
        return {"available": False}
    m = np.asarray(market, float)
    n = min([m.size] + [len(v) for v in returns_by_symbol.values()])
    if n < 10:
        return {"available": False}
    m = m[:n]
    stress = m <= np.quantile(m, stress_quantile)

    def corr_on(mask: np.ndarray) -> float:
        if int(mask.sum()) < 3:
            return float("nan")
        mat = np.array([np.asarray(returns_by_symbol[s][:n], float)[mask]
                        for s in syms])
        return _avg_offdiag(np.corrcoef(mat))

    cs, cc = corr_on(stress), corr_on(~stress)
    breakdown = cs == cs and cc == cc and (cs - cc) > 0.2
    return {
        "available": True,
        "avg_corr_stress": round(cs, 3) if cs == cs else None,
        "avg_corr_calm": round(cc, 3) if cc == cc else None,
        "n_stress": int(stress.sum()), "n_calm": int((~stress).sum()),
        "stress_quantile": stress_quantile,
        "diversification_breakdown": bool(breakdown),
    }


def cluster(symbols: list[str], corr: np.ndarray, threshold: float = 0.7) -> list[list[str]]:
    """Regroupe les actifs dont |corr| >= threshold (single-linkage via union-find)."""
    n = len(symbols)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr[i, j]) >= threshold:
                parent[find(i)] = find(j)
    groups: dict[int, list[str]] = {}
    for i, s in enumerate(symbols):
        groups.setdefault(find(i), []).append(s)
    return list(groups.values())
