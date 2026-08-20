"""Cointégration (Engle-Granger) — le socle statistique du Pairs Trading.

La corrélation mesure des rendements qui bougent ensemble ; elle est instable et ne dit
RIEN sur le retour à la moyenne d'un écart. La cointégration teste l'existence d'une
combinaison linéaire STATIONNAIRE de deux prix : c'est elle qui autorise un pari de
mean-reversion. (Chan, *Algorithmic Trading* ; Engle-Granger 1987.)

Chaîne : hedge_ratio (MCO) → résidu = spread → ADF sur le spread → demi-vie (OU) → z-score.

⚠️ Pièges encodés ici :
- valeurs critiques ADF **spécifiques au résidu de cointégration** (Engle-Granger), plus
  strictes que l'ADF standard : réutiliser −2,86 sur un résidu ESTIMÉ sur-rejette ;
- ordre non symétrique : régresser y sur x ≠ x sur y → `engle_granger_both` teste les deux ;
- multiple testing : N actifs = N(N−1)/2 paires ; sans correction on « trouve » des paires
  au hasard → `bonferroni_level` + le champ `n_tests` du verdict ;
- fit plein-échantillon = look-ahead : `hedge_ratio` doit être estimé sur une fenêtre
  PASSÉE et gelée (paramètre `train` des appelants), jamais sur tout l'historique.

Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np

# Valeurs critiques asymptotiques (MacKinnon). "level" = ADF classique avec constante ;
# "eg2" = résidu d'une régression de cointégration à 2 variables (Phillips-Ouliaris).
_CRIT = {
    "level": {0.01: -3.43, 0.05: -2.86, 0.10: -2.57},
    "eg2": {0.01: -3.90, 0.05: -3.34, 0.10: -3.04},
}


def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """MCO : renvoie (coefficients, écarts-types). X inclut déjà sa constante."""
    XtX = X.T @ X
    beta = np.linalg.solve(XtX, X.T @ y)
    resid = y - X @ beta
    dof = max(1, X.shape[0] - X.shape[1])
    s2 = float(resid @ resid) / dof
    se = np.sqrt(np.maximum(np.diag(s2 * np.linalg.inv(XtX)), 0.0))
    return beta, se


def adf_stat(series, lags: int = 1) -> dict:
    """Statistique tau de Dickey-Fuller augmenté (modèle avec constante).

    Δy_t = a + b·y_{t−1} + Σ_i c_i·Δy_{t−i} + e   →   tau = b / se(b).
    """
    y = np.asarray(series, dtype=float)
    y = y[np.isfinite(y)]
    p = max(0, int(lags))
    if y.size < 20 + p:
        return {"available": False, "n": int(y.size)}
    dy = np.diff(y)
    n = dy.size - p
    if n < 10:
        return {"available": False, "n": int(y.size)}
    cols = [np.ones(n), y[p:-1]]
    for i in range(1, p + 1):
        cols.append(dy[p - i:-i] if i <= p else dy[p:])
    X = np.column_stack(cols)
    target = dy[p:]
    if X.shape[0] != target.size:
        return {"available": False, "n": int(y.size)}
    try:
        beta, se = _ols(X, target)
    except np.linalg.LinAlgError:
        return {"available": False, "n": int(y.size)}
    if se[1] <= 0:
        return {"available": False, "n": int(y.size)}
    return {"available": True, "stat": float(beta[1] / se[1]), "b": float(beta[1]),
            "lags": p, "n": int(n)}


def adf_test(series, lags: int = 1, level: float = 0.05, kind: str = "level") -> dict:
    """ADF + verdict de stationnarité au seuil `level` (0.01 / 0.05 / 0.10)."""
    st = adf_stat(series, lags)
    if not st.get("available"):
        return {"available": False, "status": "UNCALIBRATED", "n": st.get("n", 0),
                "hint": "≥ 20 observations requises pour un ADF interprétable"}
    table = _CRIT.get(kind, _CRIT["level"])
    lv = min(table, key=lambda x: abs(x - level))
    crit = table[lv]
    return {"available": True, "stat": round(st["stat"], 4), "crit": crit,
            "level": lv, "kind": kind, "lags": st["lags"], "n": st["n"],
            "stationary": bool(st["stat"] < crit)}


def hedge_ratio(y, x) -> dict:
    """MCO y = a + b·x : `b` = ratio de couverture, résidu = spread de cointégration."""
    Y = np.asarray(y, dtype=float)
    Xv = np.asarray(x, dtype=float)
    m = np.isfinite(Y) & np.isfinite(Xv)
    Y, Xv = Y[m], Xv[m]
    if Y.size < 20 or Xv.std() <= 0:
        return {"available": False, "n": int(Y.size)}
    X = np.column_stack([np.ones(Y.size), Xv])
    beta, se = _ols(X, Y)
    spread = Y - (beta[0] + beta[1] * Xv)
    return {"available": True, "alpha": float(beta[0]), "beta": float(beta[1]),
            "beta_se": float(se[1]), "spread": spread, "n": int(Y.size)}


def half_life(spread) -> dict:
    """Demi-vie d'un processus d'Ornstein-Uhlenbeck : Δs_t = a + b·s_{t−1}, HL = −ln2 / b.

    b ≥ 0 ⇒ pas de rappel vers la moyenne (le spread diverge) ⇒ pas de trade.
    """
    s = np.asarray(spread, dtype=float)
    s = s[np.isfinite(s)]
    if s.size < 20:
        return {"available": False, "n": int(s.size)}
    ds, lag = np.diff(s), s[:-1]
    if lag.std() <= 0:
        return {"available": False, "n": int(s.size)}
    X = np.column_stack([np.ones(lag.size), lag])
    beta, _ = _ols(X, ds)
    b = float(beta[1])
    if b >= 0:
        return {"available": True, "b": b, "half_life": None,
                "mean_reverting": False}
    return {"available": True, "b": b, "mean_reverting": True,
            "half_life": float(-np.log(2.0) / b)}


def spread_zscore(spread, lookback: int = 60) -> float | None:
    """z du DERNIER point sur une fenêtre GLISSANTE (jamais la moyenne plein-échantillon)."""
    s = np.asarray(spread, dtype=float)
    s = s[np.isfinite(s)]
    if s.size < max(10, lookback // 2):
        return None
    w = s[-lookback:]
    sd = float(w.std(ddof=1))
    if sd <= 0:
        return None
    return float((s[-1] - float(w.mean())) / sd)


def bonferroni_level(alpha: float, n_tests: int) -> float:
    """Seuil individuel corrigé (Šidák) pour garder un risque global `alpha` sur N paires."""
    n = max(1, int(n_tests))
    return float(1.0 - (1.0 - alpha) ** (1.0 / n))


def engle_granger(y, x, lags: int = 1, level: float = 0.05,
                  n_tests: int = 1) -> dict:
    """Test complet sur une paire ordonnée (y régressé sur x). Valeurs critiques `eg2`."""
    hr = hedge_ratio(y, x)
    if not hr.get("available"):
        return {"available": False, "status": "UNCALIBRATED", "n": hr.get("n", 0)}
    eff = bonferroni_level(level, n_tests) if n_tests > 1 else level
    adf = adf_test(hr["spread"], lags=lags, level=max(eff, 0.01), kind="eg2")
    hl = half_life(hr["spread"])
    return {"available": True, "beta": round(hr["beta"], 6),
            "alpha": round(hr["alpha"], 6), "n": hr["n"], "adf": adf,
            "half_life": (round(hl["half_life"], 2)
                          if hl.get("half_life") is not None else None),
            "mean_reverting": bool(hl.get("mean_reverting")),
            "z": spread_zscore(hr["spread"]),
            "level_used": round(eff, 5), "n_tests": int(n_tests),
            "cointegrated": bool(adf.get("stationary") and hl.get("mean_reverting"))}


def pair_verdict(y, x, lags: int = 1, level: float = 0.05, n_tests: int = 1,
                 hl_min: float = 1.0, hl_max: float = 60.0) -> dict:
    """Verdict tradable : cointégration DANS LES DEUX SENS + demi-vie exploitable.

    Une paire n'est retenue que si (a) les deux ordres de régression rejettent la racine
    unitaire — sinon la relation dépend d'un choix arbitraire de variable dépendante —,
    et (b) la demi-vie tient dans la fenêtre de détention du robot (`hl_min`..`hl_max`
    barres). Une demi-vie de 200 barres sur un robot 4 h = capital immobilisé, pas d'edge.
    """
    a = engle_granger(y, x, lags, level, n_tests)
    b = engle_granger(x, y, lags, level, n_tests)
    if not (a.get("available") and b.get("available")):
        return {"available": False, "status": "UNCALIBRATED"}
    both = bool(a["cointegrated"] and b["cointegrated"])
    hl = a["half_life"]
    hl_ok = bool(hl is not None and hl_min <= hl <= hl_max)
    reasons: list[str] = []
    if not a["cointegrated"]:
        reasons.append("y~x non cointégré")
    if not b["cointegrated"]:
        reasons.append("x~y non cointégré (relation dépendante de l'ordre)")
    if not hl_ok:
        reasons.append(f"demi-vie {hl} hors de [{hl_min}, {hl_max}]")
    return {"available": True, "tradable": bool(both and hl_ok), "forward": a,
            "reverse": b, "half_life": hl, "z": a["z"], "reasons": reasons}
