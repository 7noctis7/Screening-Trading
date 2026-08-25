"""make alpha-lab — LE labo d'alpha : 5 hypothèses PRÉ-ENREGISTRÉES, passées au gate.

Différence avec `preset-lab` : celui-ci mesure des LEVIERS DE RISQUE sur le preset existant ;
alpha-lab teste des SIGNAUX candidats, en coupe transversale, chacun avec une paramétrisation
figée a priori (cf. `packages/research/alpha_hypotheses.PRE_REGISTERED`).

  H1 momentum 12-1       (Jegadeesh-Titman)        — CONTRÔLE de référence
  H2 momentum résiduel   (Blitz-Huij-Martens)      — loadings estimés HORS échantillon
  H3 basse vol idio.     (Ang et al.)
  H4 reversal 5 jours    (Lehmann ; Lo-MacKinlay)
  H5 proximité 52 sem.   (George-Hwang)

Chaque hypothèse passe les QUATRE étages : placebo (permutation du classement en coupe) →
DSR déflaté par le ledger → PBO/CSCV → sabotage. Un candidat n'est PROMU que si les quatre
passent. Tous les essais sont logués : la déflation du DSR augmente à chaque run, ce qui rend
le p-hacking arithmétiquement coûteux.

  export QUANT_PRICE_DB=/chemin/YAHOO.db      # données RÉELLES obligatoires
  make alpha-lab

⚠️ Ce que ce labo NE corrige PAS : l'univers est celui d'aujourd'hui (biais du survivant, cf.
finding F9) et les prix sont rétro-ajustés (finding F1). Un résultat positif ici est un
CANDIDAT à re-tester après la vague 1, jamais une conclusion.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

N_PLACEBO = 60          # permutations du classement transversal
MIN_NAMES = 30          # sous ce seuil, aucune coupe transversale n'a de sens
MIN_DOLLAR_VOL = 2e6    # liquidité minimale : sous ce seuil, les coûts modélisés sont faux
MIN_DAYS = 1300         # ~5 ans : en deçà, aucun IC n'est mesurable
MAX_NAMES = 600         # plafond mémoire/temps


def _wide_panel() -> "tuple":
    """Panel LARGE lu directement dans la base de prix — le souffle est la matière première.

    `IR = IC·√BR` : avec 30 noms, aucun IR mesurable n'est atteignable quel que soit le
    signal. On charge donc TOUT ce que la base contient, filtré sur deux critères qui ne
    sont pas des préférences mais des conditions de validité :
      - historique suffisant (sinon l'IC n'est pas mesurable) ;
      - liquidité suffisante (sinon le coût modélisé est une fiction).
    """
    import os

    import numpy as np

    from packages.data.engine import read_prices_rows
    db = os.environ.get("QUANT_PRICE_DB")
    if not db:
        from apps.api.snapshot import _price_db_path
        p = _price_db_path()
        db = str(p) if p else None
    if not db:
        return None, [], "aucune base de prix trouvée (QUANT_PRICE_DB)"
    rows = read_prices_rows(db)
    if not rows:
        return None, [], f"base illisible ou vide : {db}"
    par_sym: dict[str, list] = {}
    for r in rows:
        c, ts = r.get("close"), r.get("ts")
        if c and c > 0 and ts:
            par_sym.setdefault(r["symbol"], []).append((str(ts)[:10], float(c),
                                                        float(r.get("volume") or 0.0)))
    retenus = {}
    for sym, obs in par_sym.items():
        if len(obs) < MIN_DAYS:
            continue
        obs.sort()
        dv = np.median([c * v for _, c, v in obs[-252:]])
        if dv < MIN_DOLLAR_VOL:
            continue
        retenus[sym] = (obs, dv)
    if len(retenus) < MIN_NAMES:
        return None, [], (f"{len(retenus)} titres passent les filtres "
                          f"(≥ {MIN_DAYS} j et ≥ {MIN_DOLLAR_VOL/1e6:.0f} M$/j)")
    # grille de dates = celles présentes chez au moins 80 % des titres retenus
    from collections import Counter
    cnt = Counter(d for obs, _ in retenus.values() for d, _, _ in obs)
    seuil = 0.8 * len(retenus)
    grille = sorted(d for d, k in cnt.items() if k >= seuil)
    if len(grille) < MIN_DAYS:
        return None, [], f"seulement {len(grille)} dates communes (≥ {MIN_DAYS} requis)"
    idx = {d: i for i, d in enumerate(grille)}
    ordre = sorted(retenus, key=lambda s: -retenus[s][1])[:MAX_NAMES]   # les plus liquides
    lignes, syms = [], []
    for sym in ordre:
        serie = np.full(len(grille), np.nan)
        for d, c, _ in retenus[sym][0]:
            if d in idx:
                serie[idx[d]] = c
        if np.isfinite(serie).all():
            lignes.append(serie)
            syms.append(sym)
    if len(syms) < MIN_NAMES:
        return None, [], f"{len(syms)} titres complets sur la grille commune"
    return np.asarray(lignes), syms, ""


def _panel(data: dict) -> "tuple":
    """dict{symbole: barres} → matrice n × L alignée sur l'historique commun."""
    import numpy as np
    from packages.backtest.panel import fenetre_commune
    syms = [s for s, b in data.items() if b and len(b) > 600]
    if len(syms) < MIN_NAMES:
        return None, []
    syms, L, _ = fenetre_commune(data, syms)     # jamais `min` : cf. packages/backtest/panel
    A = np.asarray([[b.close for b in data[s]][-L:] for s in syms], dtype=float)
    ok = np.isfinite(A).all(axis=1) & (A > 0).all(axis=1)
    return A[ok], [s for s, k in zip(syms, ok) if k]


