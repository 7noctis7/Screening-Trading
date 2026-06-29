"""Étude de régime — le Fear & Greed est-il un signal contrarian sur BTC ?

Hypothèse (contrarian, comme on FADE le funding) : peur extrême → acheter, avidité
extrême → vendre. On réutilise EXACTEMENT la machinerie funding_study :
  • z-score CAUSAL du F&G (fenêtre passée → anti look-ahead) ;
  • events |z|>seuil, direction = −signe(z) (fade) ;
  • CAR signé forward sur BTC + placebo (dates aléatoires) = H0.
Si l'effet réel ≈ placebo (p≥0,05), c'est du bruit → AUCUN câblage ML/décision.
C'est un TEST honnête, pas une promesse d'alpha (cf. 5 négatifs déjà publiés).
"""

from __future__ import annotations

import numpy as np

from packages.data.crypto_history import align
from packages.research.funding_study import significance, zscore_causal


def _returns(closes: list[float]) -> np.ndarray:
    """Rendements simples jour à jour (0 au premier point)."""
    c = np.asarray(closes, float)
    r = np.zeros_like(c)
    r[1:] = np.diff(c) / np.where(c[:-1] == 0, np.nan, c[:-1])
    return np.nan_to_num(r)


def run_fng_study(fng: list[tuple[str, float]], btc: list[tuple[str, float]],
                  post: int = 5, threshold: float = 1.5, window: int = 30,
                  n_sims: int = 1000, seed: int = 0) -> dict:
    """Aligne F&G ↔ prix BTC, teste le fade contrarian au gate placebo.

    `fng`, `btc` : [(date, valeur)] (cf. crypto_history). Retourne le dict de
    significance enrichi (verdict + métadonnées). available=False si trop court.
    """
    dates, fvals, closes = align(fng, btc)
    if len(dates) < window + post + 20:
        return {"available": False, "reason": "historique commun trop court",
                "n": len(dates)}
    rets = _returns(closes)
    fz = zscore_causal(fvals, window=window)
    res = significance(rets, fz, post=post, threshold=threshold,
                       n_sims=n_sims, seed=seed)
    res.update({"factor": "fear_greed_contrarian", "asset": "BTC",
                "n_days": len(dates), "start": dates[0], "end": dates[-1],
                "post": post, "threshold": threshold})
    if res.get("available"):
        res["verdict"] = "SIGNIFICATIF" if res.get("significant") else "BRUIT"
    return res
