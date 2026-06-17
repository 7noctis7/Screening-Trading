"""Optimisation d'hyperparamètres — Optuna si dispo, sinon recherche aléatoire (numpy).

Best practice MLOps : régler les hyperparamètres sur une métrique de validation, jamais à l'œil.
Optuna (TPE) si installé ; repli sur une recherche aléatoire reproductible — même interface.
"""

from __future__ import annotations

import numpy as np


def optuna_available() -> bool:
    try:
        import optuna  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def optimize(objective, space: dict, n_trials: int = 30, seed: int = 0, maximize: bool = True):
    """Cherche les meilleurs hyperparamètres.

    Args:
        objective: fn(params:dict) -> score (float).
        space: {nom: (low, high)} pour des paramètres continus.
        n_trials: budget d'essais.
    Returns:
        {best_params, best_score, n_trials, engine}.
    """
    if optuna_available():
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study = optuna.create_study(direction="maximize" if maximize else "minimize",
                                        sampler=optuna.samplers.TPESampler(seed=seed))

            def _obj(trial):
                params = {k: trial.suggest_float(k, lo, hi) for k, (lo, hi) in space.items()}
                return objective(params)

            study.optimize(_obj, n_trials=n_trials, show_progress_bar=False)
            return {"best_params": study.best_params, "best_score": round(study.best_value, 6),
                    "n_trials": n_trials, "engine": "optuna"}
        except Exception:  # noqa: BLE001
            pass
    # repli : recherche aléatoire reproductible
    rng = np.random.default_rng(seed)
    best_p, best_s = None, (-np.inf if maximize else np.inf)
    for _ in range(n_trials):
        params = {k: float(rng.uniform(lo, hi)) for k, (lo, hi) in space.items()}
        s = objective(params)
        if (maximize and s > best_s) or (not maximize and s < best_s):
            best_p, best_s = params, s
    return {"best_params": best_p, "best_score": round(float(best_s), 6),
            "n_trials": n_trials, "engine": "random (repli)"}
