"""make meta-smc — le méta-filtre ML sait-il trier les signaux LONG de SMCLXTP-A ?

Événements = `long_signal` de SMCLXTP-A (causal) sur chaque titre négociable ; labels =
triple barrière en ATR ; validation = CV purgée + distribution NULLE par permutation
(`packages/ml/meta_smc.py`). Le filtre n'est déclaré utilisable que s'il bat la
distribution nulle ET améliore la moitié chronologique qui n'a pas fixé son seuil.
Chaque passage est un essai consigné au registre des hypothèses.

    export QUANT_PRICE_DB=/chemin/YAHOO.db       # données RÉELLES obligatoires
    make meta-smc                                 # LightGBM, swing 50
    make meta-smc ARGS="--modele logit --swing 20"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "meta_smc.json"


def _imprimer(rapport: dict) -> None:
    print(f"\n{rapport['n_evenements']} événements LONG · taux de gain brut "
          f"{(rapport['taux_base'] or 0):.1%} · rendement moyen {(rapport['rend_moyen'] or 0):+.2%}")
    edge = rapport.get("edge") or {}
    if edge:
        print(f"AUC hors échantillon {edge.get('auc_moyenne')} · p de permutation "
              f"{edge.get('p_permutation')} ({edge.get('motif')})")
    ev = (rapport.get("seuil") or {}).get("evaluation")
    if ev:
        print(f"Moitié d'évaluation : {ev['n_gardes']}/{ev['n_evalues']} gardés · "
              f"rendement {ev['rend_moyen_filtre']:+.2%} filtré contre "
              f"{ev['rend_moyen_tous']:+.2%} sans filtre")
    print(f"→ statut {rapport['statut']} · filtre utilisable : "
          f"{'OUI' if rapport['filtre_utilisable'] else 'NON'} ({rapport.get('motif')})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modele", default="lightgbm", choices=("lightgbm", "xgboost", "logit"))
    ap.add_argument("--swing", type=int, default=50, help="swing_length = pivot_length")
    a = ap.parse_args()
    from packages.ml.meta_smc import Reglages, analyser
    from packages.research.ledger import append_record
    from scripts.preset_replay import _donnees

    data, _, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — UNCALIBRATED.")
        return 1
    r = Reglages(swing_length=a.swing, pivot_length=a.swing, modele=a.modele)
    print(f"SMCLXTP-A × méta-filtre {a.modele} : {len(data)} séries ({mode}), swing {a.swing}")
    rapport = analyser(data, r)
    _imprimer(rapport)
    edge = rapport.get("edge") or {}
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"meta_smc:{a.modele}:{a.swing}", "statut": "mesure",
                   "these": "Le méta-filtre trie les LONG de SMCLXTP-A (ADR-0209).",
                   "params": asdict(r), "auc": edge.get("auc_moyenne"),
                   "p_permutation": edge.get("p_permutation"),
                   "verdict": "utilisable" if rapport["filtre_utilisable"] else "non utilisable",
                   "source": "make meta-smc (réel)"})
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**rapport, "mode_donnees": mode, "reglages": asdict(r),
                                  "mesure_le": datetime.now(UTC).isoformat(timespec="seconds")},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    chemin = SORTIE.relative_to(ROOT) if SORTIE.is_relative_to(ROOT) else SORTIE
    print(f"→ {chemin} · consigné au registre des hypothèses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
