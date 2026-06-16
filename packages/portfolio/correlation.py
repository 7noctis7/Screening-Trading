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