def _gate(name: str, A, long_only: bool, cost_bps: float, bench=None) -> dict | None:
    """Backtest + les quatre étages du gate. Renvoie une ligne de résultat, ou None."""
    import numpy as np

    from packages.portfolio.pbo import pbo_cscv
    from packages.portfolio.psr import deflated_sharpe_ratio
    from packages.research.adversarial import sabotage_verdict
    from packages.research.alpha_hypotheses import cross_sectional_backtest
    from packages.research.gate import promotion_verdict

    r = cross_sectional_backtest(A, name, long_only=long_only, cost_rt_bps=cost_bps)
    if not r.get("available"):
        return None
    ret = r["returns"]
    # 1. PLACEBO : on permute le CLASSEMENT en coupe → structure et coûts conservés,
    #    information détruite. Le seul placebo qui teste le signal et non l'univers.
    sims = []
    for s in range(N_PLACEBO):
        p = cross_sectional_backtest(A, name, long_only=long_only, cost_rt_bps=cost_bps,
                                     shuffle_seed=1000 + s)
        if p.get("available"):
            sims.append(p["sharpe"])
    placebo_p = (round(float((np.abs(np.asarray(sims)) >= abs(r["sharpe"])).mean()), 4)
                 if len(sims) >= 20 else None)
    # 2. DSR déflaté par le programme de recherche COMPLET (ledger), pas la grille locale
    try:
        from packages.research.ledger import deflation_params
        n_trials, sr_std = deflation_params(min_trials=10)
    except Exception:  # noqa: BLE001
        n_trials, sr_std = 10, None
    # PSR/DSR exigent le Sharpe et le seuil dans la MÊME périodicité : on passe donc le
    # Sharpe PAR PÉRIODE (le Sharpe annualisé n'est qu'un affichage).
    sd = float(ret.std(ddof=1))
    sr_period = float(ret.mean() / sd) if sd > 0 else 0.0
    dsr = deflated_sharpe_ratio(sr_period, ret.size, n_trials=n_trials, sr_std=sr_std)
    sab = sabotage_verdict(ret, turnover=r["turnover_annual"] / (252.0 / r["step"]))
    v = promotion_verdict(dsr=dsr, placebo_p=placebo_p, edge=float(ret.mean()))
    v["checks"]["sabotage"] = bool(sab.get("survives"))
    # BÊTA OU ALPHA ? Un long-only sur une période haussière monte parce que le marché monte.
    # Sans cette comparaison, « Sharpe 1,70 » ne dit pas si le signal apporte quoi que ce soit.
    att = {"available": False}
    if bench is not None and bench.get("available"):
        from packages.research.attribution import attribution, bat_le_benchmark
        att = attribution(ret, bench["returns"], 252.0 / r["step"])
        if long_only:      # sur un long/short le bêta est déjà neutralisé par construction
            v["checks"]["bat_benchmark"] = bat_le_benchmark(att)
            if not v["checks"]["bat_benchmark"]:
                v["reasons"].append(
                    f"ne bat pas l'univers équipondéré (alpha {att.get('alpha_annuel', 0)*100:+.1f} %/an, "
                    f"IR excès {att.get('ir_exces', 0):+.2f})")
    return {"nom": name, "long_only": long_only, "sharpe": r["sharpe"], "attribution": att,
            "sharpe_period": round(sr_period, 4),
            "periods_per_year": round(252.0 / r["step"], 4),
            "cagr": r["annualized"], "maxdd": r["max_drawdown"],
            "turnover": r["turnover_annual"], "n_steps": r["n_steps"],
            "dsr": dsr, "placebo_p": placebo_p, "sabotage": bool(sab.get("survives")),
            "returns": ret, "checks": v["checks"], "reasons": v["reasons"]}


