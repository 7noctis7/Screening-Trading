"""Détection de RÉGIME DE VOLATILITÉ (calme / normal / stress) pour piloter l'exposition
au-delà du VIX. Robuste et sans dépendance (terciles de la vol réalisée historique) ; bascule
sur un HMM gaussien à 2 états si `hmmlearn` est installé. Prolonge la volatilité gérée.
"""

from __future__ import annotations

import numpy as np

_EXPO = {"calme": 1.0, "normal": 0.7, "stress": 0.4}


def _realized_vol(returns, window: int = 20) -> np.ndarray:
    r = np.asarray(returns, float)
    out = np.full(len(r), np.nan)
    for i in range(len(r)):
        lo = max(0, i - window + 1)
        if i - lo + 1 >= max(5, window // 2):
            out[i] = float(r[lo:i + 1].std()) * np.sqrt(252)
    return out


def _hmm_state(rv: np.ndarray):
    """Régime via HMM gaussien 2 états (si hmmlearn dispo) → ('stress'/'calme', proba)."""
    try:
        from hmmlearn.hmm import GaussianHMM
    except Exception:  # noqa: BLE001
        return None
    try:
        x = rv[~np.isnan(rv)].reshape(-1, 1)
        if len(x) < 60:
            return None
        m = GaussianHMM(n_components=2, covariance_type="diag", n_iter=50, random_state=0).fit(x)
        states = m.predict(x)
        hi = int(np.argmax(m.means_.ravel()))             # état à vol la plus haute = stress
        last = int(states[-1])
        return ("stress" if last == hi else "calme"), float(m.means_.ravel()[last])
    except Exception:  # noqa: BLE001
        return None


def vol_regime(returns, window: int = 20) -> dict:
    """Régime courant + multiplicateur d'exposition suggéré (sans levier)."""
    r = np.asarray(returns, float)
    if len(r) < window + 30:
        return {"available": False}
    rv = _realized_vol(r, window)
    valid = rv[~np.isnan(rv)]
    if valid.size < 20:
        return {"available": False}
    cur = float(valid[-1])
    q33, q66 = (float(x) for x in np.percentile(valid, [33, 66]))
    state = "calme" if cur < q33 else ("stress" if cur > q66 else "normal")
    pct = float((valid < cur).mean())
    method = "terciles de vol réalisée"
    hmm = _hmm_state(rv)
    if hmm is not None and state != "normal":             # HMM affine la conviction aux extrêmes
        state, method = hmm[0], "HMM gaussien 2 états (hmmlearn)"
    return {"available": True, "state": state, "current_vol": round(cur, 4),
            "exposure_multiplier": _EXPO[state], "percentile": round(pct, 3),
            "thresholds": {"calme<": round(q33, 4), "stress>": round(q66, 4)},
            "method": method,
            "note": "Exposition suggérée : calme ×1.0 · normal ×0.7 · stress ×0.4 (sans levier)."}
