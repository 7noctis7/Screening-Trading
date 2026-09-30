"""Grille multi-horizons : court (< 1 an), moyen (1-5 ans), long (5-10 ans).

    python -m packages.backtest.grid_runner --timeframes daily weekly monthly \\
        --horizons 1y 3y 5y 10y --rebalance daily weekly monthly quarterly yearly \\
        --export-report docs/SIMULATION_RESULTS.md

Menus PRÉ-ENREGISTRÉS par horizon (`config/horizons/2026-09-30_multi_horizons.yaml`,
commité avant tout résultat). Chaque menu croise stratégies × sorties × fréquences ; le
moteur, les frais et les fenêtres d'horizon sont ceux de `scenarios_horizons` (signal au
close → ouverture suivante, stops en séance avec l'hypothèse défavorable, fenêtres
glissantes de H années COMPLÈTES face au buy & hold).

Par configuration : Sharpe, DSR (déflaté par TOUS les essais du programme), maxDD,
Calmar, taux de gain, profit factor, turnover annualisé. Par actif : PBO (CSCV). Ce qui
est demandé mais pas testable honnêtement (score ML, fondamentaux point-in-time, HMM…)
est ÉCRIT dans le rapport comme UNCALIBRATED, jamais simulé avec des données inventées.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
MENUS = ROOT / "config" / "horizons" / "2026-09-30_multi_horizons.yaml"
REBAL = {"daily": "jour", "weekly": "semaine", "monthly": "mois", "quarterly": "trimestre",
         "yearly": "annee"}
HORIZONS = {"1y": 1, "3y": 3, "5y": 5, "10y": 10}
TF = {"daily": ("1d", None), "weekly": ("1w", lambda d: d.isocalendar()[:2]),
      "monthly": ("1M", lambda d: (d.year, d.month))}
PAR_AN_TF = {"weekly": 52.0, "monthly": 12.0}
# Une fréquence de décision plus fine que la barre relit la même barre : scénario identique
# (doublon mécanique, pas une sélection) — elle n'est pas rejouée.
_FINESSE = {"jour": 1, "semaine": 2, "mois": 3, "trimestre": 4, "annee": 5}
_TF_MIN = {"daily": 1, "weekly": 2, "monthly": 3}
METRIQUES = ("sharpe", "max_drawdown", "calmar", "win_rate", "profit_factor",
             "turnover_annuel", "cagr", "trades")


def charger_menus(chemin: Path | str = MENUS) -> dict:
    import yaml
    return yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))


def menus_actifs(g: dict, horizons: list[str], rebalance: list[str]) -> dict[str, dict]:
    """Menus restreints aux horizons et fréquences demandés (intersection)."""
    inconnus = [h for h in horizons if h not in HORIZONS] + \
        [r for r in rebalance if r not in REBAL]
    if inconnus:
        raise ValueError(f"valeurs inconnues : {inconnus} (horizons {list(HORIZONS)}, "
                         f"rebalance {list(REBAL)})")
    hs, fr = {HORIZONS[h] for h in horizons}, {REBAL[r] for r in rebalance}
    out = {}
    for nom, m in g["menus"].items():
        H = [x for x in m["horizons_annees"] if x in hs]
        F = [f for f in m["frequences"] if f in fr]
        if H and F:
            out[nom] = {**m, "horizons_annees": H, "frequences": F,
                        **{k: g[k] for k in ("atr", "k_tp", "k_suiveur", "pas_fenetres_jours")}}
    return out


def plan(actifs: dict[str, dict], timeframes: list[str], n_actifs: int) -> list[tuple]:
    """(timeframe, menu, réglages, n_essais) — fréquences plus fines que la barre retirées."""
    out = []
    for tf in timeframes:
        if tf not in TF:
            raise ValueError(f"timeframe inconnu : {tf} ({list(TF)})")
        for nom, m in actifs.items():
            F = [f for f in m["frequences"] if _FINESSE[f] >= _TF_MIN[tf]]
            if F:
                n = len(m["strategies"]) * len(m["sorties"]) * len(F) * n_actifs
                out.append((tf, nom, {**m, "frequences": F}, n))
    return out


def reechantillonner(bars: list, tf: str) -> list:
    """Barres quotidiennes → hebdomadaires / mensuelles. Une barre agrégée porte la date de
    la DERNIÈRE séance de sa période : rien d'une période suivante n'y entre."""
    if tf == "daily":
        return bars
    code, cle = TF[tf]
    groupes: list[list] = []
    for b in bars:
        if groupes and cle(groupes[-1][-1].ts.date()) == cle(b.ts.date()):
            groupes[-1].append(b)
        else:
            groupes.append([b])
    return [replace(g[-1], timeframe=code, open=g[0].open, high=max(x.high for x in g),
                    low=min(x.low for x in g), volume=sum(x.volume for x in g))
            for g in groupes]


def _med(xs: list) -> float:
    xs = [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]
    return float(median(xs)) if xs else math.nan


def _top(lignes: list[dict], dsr: dict, horizons: list[int], k: int = 5) -> list[dict]:
    """Configurations classées par Sharpe MÉDIAN entre actifs (pas le meilleur actif)."""
    ids: dict[str, list[dict]] = {}
    for li in lignes:
        ids.setdefault(li["id"], []).append(li)
    out, vides = [], 0
    for i, ls in ids.items():
        if not _med([x.get("trades") for x in ls]) > 0:
            vides += 1              # indicateur jamais défini (ex. MM200 en mensuel = 16 ans)
            continue
        ligne = {"id": i, **{m: _med([x.get(m) for x in ls]) for m in METRIQUES},
                 "dsr_median": _med(dsr.get(i, []))}
        for H in horizons:
            ligne[f"rend_{H}a"] = _med([x["horizons"][H]["rend_annuel_median"] for x in ls])
            ligne[f"bat_bh_{H}a"] = _med([x["horizons"][H]["part_bat_bh"] for x in ls])
        out.append(ligne)
    out.sort(key=lambda d: d["sharpe"] if math.isfinite(d["sharpe"]) else -1e9, reverse=True)
    return out[:k], vides


def _surapprentissage(par_actif: dict, n_prior: int) -> tuple[dict, dict]:
    """DSR de chaque configuration et PBO par actif. `n_prior` inclut déjà les essais des
    autres blocs : N = tous les essais du programme."""
    from packages.research.explo_grille import classer
    n_total = sum(len(r["lignes"]) for r, _ in par_actif.values())
    dsr: dict[str, list] = {}
    pbo: dict[str, float | None] = {}
    for s, (r, ppy) in par_actif.items():
        if r["R"].shape[0] < 30:
            pbo[s] = None
            continue
        classes, p = classer([{"id": li["id"]} for li in r["lignes"]], r["R"], ppy,
                             n_prior + n_total - len(r["lignes"]))
        pbo[s] = p.get("pbo")
        for c in classes:
            dsr.setdefault(c["id"], []).append(c["dsr"])
    return dsr, pbo


def _bloc(series: dict, classes: dict, m: dict, nom: str, tf: str, debut: str,
          n_prior: int) -> dict:
    """Un menu sur un timeframe ; `n_prior` = registre + essais des autres blocs."""
    from packages.backtest.scenarios_horizons import grille_actif
    par_actif = {}
    for s, bars in series.items():
        ppy = PAR_AN_TF.get(tf) or (365.0 if classes.get(s) == "crypto" else 252.0)
        par_actif[s] = (grille_actif(bars, classes.get(s, "equity"), m, debut=debut,
                                     par_an=ppy), ppy)
    dsr, pbo = _surapprentissage(par_actif, n_prior)
    lignes = [li | {"actif": s} for s, (r, _) in par_actif.items() for li in r["lignes"]]
    H = [int(x) for x in m["horizons_annees"]]
    bh = [r["buy_and_hold"] for r, _ in par_actif.values()]
    top, vides = _top(lignes, dsr, H)
    return {"menu": nom, "timeframe": tf, "horizons": H, "n_scenarios": len(lignes),
            "top": top, "sans_trade": vides, "frequences": m["frequences"], "pbo": pbo,
            "buy_and_hold": {"sharpe": _med([b["sharpe"] for b in bh]),
                             "cagr": _med([b["cagr"] for b in bh]),
                             "max_drawdown": _med([b["max_drawdown"] for b in bh]),
                             **{f"rend_{h}a": _med([b["horizons"][h]["rend_annuel_median"]
                                                    for b in bh]) for h in H}}}


def executer_grille(univers: dict, classes: dict, *, debut: str, timeframes: list[str],
                    horizons: list[str], rebalance: list[str], n_prior: int,
                    menus: Path | str = MENUS) -> dict:
    from packages.research.explo_grille import empreinte
    g = charger_menus(menus)
    actifs = menus_actifs(g, horizons, rebalance)
    etapes = plan(actifs, timeframes, len(univers))
    total, blocs, series = sum(e[3] for e in etapes), [], {}
    for tf, nom, m, n in etapes:
        series[tf] = series.get(tf) or {s: reechantillonner(b, tf) for s, b in univers.items()}
        blocs.append(_bloc(series[tf], classes, m, nom, tf, debut, n_prior + total - n))
    return {"empreinte": empreinte(g), "nom": g["nom"], "blocs": blocs, "debut": debut,
            "non_testables": g.get("non_testables", {}), "actifs": list(univers)}


def _f(x, fmt: str) -> str:
    return "—" if not isinstance(x, (int, float)) or not math.isfinite(x) else fmt.format(x)


def _table_bloc(b: dict) -> list[str]:
    H = b["horizons"]
    tete = ("| Horizon | Configuration (stratégie · sortie · fréquence) | Sharpe | DSR méd. | "
            "MaxDD | Calmar | Win | PF | Turnover/an | "
            + " | ".join(f"Rend. {h} an(s) · bat B&H" for h in H) + " |")
    lignes = [tete, "|" + "---|" * (9 + len(H))]
    for t in b["top"]:
        cols = " | ".join(f"{_f(t[f'rend_{h}a'], '{:+.1%}')} · {_f(t[f'bat_bh_{h}a'], '{:.0%}')}"
                          for h in H)
        lignes.append(
            f"| {b['menu']} | `{t['id'].replace('|', ' · ')}` | {_f(t['sharpe'], '{:.2f}')} | "
            f"{_f(t['dsr_median'], '{:.2f}')} | {_f(t['max_drawdown'], '{:.1%}')} | "
            f"{_f(t['calmar'], '{:.2f}')} | {_f(t['win_rate'], '{:.0%}')} | "
            f"{_f(t['profit_factor'], '{:.2f}')} | {_f(t['turnover_annuel'], '{:.1f}')} | "
            f"{cols} |")
    bh = b["buy_and_hold"]
    lignes.append(f"| {b['menu']} | **buy & hold** | {_f(bh['sharpe'], '{:.2f}')} | — | "
                  f"{_f(bh['max_drawdown'], '{:.1%}')} | — | — | — | — | "
                  + " | ".join(f"{_f(bh[f'rend_{h}a'], '{:+.1%}')}" for h in H) + " |")
    return lignes


def rapport_markdown(res: dict, source: str) -> str:
    quand = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    out = ["# Résultats de simulation multi-horizons", "",
           f"> `python -m packages.backtest.grid_runner` · {quand} · source **{source}** · "
           f"grille `{res['nom']}` [{res['empreinte'][:12]}] · depuis {res['debut']} · "
           f"{len(res['actifs'])} actifs : {', '.join(res['actifs'])}", "",
           "Classement par Sharpe MÉDIAN entre actifs. DSR déflaté par tous les essais du "
           "programme (seuil de crédibilité 0,95). PBO > 0,5 : le classement est du bruit. "
           "« bat B&H » = part des fenêtres glissantes où la règle bat le buy & hold. Chaque "
           "colonne est une médiane INDÉPENDANTE entre actifs (un PF < 1 peut côtoyer un Sharpe "
           "positif) ; peu de trades par actif : win 100 % = 1 à 3 trades.", "",
           "## Demandé mais non testable aujourd'hui (UNCALIBRATED)", "",
           "| Élément | Raison |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in res["non_testables"].items()]
    for b in res["blocs"]:
        out += ["", f"## {b['menu'].capitalize()} terme — timeframe {b['timeframe']} "
                    f"({b['n_scenarios']} essais · fréquences {', '.join(b['frequences'])})",
                ""] + _table_bloc(b)
        if b["sans_trade"]:
            out += ["", f"{b['sans_trade']} configuration(s) sans aucun trade (indicateur "
                        "jamais défini sur cette barre) : exclues du classement."]
        out += ["", "PBO par actif : " + ", ".join(
            f"{s} {_f(p, '{:.2f}')}" for s, p in b["pbo"].items())]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--fmp", nargs="+", metavar="FICHIER")
    src.add_argument("--vps-crypto", choices=("1d",))
    ap.add_argument("--timeframes", nargs="+", default=["daily", "weekly", "monthly"])
    ap.add_argument("--horizons", nargs="+", default=list(HORIZONS))
    ap.add_argument("--rebalance", nargs="+", default=list(REBAL))
    ap.add_argument("--debut", default="2015-01-01")
    ap.add_argument("--aleatoire", type=int, default=12, help="0 = tous les titres éligibles")
    ap.add_argument("--graine", type=int, default=20260930)
    ap.add_argument("--export-report", default=str(ROOT / "docs" / "SIMULATION_RESULTS.md"))
    return _executer(ap.parse_args(argv))


def _executer(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT))
    from packages.backtest.comparaison_strategies import tirage
    from packages.research.ledger import append_record, deflation_params
    from scripts.comparer_strategies import _bars_fmp, _bars_vps, _eligibles
    a.vps_quotidien = not (a.fmp or a.vps_crypto)
    univers, classes = _bars_fmp(a.fmp) if a.fmp else _bars_vps(a)
    choix = _eligibles(univers, a.debut)
    choix = tirage(choix, a.aleatoire, a.graine) if a.aleatoire and not a.fmp else choix
    res = executer_grille({s: univers[s] for s in choix}, classes, debut=a.debut,
                          timeframes=a.timeframes, horizons=a.horizons,
                          rebalance=a.rebalance, n_prior=deflation_params()[0])
    source = "fmp" if a.fmp else ("vps-crypto" if a.vps_crypto else "vps-quotidien")
    md = rapport_markdown(res, source)
    Path(a.export_report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.export_report).write_text(md, encoding="utf-8")
    n = sum(b["n_scenarios"] for b in res["blocs"])
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"grid_runner:{res['empreinte'][:12]}:{source}:{a.graine}",
                   "statut": "mesure", "n_essais": n,
                   "params": {"actifs": choix, "timeframes": a.timeframes,
                              "horizons": a.horizons, "rebalance": a.rebalance},
                   "source": "packages/backtest/grid_runner.py (réel)"})
    print(md)
    print(f"→ {a.export_report} · {n} essais consignés au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
