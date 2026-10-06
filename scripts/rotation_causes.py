"""make rotation-causes — qui demande les ordres ? (audit de l'espérance, rang 4).

Rejoue les cibles de PRODUCTION (`preset_latest_weights_explique`, satellite seul, sans
cœur) sur les mêmes séries que `make preset-replay`, puis décompose leur turnover en
sélection (le top-12 change), échelle (l'exposition brute bouge) et redistribution
(ERC, tilt, plafond, blackout), et compte les allers-retours (sortie puis retour en
moins de 3 décisions).

  make rotation-causes                   # pas de 5 jours, comme le rejeu
  make rotation-causes ARGS="--pas 1"    # rythme quotidien de la production (lent)

Diagnostic en lecture seule : aucun essai au registre, aucun réglage modifié.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "rotation_causes.json"


def _pct(x) -> str:
    return "n/d" if x is None else f"{x * 100:5.1f} %"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pas", type=int, default=5)
    a = p.parse_args()
    from packages.backtest.preset_rejeu import cibles_rejouees
    from packages.research.rotation_causes import agreger
    from scripts.preset_replay import _donnees
    data, _acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — sans objet.")
        return 1
    dd = float(os.environ.get("QUANT_DD_TARGET", "0.25"))
    params = {"dd_target": dd, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    print(f"Cibles de production rejouées : {len(data)} séries ({mode}), "
          f"pas {a.pas} j.")
    prep = cibles_rejouees(data, pas=a.pas, params=params)
    if prep is None:
        print("Historique trop court.")
        return 1
    r = agreger(prep[1])
    print(f"  décisions               {r['n_decisions']}  "
          f"(vides : {r['decisions_vides']})")
    print(f"  turnover moyen / décision {_pct(r['turnover_moyen_par_decision'])}")
    for c in ("selection", "echelle", "redistribution"):
        print(f"  part {c:<15}    {_pct(r['part_' + c])}")
    print(f"  entrées / sorties       {r['n_entrees']} / {r['n_sorties']}")
    print(f"  allers-retours (≤ {r['fenetre_aller_retour']} déc.) "
          f"{r['allers_retours']}")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**r, "pas": a.pas, "mode": mode}, ensure_ascii=False,
                                 indent=1))
    print(f"Écrit : {SORTIE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
