"""MLflow tracking — non bloquant (no-op si mlflow absent), ne lève jamais."""
from packages.ml.tracking import track_training


def test_track_training_never_raises():
    ok = track_training(run_name="t", params={"a": 1}, metrics={"auc": 0.5},
                        importances={"f1": 0.9}, tags={"status": "candidate"})
    assert ok in (True, False)                              # True si mlflow présent, False sinon — jamais d'exception