def _pbo(rows: list[dict]) -> float | None:
    """PBO/CSCV sur la matrice des configurations testées (colonnes = hypothèses)."""
    import numpy as np

    from packages.portfolio.pbo import pbo_cscv
    if len(rows) < 4:
        return None
    m = min(r["returns"].size for r in rows)
    mat = np.column_stack([r["returns"][-m:] for r in rows])
    return pbo_cscv(mat).get("pbo")


def _print(rows: list[dict], pbo: float | None, n: int, L: int) -> list[dict]:
    print(f"\nUnivers : {n} titres × {L} jours · rebalancement mensuel · exécution t+1")
    print(f"\n  {'Hypothèse':24s} {'sens':11s} {'Sharpe':>7s} {'CAGR':>7s} {'maxDD':>7s} "
          f"{'turn':>6s} {'DSR':>6s} {'placebo':>8s} {'sabot.':>7s} {'bêta':>6s} "
          f"{'alpha':>7s} {'IRexc':>6s}")
    for r in rows:
        pp = f"{r['placebo_p']:.3f}" if r["placebo_p"] is not None else "  n/a"
        a = r.get("attribution") or {}
        bt = f"{a['beta']:6.2f}" if a.get("available") else "     —"
        al = f"{a['alpha_annuel']*100:+6.1f}%" if a.get("available") else "      —"
        ir = f"{a['ir_exces']:+6.2f}" if a.get("available") else "     —"
        print(f"  {r['nom']:24s} {'long-only' if r['long_only'] else 'long/short':11s} "
              f"{r['sharpe']:7.2f} {r['cagr']*100:6.1f}% {r['maxdd']*100:6.1f}% "
              f"{r['turnover']:5.1f}× {r['dsr']*100:5.0f}% {pp:>8s} "
              f"{'oui' if r['sabotage'] else 'non':>7s} {bt} {al} {ir}")
    print(f"\nPBO (CSCV sur les {len(rows)} configurations) : {pbo:.2f}"
          if pbo is not None else "\nPBO : non calculable")
    promus = []
    print("\nVERDICT (promu = placebo ET DSR ET sabotage ET edge net > 0) :")
    for r in rows:
        ok = bool(r["checks"]) and all(r["checks"].values()) and (pbo is None or pbo < 0.5)
        print(f"  {'✅ CANDIDAT' if ok else '❌ rejeté  '} {r['nom']:24s} "
              f"{'long-only' if r['long_only'] else 'long/short':11s}"
              + ("" if ok else f"  — {', '.join(r['reasons'][:2]) or 'PBO trop élevé'}"))
        if ok:
            promus.append(r)
    if not promus:
        print("\n→ Aucun candidat ne passe. C'est un RÉSULTAT : à publier sur /echecs.")
        print("  Rappel d'ordre de grandeur : sur ~6 ans de rebalancements mensuels,")
        print("  l'écart-type d'un Sharpe annuel est ≈ 0,4 — sous 0,8 rien n'est")
        print("  distinguable de zéro, quel que soit le graphique.")
    else:
        print("\n→ Re-runner une 2e fois sur une période disjointe AVANT toute activation.")
    return promus


