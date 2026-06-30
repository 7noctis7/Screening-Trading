"""Cassure de canal technique (+ confirmation on-chain optionnelle) — testée au GATE.

Détecteur PUR : canal par régression linéaire causale (fenêtre passée → anti
look-ahead) ; cassure haussière = close > borne sup + (option) pic d'activité on-chain
(z-score > seuil). Puis test de significativité placebo : les cassures prédisent-elles
un rendement forward, ou est-ce du bruit ? Tant que p ≥ 0,05 → RIEN câblé au ML/décision
(discipline : 5 négatifs déjà publiés). numpy uniquement.
"""

from __future__ import annotations

import numpy as np


def channel_break(closes, win: int = 60, k: float = 2.0,
                  confirm=None, conf_z: float = 2.0) -> dict:
    """Cassure haussière à la DERNIÈRE barre depuis le canal des `win` barres passées.

    `confirm` : série on-chain alignée (ex. adresses actives) ; si fournie, la cassure
    doit AUSSI s'accompagner d'un z-score > `conf_z` (double confirmation).
    """
    c = np.asarray(closes, float)
    if c.size < win + 1:
        return {"break": False, "reason": "série trop courte"}
    x = np.arange(win)
    seg = c[-win - 1:-1]                     # canal = win barres STRICTEMENT passées
    slope, b = np.polyfit(x, seg, 1)
    resid = seg - (slope * x + b)
    upper = (slope * win + b) + k * resid.std(ddof=1)   # extrapolé à la barre courante
    price_break = bool(c[-1] > upper)
    onchain_ok = True
    z = None
    if confirm is not None:
        past = np.asarray(confirm, float)[-win - 1:-1]
        cur = np.asarray(confirm, float)[-1]
        if past.size >= 5 and past.std(ddof=1) > 0:
            z = float((cur - past.mean()) / past.std(ddof=1))
            onchain_ok = z > conf_z
        else:
            onchain_ok = False
    return {"break": bool(price_break and onchain_ok), "slope": round(float(slope), 6),
            "price_break": price_break, "onchain_z": z}


def detect_breakouts(closes, win: int = 60, k: float = 2.0, confirm=None) -> list[int]:
    """Indices des barres en cassure (scan causal : canal = fenêtre passée)."""
    c = np.asarray(closes, float)
    out: list[int] = []
    for t in range(win, c.size):
        sub_conf = None if confirm is None else np.asarray(confirm, float)[: t + 1]
        if channel_break(c[: t + 1], win=win, k=k, confirm=sub_conf)["break"]:
            out.append(t)
    return out


def _fwd(rets, idx: int, post: int) -> float:
    r = np.asarray(rets, float)
    j0 = idx + 1
    return float(r[j0: min(len(r), j0 + post)].sum()) if j0 < len(r) else float("nan")


def strategy_returns(closes, win: int = 60, k: float = 2.0, post: int = 5,
                     confirm=None) -> np.ndarray:
    """Rendements quotidiens d'une stratégie « long les `post` jours après cassure ».

    Position = 1 sur les `post` jours suivant chaque cassure, sinon 0 (flat). Sert au
    gate (DSR/PBO/sabotage) sur une vraie courbe de rendements, pas juste des CAR.
    """
    c = np.asarray(closes, float)
    rets = np.zeros_like(c)
    rets[1:] = np.diff(c) / np.where(c[:-1] == 0, np.nan, c[:-1])
    rets = np.nan_to_num(rets)
    pos = np.zeros(c.size)
    for i in detect_breakouts(c, win=win, k=k, confirm=confirm):
        pos[i + 1: min(c.size, i + 1 + post)] = 1.0
    return pos * rets


