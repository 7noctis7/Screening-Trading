"""make labo-auc — les quatre variantes PRÉ-ENREGISTRÉES du modèle d'edge, jugées
hors échantillon (protocole et règle : `packages/ml/labo_auc.py`).

  make labo-auc     # ~10-20 min sur le VPS (Gradient Boosting, 4 × 6 entraînements)

Lecture seule : aucun modèle servi, aucun réglage modifié. Quatre essais consignés au
registre (données réelles seulement). Une variante RETENUE n'est pas adoptée : son
adoption est une PR à part, sous drapeau éteint par défaut.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "labo_auc.json"


def _fmt(x, d=3, signe=True) -> str:
    if x is None:
        return "n/d"
    return f"{x:+.{d}f}" if signe else f"{x:.{d}f}"


def _ligne(r: dict) -> str:
    e, iv = r["ic_ecart"], r["ecart_vs_v0_ic95"]
    ecart = "—" if iv is None else f"[{iv[0]:+.4f} ; {iv[1]:+.4f}]"
    return (f"  {r['variante']:<20} AUC CV {_fmt(r['auc_cv'], signe=False)}"
            f" ± {_fmt(r['auc_cv_sd'], signe=False)}"
            f" · IC CV {_fmt(r['ic_cv']['ic'], 4)}"
            f" · IC écart {_fmt(e['ic'], 4)} (t {_fmt(e['t'], 2)},"
            f" {e.get('n_disjointes', 0)} sem.) · vs V0 {ecart}"
            f" · {'RETENUE' if r['retenue'] else '—'}")


def _consigner(res: dict, mode: str) -> int:
    """Un essai par variante, sur données réelles seulement."""
    from packages.ml.edge_transversal import VERSION_FEATURES, H
    from packages.research.ledger import append_record
    if mode == "synthetic":
        return 0
    jour = datetime.now(UTC).date().isoformat()
    for r in res["variantes"]:
        append_record({
            "date": jour, "facteur": f"ml_edge:variante:{r['variante']}",
            "statut": "retenue" if r["retenue"] else "mesure", "horizon": H,
            "n_essais": 1, "params": {"base": VERSION_FEATURES},
            "these": "La représentation change l'IC hors échantillon du score ML.",
            "auc_cv": r["auc_cv"], "ic_ecart": r["ic_ecart"]["ic"],
            "t_ecart": r["ic_ecart"]["t"], "ecart_vs_v0_ic95": r["ecart_vs_v0_ic95"],
            "protocole": "pré-enregistré 07/10 : CV purgée 80 %, écart 20 %, "
                         "IC hebdo vs rendement relatif, bootstrap par blocs",
            "source": "make labo-auc (réel)"})
    return len(res["variantes"])


def main() -> int:
    from packages.research.gel_ic import autoriser_features
    ok, msg = autoriser_features(ROOT / "out" / "ic_classement.json")
    if not ok:
        print(msg)
        print("Labo non lancé — aucun essai consigné.")
        print("Les features restent gelées.")
        return 0
    from apps.api.snapshot import _sector_of, _seed_universe
    from packages.ml.edge_transversal import NOMS, modele
    from packages.ml.labo_auc import banc
    from packages.ml.variantes_auc import construire
    from scripts.preset_replay import _donnees
    data, _acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — sans objet.")
        return 1
    secteurs = {m["symbol"]: _sector_of(m) for m in _seed_universe()}
    jeu = construire(data, secteurs)
    if jeu is None:
        print("Historique trop court.")
        return 1
    print(f"Labo AUC : {len(data)} séries ({mode}), {len(jeu['R'])} échantillons, "
          "4 variantes pré-enregistrées — long.")
    res = banc(jeu, lambda: modele()[0], NOMS)
    for r in res["variantes"]:
        print(_ligne(r))
    print("\n  Repère : AUC 0,52 ≈ IC de rang 0,05 ; AUC 0,60 ≈ IC 0,21 (au-delà des "
          "meilleurs facteurs publiés : soupçonner une fuite avant de célébrer).")
    print(f"  Retenues : {', '.join(res['retenues']) or 'aucune — rien ne change'}.")
    n = _consigner(res, mode)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**res, "mode": mode}, ensure_ascii=False, indent=1,
                                 default=str), encoding="utf-8")
    print(f"Écrit : {SORTIE.relative_to(ROOT)} · {n} essai(s) consigné(s) au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