def _combinaison(A, cost: float) -> dict | None:
    """Le livre COMBINÉ : IC par signal, décorrélation, plafond d'IR, puis gate."""
    import numpy as np

    from packages.portfolio.psr import deflated_sharpe_ratio
    from packages.research.adversarial import sabotage_verdict
    from packages.research.alpha_combine import (breadth_report, combined_backtest,
                                                 measure_ics, signal_correlation)
    from packages.research.alpha_hypotheses import SIGNALS
    from packages.research.gate import promotion_verdict

    names = list(SIGNALS)
    ics = measure_ics(A, names)
    if not ics.get("available"):
        print("\n(combinaison impossible : IC non mesurables sur cet historique)")
        return None
    print("\n" + "=" * 60 + "\nIC RÉALISÉS PAR SIGNAL (le thermomètre)\n" + "=" * 60)
    print(f"  {'Signal':24s} {'IC moyen':>9s} {'t-stat':>7s} {'hit':>6s} {'n dates':>8s}")
    for k in names:
        v = ics["par_signal"].get(k)
        if v:
            print(f"  {k:24s} {v['ic_mean']:+9.4f} {v['t_stat']:+7.2f} "
                  f"{v['hit_rate']:6.2f} {v['n']:8d}")
    O = signal_correlation(A, names)
    off = O[~np.eye(len(names), dtype=bool)]
    print(f"\n  Corrélation moyenne entre signaux : {float(off.mean()):+.3f} "
          f"(min {float(off.min()):+.3f}, max {float(off.max()):+.3f})")
    print("  → c'est la DÉCORRÉLATION qui crée la valeur de la combinaison, pas la force.")
    br = breadth_report(A, names, ics)
    print(f"\n  IC combiné {br['ic_combine']:.4f} vs meilleur seul {br['ic_meilleur_seul']:.4f}"
          f"  ·  IR plafond (TC=1) {br['ir_theorique_TC1']}"
          f"  ·  IR réaliste (TC=0,5) {br['ir_realiste_TC05']}")
    print(f"  IC requis pour un IR de 1 avec TC=0,5 : {br['ic_requis_pour_IR1']:.4f}")

    print("\n" + "=" * 60 + "\nLIVRE COMBINÉ (pondération ré-estimée en fenêtre expansive)\n"
          + "=" * 60)
    out = []
    for lo in (False, True):
        c = combined_backtest(A, names, long_only=lo, cost_rt_bps=cost)
        if not c.get("available"):
            continue
        ret = c["returns"]
        sd = float(ret.std(ddof=1))
        sr_period = float(ret.mean() / sd) if sd > 0 else 0.0
        try:
            from packages.research.ledger import deflation_params
            n_trials, sr_std = deflation_params(min_trials=10)
        except Exception:  # noqa: BLE001
            n_trials, sr_std = 10, None
        dsr = deflated_sharpe_ratio(sr_period, ret.size, n_trials=n_trials, sr_std=sr_std)
        sab = sabotage_verdict(ret, turnover=c["turnover_annual"] / (252.0 / c["step"]))
        v = promotion_verdict(dsr=dsr, edge=float(ret.mean()))
        v["checks"]["sabotage"] = bool(sab.get("survives"))
        ok = bool(v["checks"]) and all(v["checks"].values())
        print(f"  {'long-only' if lo else 'long/short':11s} Sharpe {c['sharpe']:6.2f} "
              f"CAGR {c['annualized']*100:6.1f}% maxDD {c['max_drawdown']*100:6.1f}% "
              f"turn {c['turnover_annual']:4.1f}× DSR {dsr*100:3.0f}% "
              f"sabot. {'oui' if sab.get('survives') else 'non'}  "
              f"{'✅ CANDIDAT' if ok else '❌ rejeté'}")
        print(f"              poids des signaux : {c['poids_finaux']}")
        out.append({"long_only": lo, "res": c, "dsr": dsr, "ok": ok})
    return {"ics": ics, "breadth": br, "livres": out}


