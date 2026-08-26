"""Univers ROULANT : le top-K est re-sélectionné à chaque rebalancement, pas figé au départ.

Motivation. L'univers du backtest est choisi UNE FOIS, au premier pas, par momentum. Sur onze
ans, un titre bien classé en 2015 reste dans le panier en 2026 même s'il a décroché — et un titre
devenu leader en 2020 n'y entre jamais. C'est un choix, pas une évidence : il réduit le turnover
et la sur-optimisation, mais il fige aussi la sélection.

⚠️ ANTI-FUITE — la seule chose qui compte ici. La sélection à `t` lit le momentum sur
`[t-253, t-1]`, donc STRICTEMENT avant `t` ; la mesure part de `entry = t + exec_lag` vers
`entry + step`. Les deux fenêtres ne se chevauchent JAMAIS.

Ce garde-fou n'est pas théorique : une première version de ce travail (25/08) mesurait le
rendement sur `[t-step, t]` — fenêtre INCLUSE dans celle du classement — et sortait un Sharpe
de +6,8 sur une MARCHE ALÉATOIRE PURE, où il n'y a rien à capturer. Le contrôle qui l'aurait
attrapé est dans `tests/backtest/test_rolling_prospectif.py` : Sharpe sur bruit pur ≈ 0.

Défaut : DÉSACTIVÉ. Aucun chiffre publié ne bouge tant que le gate du labo n'a pas tranché sur
données réelles.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.preset_config import momentum_rank
from packages.backtest.preset_core import _fwd, _gross_pas, _poids_pas


def poids_par_symbole(w: np.ndarray, universe: list) -> dict:
    """Vecteur de poids → {symbole: poids}. L'index n'a plus de sens quand l'univers tourne."""
    return {s: float(w[i]) for i, s in enumerate(universe) if abs(float(w[i])) > 1e-12}


def frottement(cible: dict, avant: dict, rt: dict) -> tuple[float, float]:
    """Coût et turnover sur l'UNION des symboles : une ligne qui sort de l'univers est vendue,
    et cette vente coûte — l'ignorer ferait payer la rotation gratuitement."""
    cout = turn = 0.0
    for s in set(cible) | set(avant):
        d = abs(cible.get(s, 0.0) - avant.get(s, 0.0))
        turn += d
        cout += d * rt.get(s, 0.0)
    return cout, turn


def appliquer_bande(cible: dict, avant: dict, band: float) -> dict:
    """Bande de non-trading, par SYMBOLE (l'univers change d'un pas à l'autre)."""
    if band <= 0 or not avant:
        return cible
    out = dict(cible)
    for s in set(cible) | set(avant):
        c, a = cible.get(s, 0.0), avant.get(s, 0.0)
        if abs(c - a) < band:
            out[s] = a
    return {s: v for s, v in out.items() if abs(v) > 1e-12}


def selection_rolling(M: dict, syms: list, t: int, top_k: int, lookback: int) -> list:
    """Top-K au pas `t`. Fenêtre `[t-253, t-1]` : strictement antérieure à `t` (cf. en-tête)."""
    return momentum_rank(M, syms, max(t, max(lookback, 50)), top_k)
