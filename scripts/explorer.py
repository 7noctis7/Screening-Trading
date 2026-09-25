"""make explorer — banc d'exploration PRÉ-ENREGISTRÉ : classer des règles sans se mentir.

Deux temps, et seulement deux :

  1. EXPLORATION (en échantillon, jusqu'à `fin_in_sample` de la grille)
       python scripts/explorer.py --grille config/exploration/2026-09-25_quotidien.yaml
     Classe TOUS les scénarios de la grille (univers × sélection × pondération × overlay ×
     rythme de rééquilibrage), avec le Sharpe déflaté par le nombre total d'essais (DSR) et
     la probabilité de surapprentissage du classement (PBO). La période cachée n'est JAMAIS
     lue ici — le moteur ne reçoit pas les barres qui la composent.

  2. VERDICT (période cachée, UNE seule lecture par grille)
       python scripts/explorer.py --grille … --holdout "id1" ["id2" "id3"]
     Évalue 1 à 3 scénarios CHOISIS sur le classement, plus la référence acheter-conserver.
     Une seconde lecture est refusée : le registre `research/holdout_registre.jsonl` garde
     la trace. Modifier la grille pour relire = nouvelle empreinte = nouvel essai, compté.

Règle d'or : choisir le premier du classement n'est PAS un résultat. C'est le verdict sur
la période cachée, déflaté, qui en est un — et « indiscernable de la référence » est le
verdict le plus probable.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

DIMENSIONS = ("univers", "selection", "ponderation", "overlay", "nom_pas")


def _grille(chemin: str) -> dict:
    import yaml
    return yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))


def _donnees(grille: dict) -> dict:
    from packages.research.explo_donnees import charger_intraday, charger_quotidien
    tf = grille.get("timeframe", "1d")
    return charger_quotidien() if tf == "1d" else charger_intraday(tf)


def _bornes(d: dict, grille: dict) -> tuple[float, int, int] | None:
    from packages.research.explo_donnees import _par_an, index_de_date
    from packages.research.explo_regles import barres
    if len(d["dates"]) < 3:
        return None
    par_an = _par_an(d["dates"])
    debut = barres(252 + 21, par_an) + 1          # le momentum 12-1 doit exister
    fin = index_de_date(d["dates"], str(grille["fin_in_sample"]))
    return (par_an, debut, fin) if fin - debut >= 2 * par_an else None


def _n_anterieurs(facteur: str) -> int:
    """Essais du programme HORS cette grille (elle compte déjà ses propres scénarios)."""
    from packages.research.ledger import read_records
    vus: dict[str, int] = {}
    for r in read_records():
        f = r.get("facteur")
        if f and f != facteur:
            ne = r.get("n_essais")
            vus[f] = max(vus.get(f, 1), ne if isinstance(ne, int) and ne > 0 else 1)
    return sum(vus.values())


def _ligne(d: dict) -> str:
    return (f"  {d.get('rang', '·'):>4}  {d['id']:52s} CAGR {d['cagr'] * 100:6.1f} %  "
            f"Sharpe {d['sharpe']:5.2f}  maxDD {d['max_dd'] * 100:6.1f} %  "
            f"DSR {d['dsr']:.2f}  rot./an {d.get('turnover_an', 0):5.1f}")


def _par_dimension(classes: list[dict]) -> dict:
    """Sharpe MÉDIAN par valeur de chaque dimension : plus robuste que le premier du
    classement, parce qu'une médiane sur des dizaines de scénarios ne se gagne pas à la
    chance."""
    out = {}
    for dim in DIMENSIONS:
        vals = sorted({c[dim] for c in classes})
        out[dim] = {v: {"sharpe_median": round(float(np.median(
            [c["sharpe"] for c in classes if c[dim] == v])), 3),
            "n": sum(1 for c in classes if c[dim] == v)} for v in vals}
    return out


def _imprimer(classes: list[dict], pbo: dict, top: int, par_dim: dict) -> None:
    print(f"\nCLASSEMENT EN ÉCHANTILLON — {len(classes)} scénarios (Sharpe annualisé)")
    for d in classes[:top]:
        print(_ligne(d))
    print("  …")
    for d in classes[-5:]:
        print(_ligne(d))
    print("\nRéférences acheter-conserver (univers à un actif, sans overlay) :")
    for d in classes:
        if d["univers"] in ("qqq", "btc") and d["overlay"] == "aucun" and d["pas"] == 1:
            print(_ligne(d))
    print("\nSharpe médian par dimension :")
    for dim, vals in par_dim.items():
        txt = " · ".join(f"{v} {s['sharpe_median']:+.2f} (n={s['n']})" for v, s in vals.items())
        print(f"  {dim:12s} {txt}")
    if pbo.get("available"):
        print(f"\nPBO (CSCV) = {pbo['pbo']:.2f} — probabilité que le champion en échantillon "
              "finisse sous la médiane hors échantillon. > 0,5 : le classement est du bruit.")


def explorer(grille: dict, h: str, top: int) -> int:
    from packages.research.explo_donnees import executer
    from packages.research.explo_grille import classer, scenarios
    from packages.research.ledger import append_record
    d = _donnees(grille)
    b = _bornes(d, grille)
    if b is None or (grille.get("timeframe", "1d") == "1d" and len(d["noms"]) < 30):
        print(f"⛔ données insuffisantes ({d['mode']}, {len(d['noms'])} séries) — UNCALIBRATED.")
        return 1
    par_an, debut, fin = b
    print(f"Grille {grille.get('nom')} [{h[:8]}] · {len(d['noms'])} séries ({d['mode']}) · "
          f"{d['dates'][debut][:10]} → {d['dates'][fin][:10]} en échantillon · "
          f"{par_an:.0f} barres/an\nPériode cachée : après {grille['fin_in_sample']} — "
          "non lue.\n")
    R, lignes = executer(d, scenarios(grille), debut, fin, par_an)
    facteur = f"exploration:{h[:12]}"
    classes, pbo = classer(lignes, R, par_an, _n_anterieurs(facteur))
    par_dim = _par_dimension(classes)
    _imprimer(classes, pbo, top, par_dim)
    append_record({"date": datetime.now(UTC).date().isoformat(), "facteur": facteur,
                   "statut": "exploration", "n_essais": len(classes),
                   "these": f"Balayage pré-enregistré {grille.get('nom')}",
                   "params": {"empreinte": h, "fin_in_sample": str(grille["fin_in_sample"])},
                   "source": "make explorer (réel)"})
    sortie = ROOT / "out" / f"exploration_{h[:8]}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"grille": grille, "empreinte": h, "pbo": pbo,
                                  "par_dimension": par_dim, "classement": classes},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n→ {sortie.relative_to(ROOT)} · {len(classes)} essais consignés au registre.")
    print("Prochaine étape : choisir 1 à 3 scénarios (idéalement portés par une dimension "
          "robuste, pas le seul premier) puis --holdout.")
    return 0


def verdict(grille: dict, h: str, ids: list[str]) -> int:
    from packages.backtest.preset_rejeu import comparer_sharpe
    from packages.research.explo_donnees import executer
    from packages.research.explo_grille import classer, consommer_holdout, scenarios
    from packages.research.ledger import deflation_params
    tous = {s["id"]: s for s in scenarios(grille)}
    inconnus = [i for i in ids if i not in tous]
    if inconnus or not 1 <= len(ids) <= 3:
        print(f"⛔ 1 à 3 identifiants de la grille attendus ; inconnus : {inconnus}")
        return 1
    d = _donnees(grille)
    b = _bornes(d, grille)
    if b is None:
        print("⛔ données insuffisantes — UNCALIBRATED.")
        return 1
    par_an, _, fin = b
    refs = [s for s in tous.values() if s["univers"] in ("qqq", "btc")
            and s["overlay"] == "aucun" and s["pas"] == 1 and s["id"] not in ids]
    consommer_holdout(h, ids)                     # inscrit AVANT le calcul : un crash compte
    R, lignes = executer(d, [tous[i] for i in ids] + refs, fin - 1, len(d["dates"]) - 1,
                         par_an, bavard=False)
    R = R[1:]                                     # la barre d'entrée appartient à l'échantillon
    n_total, _ = deflation_params()
    classes, _ = classer(lignes, R, par_an, max(0, n_total - R.shape[1]))
    print(f"\nPÉRIODE CACHÉE — {d['dates'][fin][:10]} → {d['dates'][-1][:10]} · "
          f"lue une fois (grille {h[:8]}) · DSR déflaté par N = {n_total}")
    for c in classes:
        print(_ligne(c))
    courbes = {lg["id"]: list(np.cumprod(1 + R[:, j])) for j, lg in enumerate(lignes)}
    for r in refs:
        if r["id"] not in courbes:
            continue
        for i in ids:
            if i in courbes:
                c = comparer_sharpe(courbes[r["id"]], courbes[i])
                if c.get("disponible"):
                    print(f"  {i} vs {r['id']} : ΔSharpe {c['delta']:+.2f} "
                          f"[{c['ic95'][0]:+.2f} ; {c['ic95'][1]:+.2f}] → {c['verdict']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grille", required=True, help="YAML de la grille pré-enregistrée")
    ap.add_argument("--holdout", nargs="+", metavar="ID", help="1 à 3 scénarios à juger")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    from packages.research.explo_grille import empreinte
    grille = _grille(a.grille)
    h = empreinte(grille)
    return verdict(grille, h, a.holdout) if a.holdout else explorer(grille, h, a.top)


if __name__ == "__main__":
    raise SystemExit(main())