def _log(rows: list[dict], promus: list[dict], pbo: float | None) -> None:
    try:
        from datetime import UTC, datetime

        from packages.research.ledger import append_record, trial_count
        for r in rows:
            append_record({"date": datetime.now(UTC).date().isoformat(),
                           "facteur": f"alpha_lab_{r['nom']}"
                                      f"{'_LO' if r['long_only'] else ''}",
                           "classe": ["equity"], "horizon": "mensuel",
                           "dsr": r["dsr"], "sharpe": r["sharpe"],
                           "sharpe_period": r["sharpe_period"],
                           "periods_per_year": r["periods_per_year"],
                           "maxdd": r["maxdd"],
                           "pbo": pbo, "placebo_p": r["placebo_p"],
                           "statut": "en_test" if r in promus else "rejete",
                           "these": "Hypothèse pré-enregistrée (alpha-lab)."})
        print(f"\n📒 {len(rows)} essais logués (ledger N={trial_count()}) — "
              f"la déflation du DSR augmente d'autant au prochain run.")
    except Exception as e:  # noqa: BLE001
        print(f"(ledger non mis à jour : {e})")


def main() -> int:
    from packages.execution.costs import CostModel
    from scripts.preset_lab import _load_real_data
    from packages.research.alpha_hypotheses import SIGNALS

    print("Chargement de l'univers LARGE depuis la base de prix…")
    A, syms, err = _wide_panel()
    if A is None:
        print(f"  (univers large indisponible : {err}) — repli sur l'univers curé.")
        data, _acmap = _load_real_data()
        if data is None:
            return 1
        A, syms = _panel(data)
    if A is None or A.shape[0] < MIN_NAMES:
        print(f"⛔ Univers insuffisant ({0 if A is None else A.shape[0]} titres, "
              f"{MIN_NAMES} requis) : aucune coupe transversale possible.")
        return 1
    print(f"  Univers retenu : {A.shape[0]} titres × {A.shape[1]} jours")
    cost = CostModel.for_asset_class("equity").round_trip_bps
    print(f"Coût aller-retour appliqué : {cost:.1f} bps (barème {['equity']})")
    # BENCHMARK : détenir l'univers, équipondéré, même grille et mêmes coûts. Sans lui, un
    # Sharpe long-only de 1,70 sur une période haussière se lit comme de l'alpha.
    from packages.research.alpha_hypotheses import benchmark_equipondere
    bench = benchmark_equipondere(A, cost_rt_bps=cost)
    if bench.get("available"):
        print(f"Benchmark (univers équipondéré, buy & hold) : Sharpe {bench['sharpe']:.2f} · "
              f"CAGR {bench['annualized']*100:.1f}% · maxDD {bench['max_drawdown']*100:.1f}%")
    rows = []
    for name in SIGNALS:
        for lo in (False, True):
            r = _gate(name, A, lo, cost, bench=bench)
            if r:
                rows.append(r)
    if not rows:
        print("Aucune hypothèse mesurable sur cet historique.")
        return 1
    pbo = _pbo(rows)
    promus = _print(rows, pbo, A.shape[0], A.shape[1])
    try:
        _combinaison(A, cost)
    except Exception as e:  # noqa: BLE001 — la combinaison ne doit pas casser le labo
        print(f"\n(combinaison non calculée : {str(e)[:120]})")
    _log(rows, promus, pbo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
