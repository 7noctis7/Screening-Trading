"""MLflow tracking + journal de runs — non bloquant (no-op si mlflow absent), ne lève jamais."""
from packages.ml.tracking import detect_drift, load_history, record_run, track_training


def test_track_training_never_raises():
    ok = track_training(run_name="t", params={"a": 1}, metrics={"auc": 0.5},
                        importances={"f1": 0.9}, tags={"status": "candidate"})
    assert ok in (True, False)                              # True si mlflow présent, False sinon — jamais d'exception


def test_record_and_load_history(tmp_path):
    p = tmp_path / "hist.jsonl"
    assert record_run(metrics={"auc_oos": 0.55}, status="candidate", path=p)
    assert record_run(metrics={"auc_oos": 0.60}, status="production-ready", path=p)
    h = load_history(path=p)
    assert len(h) == 2 and h[-1]["metrics"]["auc_oos"] == 0.60 and h[-1]["status"] == "production-ready"


def test_load_history_missing_returns_empty(tmp_path):
    assert load_history(path=tmp_path / "absent.jsonl") == []


def test_detect_drift_flags_degradation():
    hist = [{"metrics": {"auc_oos": 0.60}}, {"metrics": {"auc_oos": 0.61}},
            {"metrics": {"auc_oos": 0.59}}, {"metrics": {"auc_oos": 0.48}}]   # chute finale
    d = detect_drift(hist, metric="auc_oos", drop=0.05)
    assert d["drift"] is True and d["current"] == 0.48 and d["delta"] < 0


def test_detect_drift_stable_when_steady():
    hist = [{"metrics": {"auc_oos": 0.58}}, {"metrics": {"auc_oos": 0.59}}, {"metrics": {"auc_oos": 0.585}}]
    assert detect_drift(hist, metric="auc_oos")["drift"] is False
