"""make preset-replay — mesure la règle de PRODUCTION, pas une cousine (QML-001).

Rejoue `preset_latest_weights_explique` date par date sur les données connues à chaque date,
exécute au close suivant avec la bande, le plancher et le portail de risque de `run_live`,
puis imprime le résultat À CÔTÉ de `preset_backtest` sur les mêmes prix : l'écart entre les
deux est exactement ce que les chiffres publiés jusqu'ici ne mesuraient pas.

  export QUANT_PRICE_DB=/chemin/YAHOO.db     # données RÉELLES obligatoires
  make preset-replay                          # pas de 5 jours (≈ minutes)
  python scripts/preset_replay.py --pas 1     # fidèle au rythme quotidien (lent)

Chaque passage est consigné au registre des hypothèses : une mesure est un essai.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "preset_rejeu.json"


def _donnees() -> tuple[dict, dict, str]:
    """Mêmes prix et même univers négociable que `build_snapshot` pour la production."""
    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    from packages.execution.routing import is_tradeable

    instr = _seed_universe()
    acmap = {m["symbol"]: m["asset_class"] for m in instr}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode, reels = _load_prices(instr, {m["symbol"]: _sector_of(m) for m in instr},
                                     fin - timedelta(days=_HISTORY_DAYS), fin, seed=7)
    negociables = {s: b for s, b in data.items()
                   if s in reels and b and is_tradeable(s, acmap.get(s, "equity"))}
    return negociables, acmap, mode


def _coeur(data: dict) -> dict:
    """Le cœur indiciel de `QUANT_CORE_SPEC` (seul `qqq` est rejoué), comme en production."""
    spec = dict(p.split(":", 1) for p in os.environ.get("QUANT_CORE_SPEC", "qqq:0.5").split(",")
                if ":" in p)
    part = float(spec.get("qqq", 0) or 0)
    return {"QQQ": part} if part > 0 and "QQQ" in data else {}


def _ligne(nom: str, st: dict) -> str:
    return (f"  {nom:34s} CAGR {st.get('annualized', 0) * 100:6.1f} %  Sharpe "
            f"{st.get('sharpe', 0):5.2f}  maxDD {st.get('max_drawdown', 0) * 100:6.1f} %")


def _consigner(res: dict, pas: int) -> None:
    from packages.research.ledger import append_record
    st = res.get("stats") or {}
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": "preset_production_rejeu", "statut": "mesure",
                   "these": "Rejeu date par date de la règle de production (QML-001).",
                   "params": {"pas": pas, "coeur": res.get("coeur")},
                   "sharpe": st.get("sharpe"), "periods_per_year": 252,
                   "n_obs": len(res.get("equity") or []),
                   "source": "make preset-replay (réel)"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pas", type=int, default=5, help="jours de cotation entre décisions")
    ap.add_argument("--sans-coeur", action="store_true", help="satellite seul, sans QQQ")
    a = ap.parse_args()
    from packages.backtest.preset_backtest import preset_backtest
    from packages.backtest.preset_rejeu import rejouer

    data, acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — rejeu sans objet.")
        print('   Branche tes données : export QUANT_PRICE_DB="$HOME/Desktop/YAHOO.db"')
        return 1
    dd = float(os.environ.get("QUANT_DD_TARGET", "0.25"))
    params = {"dd_target": dd, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    coeur = {} if a.sans_coeur else _coeur(data)
    print(f"Rejeu de la production : {len(data)} séries ({mode}), pas {a.pas} j, "
          f"cœur {coeur or 'aucun'} — patience, chaque date rappelle la production.")
    res = rejouer(data, pas=a.pas, params=params, coeur=coeur or None, classes=acmap)
    if not res.get("available"):
        print(f"Indisponible : {res.get('raison')}")
        return 1
    ancien = preset_backtest(data, asset_classes=acmap, dd_target=dd, band=0.03)
    print(f"\n{res['dates'][0]} → {res['dates'][-1]} · {res['n_decisions']} décisions "
          f"({res['n_decisions_vides']} sans poids) · {res['n_ordres']} ordres · "
          f"frais {res['frais']:,.0f} $\n")
    print(_ligne("REJEU — règle de production", res["stats"]))
    if ancien.get("available"):
        print(_ligne("preset_backtest (≠ production)", ancien["preset"]))
    print("\nÉcarts connus du rejeu :")
    for e in res["ecarts_connus"]:
        print(f"  · {e}")
    _consigner(res, a.pas)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**res, "mode_donnees": mode,
                                  "mesure_le": datetime.now(UTC).isoformat(timespec="seconds")},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {SORTIE.relative_to(ROOT)} · consigné au registre des hypothèses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