def full_gate(closes, win: int = 60, k: float = 2.0, post: int = 5,
              n_sims: int = 1000) -> dict:
    """Gate COMPLET : placebo → DSR → PBO (grille de params) → sabotage → verdict.

    Réutilise psr/pbo/adversarial/gate. n_trials (DSR) = taille de la grille (déflation
    pour la recherche d'hyperparamètres). Rien n'est « promu » sans TOUS les contrôles.
    """
    from packages.portfolio.pbo import pbo_cscv
    from packages.portfolio.psr import deflated_sharpe_ratio
    from packages.research.adversarial import sabotage_verdict
    from packages.research.gate import promotion_verdict

    plac = significance(closes, win=win, k=k, post=post, n_sims=n_sims)
    ret = strategy_returns(closes, win=win, k=k, post=post)
    mean, sd = float(ret.mean()), float(ret.std(ddof=1))
    sharpe = mean / sd if sd > 0 else 0.0
    # Grille ≥20 configs → PBO/CSCV moins bruité (9 configs = estimateur instable).
    grid = [(w, p) for w in (30, 40, 50, 60, 80) for p in (3, 5, 8, 10)]
    cols = [strategy_returns(closes, win=w, post=p) for w, p in grid]
    tmin = min(c.size for c in cols)
    mat = np.column_stack([c[-tmin:] for c in cols])
    pbo = pbo_cscv(mat)
    # DSR déflaté sur TOUT le programme de recherche (ledger), pas la grille locale,
    # + sr_std estimé inter-essais (correctif sous-déflation). Repli sur la grille.
    try:
        from packages.research.ledger import deflation_params
        n_trials, sr_std = deflation_params(min_trials=len(grid))
    except Exception:  # noqa: BLE001
        n_trials, sr_std = len(grid), 1.0
    dsr = deflated_sharpe_ratio(sharpe, ret.size, n_trials=n_trials, sr_std=sr_std)
    sab = sabotage_verdict(ret)
    verdict = promotion_verdict(dsr=dsr, pbo=pbo.get("pbo"),
                                placebo_p=plac.get("placebo_p_value"))
    verdict["checks"]["sabotage"] = bool(sab.get("survives"))
    promoted = bool(verdict["checks"]) and all(verdict["checks"].values())
    return {"sharpe_bar": round(sharpe, 4), "dsr": dsr, "pbo": pbo.get("pbo"),
            "placebo_p": plac.get("placebo_p_value"), "sabotage": sab,
            "n_trials": len(grid), "promoted": promoted, "checks": verdict["checks"],
            "reasons": verdict["reasons"]}


def significance(closes, win: int = 60, k: float = 2.0, post: int = 5,
                 confirm=None, n_sims: int = 1000, seed: int = 0) -> dict:
    """CAR forward moyen des cassures (long) + placebo (dates aléatoires) = H0."""
    c = np.asarray(closes, float)
    rets = np.zeros_like(c)
    rets[1:] = np.diff(c) / np.where(c[:-1] == 0, np.nan, c[:-1])
    rets = np.nan_to_num(rets)
    ev = detect_breakouts(c, win=win, k=k, confirm=confirm)
    cars = [v for i in ev if (v := _fwd(rets, i, post)) == v]
    if len(cars) < 5:
        return {"available": False, "n": len(cars)}
    arr = np.array(cars)
    mean, sd = float(arr.mean()), float(arr.std(ddof=1))
    t = mean / (sd / np.sqrt(len(arr))) if sd > 0 else 0.0
    rng = np.random.default_rng(seed)
    n = len(rets)
    hi = max(win + 1, n - post - 1)
    sims = np.array([
        np.mean([_fwd(rets, int(i), post)
                 for i in rng.integers(win, hi, size=len(cars))])
        for _ in range(n_sims)])
    p = float((np.abs(sims) >= abs(mean)).mean())
    return {"available": True, "n": len(arr), "mean_car": round(mean, 5),
            "t_stat": round(t, 3), "placebo_p_value": round(p, 4),
            "significant": bool(p < 0.05),
            "verdict": "SIGNIFICATIF" if p < 0.05 else "BRUIT"}
