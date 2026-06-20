"""Entraîne le modèle ML HORS-LIGNE et persiste l'artefact (ticket #2 : serving découplé).

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/train_model.py        # → models/ml_*.pkl (chargé ensuite par l'API)

À lancer par le cron quotidien. Force le recalcul (supprime l'artefact périmé puis ré-entraîne).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    # 1) purge des anciens artefacts → force un entraînement frais
    models = ROOT / "models"
    if models.exists():
        for p in models.glob("ml_*.pkl"):
            p.unlink()

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _ml_section, _sector_of,
                                   _seed_universe, datetime, timedelta, timezone)
    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    names = {m["symbol"]: m.get("name", m["symbol"]) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    print("Chargement des prix…")
    data, mode, _real = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    print(f"Mode : {mode} · univers {len(data)}")

    print("Entraînement + validation (CV purgée)…")
    ml = _ml_section(data, sector_of, names)      # entraîne inline → persiste l'artefact
    if not ml.get("available"):
        print("⛔ Échantillon insuffisant."); return
    arts = list((ROOT / "models").glob("ml_*.pkl"))
    print(f"✅ Modèle entraîné · AUC OOS {ml.get('auc')} · edge {'OUI' if ml.get('edge_ok') else 'non'}")
    print(f"   Artefact : {arts[0] if arts else '(non écrit)'} · servi : {ml.get('served_from')}")
    print("   L'API chargera cet artefact (plus de réentraînement par requête).")

    # MLOps : tracking MLflow (López de Prado) — hyperparams + métriques + importances + artefact,
    # tag `production-ready` si edge OOS validé. NON bloquant (no-op si MLflow absent).
    try:
        from packages.ml.tracking import record_run, track_training
        imp = {r["feature"]: r["weight"] for r in ml.get("feature_importance", [])}
        # journal append-only SANS dépendance (source du suivi de drift + affichage front)
        record_run(metrics={"auc_oos": ml.get("auc") or 0.0, "edge_ok": 1.0 if ml.get("edge_ok") else 0.0},
                   params={"model": ml.get("model"), "validation": ml.get("validation"),
                           "n_train": ml.get("n_train"), "data_mode": mode},
                   status="production-ready" if ml.get("edge_ok") else "candidate")
        logged = track_training(
            run_name="train_model",
            params={"model": ml.get("model"), "horizon_days": ml.get("horizon_days"),
                    "validation": ml.get("validation"), "n_train": ml.get("n_train"),
                    "n_splits": ml.get("n_splits"), "data_mode": mode},
            metrics={"auc_oos": ml.get("auc") or 0.0, "edge_ok": 1.0 if ml.get("edge_ok") else 0.0},
            importances=imp, artifact=str(arts[0]) if arts else None,
            tags={"status": "production-ready" if ml.get("edge_ok") else "candidate",
                  "validation": "purged_cv_embargo"})
        print("   MLflow : " + ("logué (" + ("production-ready" if ml.get("edge_ok") else "candidate") + ")"
                                 if logged else "ignoré (mlflow absent)"))
    except Exception:  # noqa: BLE001 — le tracking ne doit jamais faire échouer l'entraînement
        pass


if __name__ == "__main__":
    main()
