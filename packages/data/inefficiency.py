"""Audit d'INEFFICIENCE d'un univers (ticket #4, Thiel) : un micro-marché ne « vaut le coup »
que s'il contient une structure EXPLOITABLE. On mesure, point-in-time :

  1. Autocorrélation lag-1 des rendements (momentum persistant si > 0 ; mean-reverting si < 0).
  2. Variance ratio de Lo-MacKinlay (≠ 1 = s'écarte de la marche aléatoire → exploitable).
  3. Dispersion cross-sectionnelle (taille de l'opportunité de sélection).
  4. **Edge momentum réel** : DSR (Sharpe déflaté) d'une stratégie momentum long top-décile vs marché
     — le juge de paix, anti-surapprentissage.

Score d'exploitabilité 0-100 (piloté à 70 % par le DSR du momentum). numpy pur, testable.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.psr import deflated_sharpe_ratio


def _autocorr1(r: np.ndarray) -> float:
    if len(r) < 30 or r.std() == 0:
        return float("nan")
    return float(np.corrcoef(r[:-1], r[1:])[0, 1])


def variance_ratio(r: np.ndarray, q: int = 5) -> float:
    """Lo-MacKinlay VR(q) = Var(rendement q-périodes) / (q · Var(1 période)). 1 = marche aléatoire."""
    n = (len(r) // q) * q
    if n < q * 4:
        return float("nan")
    r = r[:n]
    var1 = r.var()
    if var1 <= 0:
        return float("nan")
    rq = r.reshape(-1, q).sum(axis=1)
    return float(rq.var() / (q * var1))


def momentum_edge(data: dict, step: int = 21, lookback: int = 63, top_frac: float = 0.2) -> dict:
    """Alpha d'une stratégie momentum cross-section (long top-décile vs marché), DSR à l'appui."""
    syms = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(syms) < 10:
        return {"available": False}
    L = min(len(data[s]) for s in syms)
    M = np.array([[x.close for x in data[s]][-L:] for s in syms], dtype=float)
    port = []
    for t in range(lookback, L - 1, step):
        mom = M[:, t] / M[:, t - lookback] - 1
        k = max(1, int(len(syms) * top_frac))
        idx = np.argsort(mom)[::-1][:k]
        nxt = min(t + step, L - 1)
        port.append(float((M[idx, nxt] / M[idx, t] - 1).mean() - (M[:, nxt] / M[:, t] - 1).mean()))
    if len(port) < 5:
        return {"available": False}
    r = np.asarray(port)
    sd = float(r.std())
    per_year = 252.0 / step
    sharpe = float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    sr_p = float(r.mean() / sd) if sd > 0 else 0.0
    return {"available": True, "sharpe": round(sharpe, 2), "n": len(r),
            "dsr": deflated_sharpe_ratio(sr_p, len(r), n_trials=10)}


def inefficiency_report(data: dict) -> dict:
    """Rapport d'exploitabilité d'un univers (score 0-100 + verdict)."""
    rets, acs, vrs = [], [], []
    for _s, b in data.items():
        c = np.array([x.close for x in b], dtype=float)
        if len(c) < 120:
            continue
        r = np.diff(c) / c[:-1]
        rets.append(r)
        a = _autocorr1(r)
        if not np.isnan(a):
            acs.append(a)
        v = variance_ratio(r, 5)
        if not np.isnan(v):
            vrs.append(v)
    if len(acs) < 5:
        return {"available": False, "reason": "univers trop petit / historique insuffisant"}
    ac = float(np.mean(acs))
    vr = float(np.mean(vrs)) if vrs else 1.0
    disp = float(np.std([r.mean() for r in rets]))
    edge = momentum_edge(data)
    dsr = edge.get("dsr", 0.0) if edge.get("available") else 0.0
    # structure ∈ [0,1] : éloignement de la marche aléatoire (autocorr + variance ratio)
    struct = min(1.0, abs(ac) / 0.05 * 0.5 + abs(vr - 1.0) / 0.30 * 0.5)
    score = round(100.0 * (0.70 * dsr + 0.30 * struct), 1)
    verdict = ("EXPLOITABLE — un edge semble présent" if score >= 50 else
               "INCERTAIN — à creuser" if score >= 25 else
               "EFFICIENT — peu/pas d'edge, ne pas s'engager")
    return {"available": True, "n_assets": len(acs), "score": score, "verdict": verdict,
            "autocorr_lag1": round(ac, 4), "variance_ratio": round(vr, 3),
            "cross_dispersion": round(disp, 5),
            "momentum_sharpe": edge.get("sharpe") if edge.get("available") else None,
            "momentum_dsr": round(dsr, 3),
            "note": ("Score piloté à 70 % par le DSR du momentum (edge réel) + 30 % structure "
                     "(autocorr/variance-ratio). DSR≈0 ⇒ pas d'edge prouvé, peu importe la structure.")}
