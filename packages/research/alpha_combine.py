"""Combinaison de signaux — la façon dont les institutions produisent réellement de l'alpha.

Aucun facteur public ne passe un gate honnête tout seul : un IC de 0,03 sur 300 noms donne un
IR d'environ 0,5 AVANT coûts. Ce que font les multi-stratégies n'est pas de trouver LE signal,
c'est d'en agréger beaucoup de faibles, aussi décorrélés que possible :

    w* ∝ Omega⁻¹ · ic          IC_combiné = √( ic' · Omega⁻¹ · ic )

`Omega` = corrélation DES SIGNAUX entre eux. Deux signaux à IC 0,03 corrélés à 0,9 valent un
seul signal ; corrélés à 0,1, ils valent √2 fois plus. **La décorrélation vaut plus que la
force** — c'est le principe du modèle en pods.

⚠️ Le piège qui invalide 90 % des combinaisons : pondérer par des IC mesurés sur TOUT
l'historique, puis backtester sur ce même historique. La combinaison est alors ajustée
in-sample et son résultat ne veut rien dire. Ici les IC sont estimés en **fenêtre expansive**
(passé strict), ré-estimés périodiquement, et appliqués à la période SUIVANTE.

numpy pur. `A` = matrice n × L de prix (lignes = actifs).
"""

from __future__ import annotations

import numpy as np

from packages.ranking.orthogonalize import combine_signals, robust_z
from packages.research.alpha_hypotheses import (PRE_REGISTERED, SIGNALS, _weights,
                                                MAX_WEIGHT, STEP, TOP_FRAC)


def _rank(x: np.ndarray) -> np.ndarray:
    """Rangs normalisés dans [0,1] ; NaN → NaN (exclus des corrélations)."""
    out = np.full(x.size, np.nan)
    m = np.isfinite(x)
    if m.sum() < 3:
        return out
    order = np.argsort(np.argsort(x[m]))
    out[m] = order / max(1, m.sum() - 1)
    return out


def rank_ic(score: np.ndarray, fwd: np.ndarray) -> float | None:
    """IC = corrélation de RANG entre le score et le rendement futur (robuste aux queues)."""
    a, b = _rank(score), _rank(fwd)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 10 or a[m].std() == 0 or b[m].std() == 0:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def _score_at(A: np.ndarray, name: str, t: int) -> np.ndarray:
    return SIGNALS[name](A, t, **PRE_REGISTERED[name])


def measure_ics(A: np.ndarray, names: list[str], step: int = STEP,
                start: int = 520, exec_lag: int = 1, t_max: int | None = None) -> dict:
    """IC réalisé par signal sur [start, t_max] — le thermomètre avant toute pondération."""
    n, L = A.shape
    end = min(t_max if t_max is not None else L - 1, L - 1) - step - exec_lag
    if end <= start:
        return {"available": False, "status": "UNCALIBRATED"}
    series: dict[str, list[float]] = {k: [] for k in names}
    for t in range(start, end, step):
        entry, nxt = t + exec_lag, min(t + exec_lag + step, L - 1)
        fwd = A[:, nxt] / np.where(A[:, entry] == 0, np.nan, A[:, entry]) - 1.0
        for k in names:
            ic = rank_ic(_score_at(A, k, t), fwd)
            if ic is not None:
                series[k].append(ic)
    out = {}
    for k, vals in series.items():
        if len(vals) < 8:
            continue
        arr = np.asarray(vals)
        sd = float(arr.std(ddof=1))
        out[k] = {"ic_mean": round(float(arr.mean()), 4),
                  "ic_std": round(sd, 4), "n": int(arr.size),
                  "t_stat": round(float(arr.mean() / (sd / np.sqrt(arr.size))), 2)
                  if sd > 0 else 0.0,
                  "hit_rate": round(float((arr > 0).mean()), 3)}
    if not out:
        return {"available": False, "status": "UNCALIBRATED"}
    return {"available": True, "par_signal": out, "n_dates": len(next(iter(series.values())))}


def signal_correlation(A: np.ndarray, names: list[str], step: int = STEP,
                       start: int = 520, t_max: int | None = None) -> np.ndarray:
    """Corrélation MOYENNE entre signaux, mesurée en coupe à chaque date de rebalancement."""
    L = A.shape[1]
    end = min(t_max if t_max is not None else L - 1, L - 1)
    k = len(names)
    acc, cnt = np.zeros((k, k)), 0
    for t in range(start, end, step):
        Z = np.column_stack([robust_z(_score_at(A, nm, t)) for nm in names])
        if not np.isfinite(Z).all() or Z.std(axis=0).min() == 0:
            continue
        acc += np.corrcoef(Z, rowvar=False)
        cnt += 1
    return acc / cnt if cnt else np.eye(k)


