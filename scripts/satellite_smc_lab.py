"""make satellite-smc — SMCLXTP-A bat-il le setup de production (cœur QQQ + preset) ?

Rejoue les décisions de production date par date, puis remplace SEULEMENT le satellite
par SMCLXTP-A (équipondéré des titres où il est acheteur) : même cœur QQQ, mêmes dates,
même exécution, même bande, mêmes frais (`packages/backtest/satellite_smc.py`).

Règle écrite AVANT la mesure : SMCLXTP-A n'est MEILLEUR que si ΔSharpe apparié > 0 avec
p < 0,05 ET maxDD pas pire. Sinon : production conservée. Un essai, consigné au registre.

    make satellite-smc                  # pas de 5 jours, cœur QUANT_CORE_SPEC (qqq:0.5)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "satellite_smc.json"


def _imprimer(res: dict, coeur: dict) -> None:
    from scripts.preset_replay import _ligne
    st, d = res["stats"], res["delta"]
    print(f"\n{res['dates'][0]} → {res['dates'][-1]} · cœur {coeur or 'aucun'} · "
          f"SMCLXTP-A acheteur sur {res['titres_long_moyen']:.0f} titres en moyenne "
          f"({res['decisions_sans_long']} décisions sans aucun)\n")
    for k, nom in (("production", "PRODUCTION (cœur + preset)"),
                   ("smclxtp", "cœur + SMCLXTP-A")):
        print(_ligne(nom, st[k]) + f"  frais {res['frais'][k]:,.0f} $ · "
              f"{res['n_ordres'][k]} ordres")
    if d.get("disponible"):
        lo, hi = d["ic95"]
        print(f"\nΔSharpe SMCLXTP-A − production (apparié) {d['delta']:+.2f} "
              f"[{lo:+.2f} ; {hi:+.2f}]  p = {d['p']:.3f}  ({d['verdict']})")
    print(f"→ {res['verdict']}")


def _consigner(res: dict, pas: int, coeur: dict) -> None:
    from packages.research.ledger import append_record
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": "satellite_smclxtp_vs_production", "statut": "mesure",
                   "these": "SMCLXTP-A équipondéré à la place du satellite preset.",
                   "params": {"pas": pas, "coeur": coeur}, "verdict": res["verdict"],
                   "sharpe": res["stats"]["smclxtp"].get("sharpe"),
                   "periods_per_year": 252, "n_obs": len(res["dates"]),
                   "source": "make satellite-smc (réel)"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pas", type=int, default=5, help="jours de cotation entre décisions")
    a = ap.parse_args()
    from packages.backtest.preset_rejeu import cibles_rejouees
    from packages.backtest.satellite_smc import comparer_satellites
    from scripts.preset_replay import _coeur, _donnees

    data, acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — UNCALIBRATED.")
        return 1
    dd = float(os.environ.get("QUANT_DD_TARGET", "0.25"))
    params = {"dd_target": dd, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    coeur = _coeur(data)
    print(f"Production vs SMCLXTP-A : {len(data)} séries ({mode}), pas {a.pas} j — "
          f"patience, chaque date rappelle la production.")
    prep = cibles_rejouees(data, pas=a.pas, params=params, coeur=coeur or None)
    if prep is None:
        print("Indisponible : historique trop court.")
        return 1
    res = comparer_satellites(data, prep, coeur=coeur or None, classes=acmap)
    if not res.get("available"):
        print(f"Indisponible : {res.get('raison')}")
        return 1
    _imprimer(res, coeur)
    _consigner(res, a.pas, coeur)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**{k: v for k, v in res.items() if k != "dates"},
                                  "debut": res["dates"][0], "fin": res["dates"][-1],
                                  "mode_donnees": mode,
                                  "mesure_le": datetime.now(UTC).isoformat(timespec="seconds")},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n→ {SORTIE.relative_to(ROOT)} · 1 essai consigné au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
