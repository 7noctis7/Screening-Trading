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


# ─────────── Journal de runs SANS dépendance (toujours dispo, complète MLflow) ───────────
_HISTORY_PATH = _ROOT / "models" / "train_history.jsonl"


def record_run(*, metrics: dict[str, float], params: dict[str, Any] | None = None,
               status: str = "candidate", path: str | Path | None = None) -> bool:
    """Ajoute une ligne au journal d'entraînement (JSONL append-only). stdlib pur, jamais bloquant.
    Sert de source au suivi de drift et à l'affichage front, indépendamment de MLflow."""
    try:
        import json
        from datetime import datetime, timezone
        p = Path(path) if path else _HISTORY_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "status": status,
               "metrics": {k: round(float(v), 6) for k, v in metrics.items() if v is not None},
               "params": {k: v for k, v in (params or {}).items() if v is not None}}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return True
    except Exception:  # noqa: BLE001
        return False


def load_history(limit: int = 30, path: str | Path | None = None) -> list[dict]:
    """Lit les derniers runs du journal (les plus récents en dernier). Best-effort → [] si absent."""
    try:
        import json
        p = Path(path) if path else _HISTORY_PATH
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        out = []
        for ln in lines[-limit:]:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out
    except Exception:  # noqa: BLE001
        return []


def detect_drift(history: list[dict], *, metric: str = "auc_oos", window: int = 5,
                 drop: float = 0.05) -> dict[str, Any]:
    """Détecte une DÉGRADATION du modèle : la métrique courante chute de plus de `drop` sous la
    moyenne des `window` runs précédents. Pur stdlib. Renvoie {drift, current, baseline, delta}."""
    vals = [h.get("metrics", {}).get(metric) for h in history]
    vals = [float(v) for v in vals if v is not None]
    if len(vals) < 2:
        return {"drift": False, "current": vals[-1] if vals else None, "baseline": None, "delta": None,
                "n": len(vals)}
    current = vals[-1]
    prev = vals[-(window + 1):-1] or vals[:-1]
    baseline = sum(prev) / len(prev)
    delta = round(current - baseline, 6)
    return {"drift": (baseline - current) > drop, "current": round(current, 6),
            "baseline": round(baseline, 6), "delta": delta, "n": len(vals), "metric": metric}
