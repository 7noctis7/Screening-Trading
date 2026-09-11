from packages.ml import artifact


def test_metrics_payload_preserves_missing_dsr_without_inventing_one():
    """Un classifieur sans rendements OOS ne peut pas prétendre avoir un DSR."""
    assert artifact.metrics_payload(dsr=None, brier=0.21, auc=0.54) == {
        "dsr": None, "brier": 0.21, "auc": 0.54,
    }


def test_metrics_payload_rejects_non_finite_values():
    assert artifact.metrics_payload(dsr=float("nan"), brier=float("inf"), auc=0.51) == {
        "dsr": None, "brier": None, "auc": 0.51,
    }


def test_metrics_from_old_or_invalid_payload_is_explicitly_uncalibrated():
    expected = {"dsr": None, "brier": None, "auc": None}
    assert artifact.metrics_from_payload({"fn": ["f"]}) == expected
    assert artifact.metrics_from_payload({"metrics": "invalid"}) == expected


def test_metrics_from_payload_normalises_corrupted_metric_values():
    assert artifact.metrics_from_payload({"metrics": {"dsr": "bad", "brier": 0.2,
                                                       "auc": float("nan")}}) == {
        "dsr": None, "brier": 0.2, "auc": None,
    }


def test_save_and_load_keep_oos_metrics_with_the_model(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact, "_DIR", tmp_path)
    metrics = artifact.metrics_payload(dsr=None, brier=0.19, auc=0.53)

    assert artifact.save((100, 3), "champion", {"fn": ["f"], "metrics": metrics})

    model, payload = artifact.load((100, 3))
    assert model == "champion"
    assert payload["metrics"] == metrics
