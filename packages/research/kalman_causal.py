"""Filtre de Kalman causal pour un hedge ratio dynamique.

La calibration est faite uniquement sur un préfixe d'apprentissage, puis les paramètres
sont gelés. Le filtre est unilatéral : aucune passe arrière RTS n'existe dans ce module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class KalmanParams:
    delta: float
    observation_var: float
    train_end: int


def _filter(y: np.ndarray, x: np.ndarray, delta: float, obs_var: float) -> dict:
    state = np.zeros(2, dtype=float)
    cov = np.eye(2, dtype=float)
    states, innovations, variances = [], [], []
    process = delta / max(1.0 - delta, 1e-12) * np.eye(2)
    for yi, xi in zip(y, x, strict=True):
        design = np.array([1.0, xi], dtype=float)
        pred_cov = cov + process
        innovation = float(yi - design @ state)
        variance = float(design @ pred_cov @ design + obs_var)
        gain = pred_cov @ design / max(variance, 1e-12)
        state = state + gain * innovation
        cov = pred_cov - np.outer(gain, design) @ pred_cov
        states.append(state.copy())
        innovations.append(innovation)
        variances.append(variance)
    return {
        "states": np.asarray(states),
        "innovations": np.asarray(innovations),
        "innovation_var": np.asarray(variances),
    }


def _nll(y: np.ndarray, x: np.ndarray, delta: float, obs_var: float) -> float:
    result = _filter(y, x, delta, obs_var)
    v = result["innovation_var"]
    e = result["innovations"]
    return float(0.5 * np.sum(np.log(2.0 * np.pi * v) + e * e / v))


def calibrate_train_only(
    y,
    x,
    train_end: int,
    *,
    deltas: tuple[float, ...] = (1e-6, 1e-5, 1e-4, 1e-3),
    observation_vars: tuple[float, ...] | None = None,
) -> KalmanParams:
    """Calibre (delta, R) par MLE sur ``[0:train_end]`` exclusivement."""
    ya, xa = np.asarray(y, float), np.asarray(x, float)
    if ya.shape != xa.shape or train_end < 20 or train_end > ya.size:
        raise ValueError(
            "train_end doit définir un préfixe commun d'au moins 20 observations"
        )
    if not (np.isfinite(ya[:train_end]).all() and np.isfinite(xa[:train_end]).all()):
        raise ValueError("le préfixe d'apprentissage contient une valeur non finie")
    scale = max(float(np.var(ya[:train_end])), 1e-8)
    grid_r = observation_vars or (scale * 0.001, scale * 0.01, scale * 0.1)
    candidates = (
        (d, r, _nll(ya[:train_end], xa[:train_end], d, r))
        for d in deltas
        for r in grid_r
        if 0 < d < 1 and r > 0
    )
    try:
        delta, obs_var, _ = min(candidates, key=lambda item: item[2])
    except ValueError as exc:
        raise ValueError("grille de calibration Kalman vide") from exc
    return KalmanParams(float(delta), float(obs_var), int(train_end))


def causal_kalman(y, x, params: KalmanParams) -> dict:
    """Filtre progressif sur toute la série avec paramètres pré-calibrés et gelés."""
    ya, xa = np.asarray(y, float), np.asarray(x, float)
    if (
        ya.shape != xa.shape
        or ya.ndim != 1
        or not np.isfinite(ya).all()
        or not np.isfinite(xa).all()
    ):
        raise ValueError("y et x doivent être deux séries 1-D finies de même taille")
    out = _filter(ya, xa, params.delta, params.observation_var)
    out["alpha"] = out["states"][:, 0]
    out["beta"] = out["states"][:, 1]
    out["params"] = params
    return out
