"""Tracking MLOps via MLflow (local, gratuit) — OPTIONNEL et NON bloquant.

Logue hyperparamètres, métriques (AUC, stats triple-barrière), importance des features et l'artefact
du modèle ; tague `production-ready` le modèle validé. Si MLflow est absent ou échoue, on renvoie
False SANS jamais lever : l'entraînement et le serving ne doivent JAMAIS dépendre du tracking."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("quant.mltrack")
_ROOT = Path(__file__).resolve().parents[2]


def track_training(*, run_name: str, params: dict[str, Any], metrics: dict[str, float],
                   importances: dict[str, float] | None = None, artifact: str | Path | None = None,
                   tags: dict[str, str] | None = None, experiment: str = "quant-ml") -> bool:
    """Logue un run d'entraînement dans MLflow local (./mlruns). Renvoie True si logué, False sinon.
    JAMAIS d'exception propagée."""
    try:
        import mlflow
    except Exception:  # noqa: BLE001 — MLflow non installé → no-op silencieux
        return False
    try:
        uri = os.environ.get("MLFLOW_TRACKING_URI", f"file:{_ROOT / 'mlruns'}")
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({k: v for k, v in params.items() if v is not None})
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
            for k, v in (tags or {}).items():
                mlflow.set_tag(k, v)
            if importances:
                mlflow.log_dict(importances, "feature_importance.json")
            if artifact and Path(artifact).exists():
                mlflow.log_artifact(str(artifact))
        return True
    except Exception as e:  # noqa: BLE001 — toute panne MLflow est non bloquante
        log.warning("MLflow tracking ignoré : %s", e)
        return False
