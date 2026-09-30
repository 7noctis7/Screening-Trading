"""make simuler-horizons — horizon de détention × stratégie × sortie × fréquence de décision.

Grille PRÉ-ENREGISTRÉE (`config/horizons/2026-09-30_horizons.yaml`, empreinte imprimée) :
6 stratégies × 4 critères de sortie × 5 fréquences = 120 scénarios par actif, jugés sur
des fenêtres glissantes de 1, 3, 5 et 10 ans, face au buy & hold des mêmes fenêtres.
Chaque scénario est un essai consigné au registre ; la PBO (CSCV) dit si le classement
tient hors échantillon, le DSR si le meilleur survit au nombre d'essais.

Sources RÉELLES (mêmes options que `make comparer-strategies`) :
  --fmp FICHIER...          exports du connecteur FMP (quotidien)
  --vps-quotidien           base locale du VPS (actions / ETF)
  --vps-crypto 1h|4h|1d     crypto Binance (`data/crypto_intraday.db`)
  --aleatoire K --graine G  tirage reproductible parmi les titres éligibles

    make simuler-horizons ARGS="--vps-quotidien --debut 2015-01-01 --aleatoire 12"
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GRILLE = ROOT / "config" / "horizons" / "2026-09-30_horizons.yaml"


def _f(x, fmt: str) -> str:
    return "—" if not isinstance(x, (int, float)) or not math.isfinite(x) else fmt.format(x)


def _h(li: dict, H: int, cle: str) -> float:
    v = li["horizons"].get(H, {}).get(cle)
    return v if isinstance(v, (int, float)) else math.nan


def imprimer_dimensions(lignes: list[dict], horizons: list[int]) -> dict:
    from packages.backtest.horizons_stats import par_dimension
    tables = {"sharpe": par_dimension(lignes, "sharpe"), "cagr": par_dimension(lignes, "cagr"),
              "maxdd": par_dimension(lignes, "max_drawdown")}
    for H in horizons:
        tables[f"r{H}"] = par_dimension(lignes, lambda li, H=H: _h(li, H, "rend_annuel_median"))
        tables[f"b{H}"] = par_dimension(lignes, lambda li, H=H: _h(li, H, "part_bat_bh"))
    for dim in ("strategie", "sortie", "frequence"):
        print(f"\n— par {dim} (médianes) —  Sharpe  CAGR  maxDD  | "
              + "  ".join(f"{H} an(s): rend. / bat B&H" for H in horizons))
        for v in tables["sharpe"][dim]:
            cols = "  ".join(f"{_f(tables[f'r{H}'][dim][v], '{:+6.1%}')} / "
                             f"{_f(tables[f'b{H}'][dim][v], '{:4.0%}')}" for H in horizons)
            print(f"  {v:15s} {_f(tables['sharpe'][dim][v], '{:5.2f}')} "
                  f"{_f(tables['cagr'][dim][v], '{:+6.1%}')} "
                  f"{_f(tables['maxdd'][dim][v], '{:6.1%}')}  | {cols}")
    return tables


def imprimer_horizons(lignes: list[dict], horizons: list[int], bh: dict) -> dict:
    from packages.backtest.horizons_stats import meilleurs
    out = {}
    for H in horizons:
        top = meilleurs(lignes, lambda li, H=H: _h(li, H, "rend_annuel_median"), top=3)
        bhs = [b["horizons"][H]["rend_annuel_median"] for b in bh.values()
               if b["horizons"][H]["n"]]
        ref = sorted(bhs)[len(bhs) // 2] if bhs else math.nan
        print(f"\nHorizon {H} an(s) — buy & hold médian {_f(ref, '{:+.1%}')}/an :")
        if not top:
            print("  aucune fenêtre complète : UNCALIBRATED (historique trop court)")
        for t in top:
            print(f"  {t['id']:45s} {_f(t['valeur'], '{:+.1%}')}/an (médiane sur "
                  f"{t['n_actifs']} actifs)")
        out[H] = {"top": top, "buy_and_hold_median": ref}
    return out


def pbo_et_dsr(par_actif: dict, par_an: dict, n_prior: int) -> dict:
    from packages.research.explo_grille import classer
    n_total = sum(len(r["lignes"]) for r in par_actif.values())
    out = {}
    for sym, r in par_actif.items():
        classes, pbo = classer([{"id": li["id"]} for li in r["lignes"]], r["R"], par_an[sym],
                               n_prior + n_total - len(r["lignes"]))
        out[sym] = {"pbo": pbo.get("pbo"), "meilleur": classes[0]["id"],
                    "dsr_meilleur": classes[0]["dsr"]}
        print(f"  {sym:10s} PBO {_f(pbo.get('pbo'), '{:.2f}')} · meilleur Sharpe "
              f"{classes[0]['id']} → DSR {classes[0]['dsr']:.2f}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--fmp", nargs="+", metavar="FICHIER")
    src.add_argument("--vps-quotidien", action="store_true")
    src.add_argument("--vps-crypto", choices=("1h", "4h", "1d"))
    ap.add_argument("--grille", default=str(GRILLE))
    ap.add_argument("--debut", default="2020-01-01")
    ap.add_argument("--aleatoire", type=int, default=0)
    ap.add_argument("--graine", type=int, default=20260930)
    a = ap.parse_args()
    return executer(a)


def executer(a: argparse.Namespace) -> int:
    import yaml

    from packages.backtest.comparaison_strategies import tirage
    from packages.backtest.scenarios_horizons import grille_actif
    from packages.research.explo_grille import empreinte
    from packages.research.ledger import deflation_params
    from scripts.comparer_strategies import PAR_AN, _bars_fmp, _bars_vps, _eligibles
    g = yaml.safe_load(Path(a.grille).read_text(encoding="utf-8"))
    h = empreinte(g)
    univers, classes = _bars_fmp(a.fmp) if a.fmp else _bars_vps(a)
    choix = _eligibles(univers, a.debut)
    choix = tirage(choix, a.aleatoire, a.graine) if a.aleatoire else choix
    tf = a.vps_crypto or "1d"
    par_an = {s: PAR_AN[tf] if a.vps_crypto else (365.0 if classes.get(s) == "crypto"
                                                  else 252.0) for s in choix}
    print(f"Grille {g['nom']} [{h[:12]}] · {len(choix)} actifs : {', '.join(choix)} · "
          f"{tf} · depuis {a.debut}")
    par_actif = {s: grille_actif(univers[s], classes.get(s, "equity"), g, debut=a.debut,
                                 par_an=par_an[s]) for s in choix}
    lignes = [li | {"actif": s} for s, r in par_actif.items() for li in r["lignes"]]
    horizons = [int(x) for x in g["horizons_annees"]]
    tables = imprimer_dimensions(lignes, horizons)
    bh = {s: r["buy_and_hold"] for s, r in par_actif.items()}
    top = imprimer_horizons(lignes, horizons, bh)
    print("\nSurapprentissage (PBO par actif, DSR du meilleur Sharpe) :")
    n_prior, _ = deflation_params()
    stats = pbo_et_dsr(par_actif, par_an, n_prior)
    _ecrire(a, g, h, tf, choix, lignes, tables, top, stats, bh)
    return 0


def _ecrire(a, g, h, tf, choix, lignes, tables, top, stats, bh) -> None:
    from packages.research.ledger import append_record
    source = "fmp" if a.fmp else ("vps-quotidien" if a.vps_quotidien else "vps-crypto")
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"horizons:{h[:12]}:{source}:{tf}:{a.graine}",
                   "statut": "mesure", "n_essais": len(lignes),
                   "params": {"actifs": choix, "debut": a.debut, "grille": g["nom"]},
                   "source": "scripts/simuler_horizons.py (réel)"})
    sortie = ROOT / "out" / f"horizons_{source}_{tf}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"empreinte": h, "actifs": choix, "tables": tables,
                                  "horizons": top, "surapprentissage": stats,
                                  "buy_and_hold": bh, "lignes": lignes},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n→ {sortie.relative_to(ROOT)} · {len(lignes)} essais consignés au registre.")


if __name__ == "__main__":
    raise SystemExit(main())
