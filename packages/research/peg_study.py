"""Déviation de peg des actions tokenisées (xStocks) — piste 0 €, sous le gate.

Idée : une action tokenisée (ex. AAPLx sur Solana/Bybit) suit son sous-jacent réel
(AAPL). L'écart token/sous-jacent (peg) reflète une pression d'arbitrage/stress.
Hypothèse testable : une déviation EXTRÊME revient vers 0 (mean-reversion) → on la FADE.

⚠️ HONNÊTETÉ : ce n'est PAS le flux institutionnel de l'action réelle (liquidité token
minuscule, flux d'arbitrage). Signal de peg, à valider au gate placebo avant tout
câblage. Réutilise funding_study.significance (même machinerie fade + placebo).
"""

from __future__ import annotations

import numpy as np

from packages.research.funding_study import significance, zscore_causal


def peg_deviation(token: float, underlying: float) -> float | None:
    """Écart relatif token/sous-jacent : >0 = prime (token cher), <0 = décote."""
    if not underlying or underlying <= 0 or token is None:
        return None
    return token / underlying - 1.0


def classify(dev: float | None, band: float = 0.005) -> str:
    """'prime' / 'décote' / 'aligné' selon une bande de tolérance (déf. 0,5 %)."""
    if dev is None:
        return "n/d"
    return "prime" if dev > band else "décote" if dev < -band else "aligné"


def run_study(token_prices: list[float], underlying_prices: list[float],
              post: int = 3, threshold: float = 1.5, n_sims: int = 1000,
              seed: int = 0) -> dict:
    """La déviation de peg extrême prédit-elle un retour du token ? (fade + placebo)

    `token_prices` et `underlying_prices` alignés (même horloge). Retourne le dict de
    significance + verdict. available=False si série trop courte.
    """
    n = min(len(token_prices), len(underlying_prices))
    if n < 40:
        return {"available": False, "reason": "série trop courte", "n": n}
    tok = np.asarray(token_prices[:n], float)
    und = np.asarray(underlying_prices[:n], float)
    dev = np.where(und > 0, tok / und - 1.0, 0.0)
    rets = np.zeros(n)
    rets[1:] = np.diff(tok) / np.where(tok[:-1] == 0, np.nan, tok[:-1])
    rets = np.nan_to_num(rets)
    z = zscore_causal(dev.tolist(), window=30)
    res = significance(rets, z, post=post, threshold=threshold,
                       n_sims=n_sims, seed=seed)
    if res.get("available"):
        res.update({"factor": "xstock_peg_reversion", "n_obs": n,
                    "verdict": "SIGNIFICATIF" if res.get("significant") else "BRUIT"})
    return res
