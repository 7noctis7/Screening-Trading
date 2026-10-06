"""Publication du modèle d'edge : artefact servi, scores, diagnostics, garde-fou d'edge.

Serving DÉCOUPLÉ de l'entraînement (ticket #2) : le modèle final est rechargé depuis
un artefact frais (`make train` / cron) ; sinon il est entraîné ici puis persisté.
La clé de l'artefact inclut la version des features et du label
(`edge_transversal.signature`) : changer leur définition invalide l'ancien modèle.
"""

from __future__ import annotations

import numpy as np

from packages.ml import edge_diagnostics as diag
from packages.ml.edge_transversal import (
    NOMS,
    H,
    cv_purgee,
    importance,
    modele,
    signature,
)

N_SPLITS = 5
CONTRAT = {
    "question": ("le titre bat la médiane de ses pairs de la même semaine à ~1 mois, "
                 "frais aller-retour déduits"),
    "frais_inclus": True,
    "proba_par_titre": False,
    "motif": ("le nombre par titre est la sortie brute du modèle, "
              "pas une fréquence calibrée"),
}


def _servir(X, y, sig):
    """(modèle, métriques de l'artefact, persisté ?, origine, artefact_chargé ?)."""
    from packages.ml import artifact as art
    cache = art.load(sig)
    if cache is not None:
        metriques = art.metrics_from_payload(cache[1])
        return cache[0], metriques, True, "artefact (cron)", True
    model, _ = modele()
    model.fit(X, y)                              # entraînement inline (repli sûr)
    vide = art.metrics_payload(dsr=None, brier=None, auc=None)
    return model, vide, False, "inline", False


def _persister(sig, model, cal: dict, cv_auc) -> tuple[dict, bool]:
    """Le champion porte les nombres qui ont motivé son adoption — sinon aucun."""
    from packages.ml import artifact as art
    # DSR explicitement non calibré : un classifieur binaire ne produit pas de
    # série de rendements OOS, le fabriquer depuis l'AUC serait une fausse métrique.
    m = art.metrics_payload(dsr=None, auc=cv_auc,
                            brier=cal.get("brier_raw") if cal["available"] else None)
    ok = art.save(sig, model, {"fn": NOMS, "metrics": m})
    if not ok:                                   # calculées mais perdues : non publiées
        m = art.metrics_payload(dsr=None, brier=None, auc=None)
    return m, ok


def _edge(aucs: list[float]) -> tuple[bool, str, dict]:
    """QML-011 : un edge ne s'affirme que contre une distribution NULLE."""
    from packages.ml.validation_edge import edge_detecte
    e = edge_detecte(aucs)
    msg = ("Edge OOS détecté (test de permutation) — utilisable avec prudence."
           if e["edge"] else
           "Edge NON établi (UNCALIBRATED : sans test de permutation, une AUC de CV "
           "ne se distingue pas du hasard) — score indicatif, ne pas surpondérer.")
    return e["edge"], msg, e


def _scores(model, last: dict, names: dict, sector_of: dict):
    probs = {s: float(model.predict_proba([f])[0]) for s, f in last.items()}
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:15]
    conv = [{"symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
             "ml_score": round(p, 3)} for s, p in top]
    return {s: round(p, 3) for s, p in probs.items()}, conv


def publier(X, y, T0, T1, last, sector_of: dict, names: dict) -> dict:
    """Section ML du snapshot (mêmes clés qu'avant l'extraction du 06/10)."""
    _, model_name = modele()
    aucs = cv_purgee(X, y, T0, T1, N_SPLITS)
    cv_auc = round(float(np.mean(aucs)), 3) if aucs else None
    sig = signature(X, T1, last)
    model, metrics, persiste, servi, charge = _servir(X, y, sig)
    imp = importance(model, NOMS, X, y)
    mx = max((v for _, v in imp), default=1.0) or 1.0
    scores, conviction = _scores(model, last, names, sector_of)
    cal = diag.calibration(X, y)
    diag.tracer_mlflow(model_name, H, N_SPLITS, len(X), cv_auc)
    edge_ok, edge_msg, edge_detail = _edge(aucs)
    if not charge:
        metrics, persiste = _persister(sig, model, cal, cv_auc)
    return {
        "available": True, "model": model_name, "horizon_days": H,
        "validation": f"CV purgée + embargo (k={N_SPLITS})", "served_from": servi,
        "edge_ok": edge_ok, "edge_message": edge_msg, "auc_floor": 0.52,
        "edge_detail": edge_detail, "contrat": dict(CONTRAT),
        "n_train": int(len(X)), "n_splits": len(aucs), "auc": cv_auc,
        "artifact_metrics": metrics, "artifact_persisted": persiste,
        "feature_importance": [{"feature": f, "weight": round(v / mx, 3)}
                               for f, v in imp],
        "top_conviction": conviction, "scores": scores,
        "calibration": cal, "conformal": diag.conformal(X, y),
        "walk_forward": diag.walk_forward(X, y),
        "meta_labeling": diag.meta_labeling(X, y),
        "drift": diag.derive(X, NOMS), "training_history": diag.historique(),
    }
