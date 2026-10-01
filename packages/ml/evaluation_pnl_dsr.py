"""Pont métrique ML → PnL/DSR (P0) — complète packages/ml/evaluation.py.

CONTEXTE. `apps/api/snapshot._ml_section` embarque `metrics_payload(dsr=None, …)`
parce que le classifieur ne produit que des labels/probabilités, pas une série de
rendements OOS. Or `packages/ml/promotion.should_promote` EXIGE un DSR comparable :
sans série de PnL, le champion ne porte jamais de DSR → promotion bloquée ou
comparaison impossible (voir `scripts/train_model._metrics`).

Ce module construit la série manquante à partir des rendements réalisés des labels
(triple-barrière / meta-labeling) et des prédictions OOS, puis calcule PSR/DSR via
`packages.portfolio.psr.psr_dsr_depuis_rendements` (même chemin que le portefeuille).

Mesure uniquement — ne pilote aucun ordre.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np


def strategy_returns_from_meta(
    y_pred: np.ndarray,
    realized_ret: np.ndarray,
    *,
    side: int = 1,
) -> np.ndarray:
    """Rendements de stratégie OOS pour un méta-label binaire.

    - `y_pred` : 0/1 (agir ou non) sur le fold OOS.
    - `realized_ret` : rendement du trade primaire aligné (ex. `Label.ret`).
    - `side` : sens du primaire (+1 long / -1 short).

    PnL par trade = y_pred * side * realized_ret (pas d'action → 0).
    """
    pred = np.asarray(y_pred, dtype=float).ravel()
    rets = np.asarray(realized_ret, dtype=float).ravel()
    if pred.shape != rets.shape:
        raise ValueError(f"y_pred {pred.shape} ≠ realized_ret {rets.shape}")
    act = (pred > 0.5).astype(float)
    return act * float(side) * rets


def strategy_returns_from_scores(
    scores: np.ndarray,
    realized_ret: np.ndarray,
    *,
    threshold: float = 0.5,
    side: int = 1,
) -> np.ndarray:
    """Variante probabilités : n'entre que si score ≥ seuil."""
    s = np.asarray(scores, dtype=float).ravel()
    return strategy_returns_from_meta((s >= threshold).astype(int), realized_ret, side=side)


def dsr_from_oos_returns(
    returns: Iterable[float],
    *,
    n_trials: int = 20,
) -> dict:
    """DSR/PSR depuis les rendements de stratégie OOS (délègue à portfolio.psr).

    Renvoie un dict prêt pour `artifact.metrics_payload` :
    ``{"dsr": float|None, "psr": float|None, "available": bool, "motif": str, ...}``.
    """
    from packages.portfolio.psr import psr_dsr_depuis_rendements

    d = psr_dsr_depuis_rendements(list(returns), n_trials=n_trials)
    if not d.get("available"):
        return {
            "available": False,
            "dsr": None,
            "psr": None,
            "motif": d.get("motif", "échantillon insuffisant"),
            "n_obs": d.get("n_obs"),
        }
    return {
        "available": True,
        "dsr": float(d["dsr"]),
        "psr": float(d["psr"]),
        "sharpe_annualise": d.get("sharpe_annualise"),
        "n_obs": d["n_obs"],
        "n_trials": d["n_trials"],
        "motif": "",
    }


def evaluate_oos_with_dsr(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    realized_ret: np.ndarray,
    *,
    scores: np.ndarray | None = None,
    side: int = 1,
    n_trials: int = 20,
) -> dict:
    """Rapport d'évaluation OOS : classification + pont PnL → DSR.

    Remplace le trou `dsr=None` : brancher le `dsr` renvoyé dans
    `artifact.metrics_payload(...)` puis dans le payload sauvé par `_ml_section`.
    """
    from packages.ml.evaluation import accuracy, precision_recall

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    acc = accuracy(y_true, y_pred)
    prec, rec = precision_recall(y_true, y_pred)
    strat = strategy_returns_from_meta(y_pred, realized_ret, side=side)
    bridge = dsr_from_oos_returns(strat, n_trials=n_trials)

    out = {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "n": int(len(y_true)),
        "pnl_sum": float(np.nansum(strat)),
        "pnl_mean": float(np.nanmean(strat)) if len(strat) else 0.0,
        "dsr": bridge["dsr"],
        "psr": bridge["psr"],
        "dsr_available": bridge["available"],
        "dsr_motif": bridge.get("motif", ""),
        "n_obs_dsr": bridge.get("n_obs"),
    }
    if scores is not None:
        out["dsr_from_scores"] = dsr_from_oos_returns(
            strategy_returns_from_scores(scores, realized_ret, side=side),
            n_trials=n_trials,
        ).get("dsr")
    return out
