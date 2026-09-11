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

# MATÉRIEL — avant tout autre import du projet, et surtout avant pandas.
#
# `activer_cudf()` pose un crochet d'importation qui doit précéder l'entrée de pandas
# en mémoire : posé après, il ne fait plus rien ET ne lève rien, ce qui donnerait un
# script se croyant accéléré alors qu'il tourne sur processeur. Sur Mac, cudf est
# absent : la fonction rend False sans bruit et pandas reste pandas.
from packages.common.device import activer_cudf, banniere  # noqa: E402

activer_cudf()
banniere()


ABRI = ".rollback"        # sous-dossier de models/ — hors du chemin de chargement


def _artefacts(models: Path) -> list[Path]:
    """Le modèle ET son empreinte. `ml_*.pkl` ne matche PAS `ml_*.pkl.sha256`."""
    return sorted(models.glob("ml_*.pkl")) + sorted(models.glob("ml_*.pkl.sha256"))


def _mettre_de_cote(models: Path) -> Path | None:
    """Écarte le champion du chemin de chargement SANS le détruire.

    POURQUOI CETTE FONCTION EXISTE. Il faut bien retirer l'artefact du chemin :
    `artifact.load()` le trouverait et l'entraînement n'aurait pas lieu — `make train`
    deviendrait un no-op silencieux. L'ancienne version réglait ça en le SUPPRIMANT,
    avant d'entraîner. Un entraînement qui échoue, ou un échantillon jugé insuffisant,
    laissait alors `models/` VIDE : plus de champion, et plus rien pour le dire, car
    `cron_daily.sh` termine la ligne par `|| true`. L'API retombait sur un entraînement
    inline à chaque requête — le découplage entraînement/serving disparaissait sans
    qu'aucune ligne de journal ne change. On DÉPLACE donc, et on ne détruit qu'une
    fois le remplaçant écrit.
    """
    art = _artefacts(models)
    if not art:
        return None
    abri = models / ABRI
    abri.mkdir(parents=True, exist_ok=True)
    for f in art:
        f.replace(abri / f.name)
    return abri


def _restaurer(abri: Path | None) -> int:
    """Remet le champion en place. Retourne le nombre de fichiers rendus."""
    if abri is None or not abri.exists():
        return 0
    rendus = 0
    for f in sorted(abri.iterdir()):
        f.replace(abri.parent / f.name)
        rendus += 1
    abri.rmdir()
    return rendus


def _oublier(abri: Path | None) -> None:
    """Le remplaçant est écrit : l'ancien peut partir."""
    if abri is None or not abri.exists():
        return
    for f in sorted(abri.iterdir()):
        f.unlink()
    abri.rmdir()


def main() -> None:
    models = ROOT / "models"
    models.mkdir(parents=True, exist_ok=True)
    _restaurer(models / ABRI)      # un run tué en plein vol a pu laisser l'abri
    abri = _mettre_de_cote(models)     # champion écarté, pas supprimé

    from datetime import timezone

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _ml_section, _sector_of,
                                   _seed_universe, datetime, timedelta)
    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    names = {m["symbol"]: m.get("name", m["symbol"]) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    print("Chargement des prix…")
    data, mode, _real = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    print(f"Mode : {mode} · univers {len(data)}")

    print("Entraînement + validation (CV purgée)…")
    try:
        ml = _ml_section(data, sector_of, names)   # entraîne → persiste l'artefact
    except Exception:
        rendus = _restaurer(abri)
        print(f"⛔ Entraînement en échec — champion restauré ({rendus} fichier(s)).")
        raise
    arts = list(models.glob("ml_*.pkl"))
    if not ml.get("available") or not arts:
        rendus = _restaurer(abri)
        motif = ("échantillon insuffisant" if not ml.get("available")
                 else "aucun artefact écrit")
        print(f"⛔ {motif.capitalize()} — champion restauré ({rendus} fichier(s)).")
        raise SystemExit(1)
    _oublier(abri)                                # le remplaçant est en place
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
