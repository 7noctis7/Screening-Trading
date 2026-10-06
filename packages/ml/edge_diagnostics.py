"""Diagnostics du modèle d'edge transversal — chacun sur une découpe TEMPORELLE.

`X` arrive trié par début de label (cf. `edge_transversal.jeu_de_donnees`) : toute coupe
« les N premiers / les suivants » est donc passé → futur. Chaque diagnostic renvoie
`{"available": False}` plutôt que de lever : une section indisponible ne doit pas
empêcher le snapshot de se construire.
"""

from __future__ import annotations

import numpy as np

from packages.ml.edge_transversal import auc, modele


def calibration(X, y) -> dict:
    """Platt ajusté sur une moitié du test, jugé sur l'autre (QML-011) ; Brier."""
    try:
        from packages.ml.validation_edge import calibration_hors_echantillon
        cut = int(len(X) * 0.8)
        if cut <= 100 or len(X) - cut <= 50:
            return {"available": False}
        m, _ = modele()
        m.fit(X[:cut], y[:cut])
        p_te = np.asarray(m.predict_proba(X[cut:]), float)
        return calibration_hors_echantillon(p_te, y[cut:])
    except Exception:  # noqa: BLE001
        return {"available": False}


def conformal(X, y) -> dict:
    """Prédiction conforme (LAC) : couverture garantie 1−α (split calib/test)."""
    try:
        from packages.ml.conformal import evaluate as conformal_eval
        cut, mid = int(len(X) * 0.8), int(len(X) * 0.6)
        if mid <= 100 or len(X) - cut <= 50:
            return {"available": False}
        m, _ = modele()
        m.fit(X[:mid], y[:mid])
        p_cal = np.asarray(m.predict_proba(X[mid:cut]), float)
        p_te = np.asarray(m.predict_proba(X[cut:]), float)
        return {"available": True,
                **conformal_eval(p_cal, y[mid:cut], p_te, y[cut:], alpha=0.1)}
    except Exception:  # noqa: BLE001
        return {"available": False}


def meta_labeling(X, y) -> dict:
    """Un 2e modèle filtre les faux positifs du primaire (primaire / méta / test)."""
    try:
        from packages.ml.meta import evaluate as meta_eval
        from packages.ml.meta import meta_labels
        from packages.ml.sizing import evaluate_sizing
        a0, a1, a2 = int(len(X) * 0.5), int(len(X) * 0.75), len(X)
        if a0 <= 100 or a2 - a1 <= 50:
            return {"available": False}
        mp, _ = modele()
        mp.fit(X[:a0], y[:a0])
        pm = np.asarray(mp.predict_proba(X[a0:a1]), float)
        lbl = meta_labels(pm, y[a0:a1])
        if len(set(lbl)) <= 1:
            return {"available": False}
        mm, _ = modele()
        mm.fit(np.column_stack([X[a0:a1], pm]), lbl)
        pte = np.asarray(mp.predict_proba(X[a1:a2]), float)
        mte = np.asarray(mm.predict_proba(np.column_stack([X[a1:a2], pte])), float)
        return {"available": True, **meta_eval(pte, mte, y[a1:a2]),
                "sizing": evaluate_sizing(pte, y[a1:a2], mte)}
    except Exception:  # noqa: BLE001
        return {"available": False}


def walk_forward(X, y) -> dict:
    """Walk-forward ancré : AUC moyenne ± écart-type sur 5 plis."""
    try:
        from packages.backtest.walk_forward import walk_forward_splits
        aucs = []
        for tr, te in walk_forward_splits(len(X), n_splits=5, train_frac=0.5,
                                          anchored=True):
            tr, te = list(tr), list(te)
            if len(set(y[te])) < 2:
                continue
            m, _ = modele()
            m.fit(X[tr], y[tr])
            a = auc(m.predict_proba(X[te]), y[te])
            if a is not None:
                aucs.append(a)
        if not aucs:
            return {"available": False}
        return {"available": True, "folds": len(aucs),
                "auc_mean": round(float(np.mean(aucs)), 3),
                "auc_std": round(float(np.std(aucs)), 3),
                "aucs": [round(a, 3) for a in aucs]}
    except Exception:  # noqa: BLE001
        return {"available": False}


def derive(X, noms) -> dict:
    """Dérive des features (PSI) : 1re moitié (référence) vs 2nde moitié."""
    try:
        from packages.ml.drift import feature_drift
        half = len(X) // 2
        if half <= 50:
            return {"available": False}
        return {"available": True, **feature_drift(X[:half], X[half:], noms)}
    except Exception:  # noqa: BLE001
        return {"available": False}


def historique() -> dict:
    """AUC OOS run après run (journal append-only) et alerte de dégradation."""
    try:
        from packages.ml.tracking import detect_drift, load_history
        hist = load_history(limit=30)
        if not hist:
            return {"available": False}
        runs = [{"ts": h.get("ts"), "status": h.get("status"),
                 "auc_oos": h.get("metrics", {}).get("auc_oos")} for h in hist[-15:]]
        return {"available": True, "runs": runs,
                "drift": detect_drift(hist, metric="auc_oos")}
    except Exception:  # noqa: BLE001
        return {"available": False}


def tracer_mlflow(model_name: str, horizon: int, n_splits: int, n: int,
                  cv_auc: float | None) -> None:
    """Suivi d'expérience mlflow, optionnel et silencieux s'il est absent."""
    try:
        import mlflow
        mlflow.set_experiment("quant-terminal-ml")
        with mlflow.start_run(run_name="edge_cross_section"):
            mlflow.log_params({"model": model_name, "horizon": horizon,
                               "n_splits": n_splits, "n_samples": n})
            if cv_auc is not None:
                mlflow.log_metric("cv_auc_purged", cv_auc)
    except Exception:  # noqa: BLE001
        pass
