"""Le livre contre QQQ + cash au MÊME drawdown ou à la MÊME volatilité.

POURQUOI. Battre QQQ nu ne prouve rien : la production réduit déjà son exposition quand
la volatilité monte (`packages/portfolio/contraintes.py`, DD-target du preset). Un
drawdown plus faible peut n'être que « moins investi ». La seule comparaison honnête
est un mélange α·QQQ + (1−α)·cash, rebalancé chaque jour, dont α est choisi pour que
son drawdown maximal (ou sa volatilité) égale celui du livre, sur les MÊMES dates.

Le cash est rémunéré à zéro, comme dans le rejeu : cela AVANTAGE le livre (le cash réel
rapporte le taux court) — le verdict est donc indulgent pour la stratégie.

VERDICT. Écart de rendement quotidien moyen (livre − mélange), annualisé, avec un
intervalle par bootstrap en BLOCS (les rendements sont autocorrélés) ; Sharpe déflaté
de cet écart par le nombre d'essais du registre. α ne peut pas dépasser 1 (aucun
levier) : si le livre a un drawdown plus profond que QQQ, α = 1 et c'est signalé.
"""

from __future__ import annotations

import numpy as np

BLOC = 20                     # ~1 mois de bourse
N_BOOT = 2000


def rendements(courbe) -> np.ndarray:
    c = np.asarray(courbe, float)
    return c[1:] / c[:-1] - 1.0


def max_drawdown(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + np.asarray(r, float))
    return float((eq / np.maximum.accumulate(eq) - 1.0).min()) if eq.size else 0.0


def alpha_meme_drawdown(r_livre: np.ndarray, r_qqq: np.ndarray,
                        iters: int = 60) -> float:
    """α ∈ [0, 1] tel que maxDD(α·QQQ) = maxDD(livre). Bissection (DD monotone en α)."""
    cible = max_drawdown(r_livre)
    if max_drawdown(r_qqq) >= cible:              # QQQ entier ne descend pas si bas
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if max_drawdown(mid * r_qqq) > cible:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def alpha_meme_vol(r_livre: np.ndarray, r_qqq: np.ndarray) -> float:
    sq = float(np.std(r_qqq, ddof=1))
    return float(min(1.0, np.std(r_livre, ddof=1) / sq)) if sq > 0 else 0.0


def _bootstrap_blocs(e: np.ndarray, n_boot: int, bloc: int, graine: int) -> np.ndarray:
    rng = np.random.default_rng(graine)
    n = e.size
    k = int(np.ceil(n / bloc))
    debuts = rng.integers(0, max(1, n - bloc + 1), size=(n_boot, k))
    idx = (debuts[:, :, None] + np.arange(bloc)[None, None, :]).reshape(n_boot, -1)
    idx = idx[:, :n]
    return e[idx].mean(axis=1)


def _dsr_ecart(e: np.ndarray, n_essais: int) -> float | None:
    from packages.portfolio.psr import deflated_sharpe_ratio
    sd = float(e.std(ddof=1))
    if sd <= 0 or e.size < 30:
        return None
    m3 = float(((e - e.mean()) ** 3).mean()) / sd ** 3
    m4 = float(((e - e.mean()) ** 4).mean()) / sd ** 4
    return float(deflated_sharpe_ratio(float(e.mean()) / sd, e.size, max(1, n_essais),
                                       skew=m3, kurt=m4))


def comparer(r_livre, r_qqq, *, n_essais: int, base: str = "drawdown",
             periodes_par_an: float = 252.0, graine: int = 0) -> dict:
    """Livre contre α·QQQ + cash, α calé sur le drawdown (défaut) ou la volatilité."""
    rl, rq = np.asarray(r_livre, float), np.asarray(r_qqq, float)
    n = min(rl.size, rq.size)
    rl, rq = rl[:n], rq[:n]
    if n < 60:
        return {"available": False, "status": "UNCALIBRATED", "n": int(n)}
    a = alpha_meme_drawdown(rl, rq) if base == "drawdown" else alpha_meme_vol(rl, rq)
    e = rl - a * rq
    boot = _bootstrap_blocs(e, N_BOOT, BLOC, graine) * periodes_par_an
    return {"available": True, "base": base, "alpha_qqq": a, "plafonne": a >= 1.0,
            "n_jours": int(n), "maxdd_livre": max_drawdown(rl),
            "maxdd_melange": max_drawdown(a * rq),
            "ecart_annualise": float(e.mean() * periodes_par_an),
            "ic95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "dsr_ecart": _dsr_ecart(e, n_essais), "n_essais": int(n_essais)}