def combined_backtest(A: np.ndarray, names: list[str], long_only: bool = False,
                      step: int = STEP, cost_rt_bps: float = 10.0, exec_lag: int = 1,
                      burn_in: int = 756, refit_every: int = 252,
                      shrink: float = 0.25, top_frac: float = TOP_FRAC,
                      max_weight: float = MAX_WEIGHT) -> dict:
    """Backtest du LIVRE COMBINÉ, pondération ré-estimée en fenêtre expansive.

    À chaque ré-estimation (tous les `refit_every` jours), on mesure les IC et la corrélation
    des signaux sur le PASSÉ STRICT, on en tire `w ∝ Omega⁻¹·ic`, et on applique ces poids à
    la période suivante. Aucune information future n'entre dans la pondération.

    Un signal dont l'IC passé est NÉGATIF garde son signe : c'est une information, pas une
    erreur — mais on n'inverse jamais un signal a posteriori sur la foi d'un seul échantillon,
    donc les poids négatifs sont écrêtés à zéro (parcimonie assumée, documentée).
    """
    n, L = A.shape
    start = max(burn_in, 520)
    if L < start + 4 * step:
        return {"available": False, "status": "UNCALIBRATED", "L": int(L)}
    prev = np.zeros(n)
    rets, turn, poids_hist = [], 0.0, []
    w_sig = None
    last_fit = -10**9
    for t in range(start, L - 1 - exec_lag, step):
        if t - last_fit >= refit_every or w_sig is None:
            ic_res = measure_ics(A, names, step=step, start=520, exec_lag=exec_lag, t_max=t)
            if ic_res.get("available"):
                ics = np.array([ic_res["par_signal"].get(k, {}).get("ic_mean", 0.0)
                                for k in names])
                O = signal_correlation(A, names, step=step, start=520, t_max=t)
                Z0 = np.column_stack([robust_z(_score_at(A, k, t)) for k in names])
                comb = combine_signals(Z0, ics, corr=O, shrink=shrink)
                if comb.get("available"):
                    w_sig = np.clip(comb["weights"], 0.0, None)   # pas d'inversion a posteriori
                    if w_sig.sum() <= 0:
                        w_sig = np.ones(len(names)) / len(names)
                    w_sig = w_sig / w_sig.sum()
                    last_fit = t
        if w_sig is None:
            continue
        Z = np.column_stack([robust_z(_score_at(A, k, t)) for k in names])
        score = np.nan_to_num(Z) @ w_sig
        w = _weights(score, long_only, top_frac, max_weight)
        entry = min(t + exec_lag, L - 1)
        nxt = min(entry + step, L - 1)
        fwd = np.nan_to_num(A[:, nxt] / np.where(A[:, entry] == 0, np.nan, A[:, entry]) - 1.0)
        cout = float(np.abs(w - prev).sum()) * cost_rt_bps / 1e4
        rets.append(float((w * fwd).sum()) - cout)
        turn += float(np.abs(w - prev).sum())
        poids_hist.append(w_sig.copy())
        prev = w
    if len(rets) < 8:
        return {"available": False, "status": "UNCALIBRATED", "n_steps": len(rets)}
    r = np.asarray(rets)
    per_year = 252.0 / step
    sd = float(r.std(ddof=1))
    eq = np.cumprod(1 + r)
    return {"available": True, "returns": r, "n_steps": int(r.size),
            "sharpe": round(float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0, 3),
            "annualized": round(float(eq[-1] ** (per_year / r.size) - 1), 4),
            "max_drawdown": round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
            "turnover_annual": round(turn / r.size * per_year, 2),
            "poids_finaux": {k: round(float(v), 3) for k, v in zip(names, poids_hist[-1])},
            "long_only": long_only, "step": step, "exec_lag": exec_lag}


def breadth_report(A: np.ndarray, names: list[str], ics: dict, step: int = STEP) -> dict:
    """IR ATTEIGNABLE = IC_combiné · √BR_eff · TC — le calcul à faire AVANT d'espérer.

    Répond à « avec cet univers et ces signaux, un IR de 1 est-il seulement possible ? ».
    """
    from packages.research.breadth import effective_breadth, expected_ir, ic_required
    n = A.shape[0]
    per_year = 252.0 / step
    O = signal_correlation(A, names, step=step)
    k = len(names)
    rho_sig = float((O.sum() - np.trace(O)) / (k * (k - 1))) if k > 1 else 0.0
    ic_vec = np.array([ics["par_signal"].get(nm, {}).get("ic_mean", 0.0) for nm in names])
    Osh = (1 - 0.25) * O + 0.25 * np.eye(k)
    ic_comb = float(np.sqrt(max(0.0, ic_vec @ np.linalg.pinv(Osh) @ ic_vec)))
    br = effective_breadth(n, int(round(per_year)), rho_cross=0.0, rho_time=0.0)
    return {"n_noms": n, "n_signaux": k, "rho_signaux": round(rho_sig, 3),
            "ic_combine": round(ic_comb, 4),
            "ic_meilleur_seul": round(float(np.max(np.abs(ic_vec))), 4),
            "breadth_naive": br["breadth_naive"],
            "ir_theorique_TC1": round(expected_ir(ic_comb, br["breadth_naive"], 1.0), 2),
            "ir_realiste_TC05": round(expected_ir(ic_comb, br["breadth_naive"], 0.5), 2),
            "ic_requis_pour_IR1": round(ic_required(1.0, br["breadth_naive"], 0.5) or 0.0, 4),
            "note": "BR naïf = n·périodes ; le souffle EFFECTIF est plus petit "
                    "(corrélation des noms et persistance des scores) — cet IR est un PLAFOND."}
