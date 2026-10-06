"""make rapport-esperance — les quatre questions sur le livre de PRODUCTION.

Rejoue la règle de production (`preset_latest_weights_explique` + cœur QQQ, bande,
plancher, portail, exécution au close de la séance suivante), puis mesure :
  1. l'espérance nette d'un aller-retour (frais du barème + impact racine carrée) ;
  2. le livre contre QQQ + cash au même drawdown et à la même volatilité ;
  3. les paris indépendants et l'IC hors échantillon du classement tradé ;
  4. l'encours où l'espérance devient nulle.

  make rapport-esperance                  # décision tous les 5 j (rejeu publié)
  make rapport-esperance ARGS="--pas 1"   # rythme quotidien de la production (lent)

Écrit out/rapport_esperance.md (une page) et .json. Les horizons d'IC sont consignés au
registre sous les facteurs de `make ic-classement` (une re-mesure ne gonfle pas N).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SORTIE = ROOT / "out" / "rapport_esperance"


def _rejeu(data: dict, acmap: dict, pas: int) -> tuple | None:
    from packages.backtest.preset_rejeu import _prix_par_jour, cibles_rejouees, simuler
    from scripts.preset_replay import _coeur
    dd = float(os.environ.get("QUANT_DD_TARGET", "0.25"))
    params = {"dd_target": dd, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    prep = cibles_rejouees(data, pas=pas, params=params, coeur=_coeur(data) or None)
    if prep is None:
        return None
    cal, _brutes, cibles = prep
    prix = _prix_par_jour(data)
    res = simuler(cibles, prix, cal, classes=acmap)
    return (res, cibles, prix) if res.get("available") else None


def _q1(ars: list, data: dict) -> dict:
    from packages.research import aller_retour as ar
    from packages.research.capacite import Marche, _param, impact
    m = Marche(data)
    out = {}
    for y, cle in ((0.0, "q1_frais"), (0.5, "q1_y05"), (1.0, "q1_y10")):
        nets, w = [], []
        for a in ars:
            p = _param(m, a)
            if p is None:
                continue
            (adv_a, sg_a), (adv_v, sg_v) = p
            nets.append(ar.rendement_net(a, impact(a["q"], adv_a, sg_a, y),
                                         impact(a["q"], adv_v, sg_v, y)))
            w.append(a["notionnel"])
        out[cle] = ar.esperance(nets, w)
    return out


def _q2(res: dict, prix: dict) -> dict:
    from packages.backtest.preset_rejeu import _Cours
    from packages.research.ledger import deflation_params
    from packages.research.melange_meme_risque import comparer, rendements
    if "QQQ" not in prix:
        return {"q2_dd": {"available": False}, "q2_vol": {"available": False}}
    cours = _Cours({"QQQ": prix["QQQ"]})
    qqq = [cours("QQQ", j) for j in res["dates"]]
    if any(x is None for x in qqq):
        return {"q2_dd": {"available": False}, "q2_vol": {"available": False}}
    rl, rq = rendements(res["equity"]), rendements(qqq)
    n = deflation_params()[0]
    return {"q2_dd": comparer(rl, rq, n_essais=n, base="drawdown"),
            "q2_vol": comparer(rl, rq, n_essais=n, base="volatilite")}


def _q3(cibles: list, prix: dict, ars: list) -> dict:
    from packages.research import paris_independants as pi
    from packages.research.aller_retour import duree_jours
    det = (statistics.median(duree_jours(a) for a in ars) * 252 / 365) if ars else None
    return pi.resume(pi.par_decision(cibles, prix), det)


def _ic(data: dict, mode: str) -> dict:
    from packages.research.ic_classement import mesurer
    from scripts.ic_classement import _consigner
    res = mesurer(data)
    _consigner(res, 0, mode)
    return res


def _calculer(data: dict, acmap: dict, mode: str, pas: int) -> dict | None:
    from packages.research.aller_retour import apparier
    from packages.research.capacite import capacite
    from packages.research.rapport_esperance import verdict
    sortie = _rejeu(data, acmap, pas)
    if sortie is None:
        return None
    res, cibles, prix = sortie
    ars, ouverts = apparier(res["executions"])
    r = {"meta": {"mode": mode, "n_series": len(data), "pas": pas,
                  "debut": res["dates"][0], "fin": res["dates"][-1],
                  "capital": res["equity"][0], "n_ordres": res["n_ordres"],
                  "allers_retours": len(ars), "lots_ouverts_fin": ouverts},
         **_q1(ars, data), **_q2(res, prix), "q3": _q3(cibles, prix, ars),
         "ic": _ic(data, mode), "q4": capacite(ars, data, res["equity"][0])}
    r["verdict"] = verdict(r["q1_y10"], r["q2_dd"])     # Y prudent, même drawdown
    return r


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pas", type=int, default=5)
    a = p.parse_args()
    from packages.research.rapport_esperance import markdown
    from scripts.preset_replay import _donnees
    data, acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — sans objet.")
        return 1
    print(f"Rapport d'espérance : {len(data)} séries ({mode}), pas {a.pas} j — long.")
    r = _calculer(data, acmap, mode, a.pas)
    if r is None:
        print("Historique trop court pour rejouer.")
        return 1
    page = markdown(r)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.with_suffix(".md").write_text(page, encoding="utf-8")
    SORTIE.with_suffix(".json").write_text(json.dumps(r, ensure_ascii=False, indent=1,
                                                      default=str), encoding="utf-8")
    print(page)
    print(f"Écrit : {SORTIE.relative_to(ROOT)}.md / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
