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


def _panel(data: dict) -> "tuple":
    """dict{symbole: barres} → matrice n × L alignée sur l'historique commun."""
    import numpy as np
    syms = [s for s, b in data.items() if b and len(b) > 600]
    if len(syms) < MIN_NAMES:
        return None, []
    L = min(len(data[s]) for s in syms)
    A = np.asarray([[b.close for b in data[s]][-L:] for s in syms], dtype=float)
    ok = np.isfinite(A).all(axis=1) & (A > 0).all(axis=1)
    return A[ok], [s for s, k in zip(syms, ok) if k]


def _gate(name: str, A, long_only: bool, cost_bps: float) -> dict | None:
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
    dsr = deflated_sharpe_ratio(r["sharpe"], ret.size, n_trials=n_trials, sr_std=sr_std)
    sab = sabotage_verdict(ret, turnover=r["turnover_annual"] / (252.0 / r["step"]))
    v = promotion_verdict(dsr=dsr, placebo_p=placebo_p, edge=float(ret.mean()))
    v["checks"]["sabotage"] = bool(sab.get("survives"))
    return {"nom": name, "long_only": long_only, "sharpe": r["sharpe"],
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
          f"{'turn':>6s} {'DSR':>6s} {'placebo':>8s} {'sabot.':>7s}")
    for r in rows:
        pp = f"{r['placebo_p']:.3f}" if r["placebo_p"] is not None else "  n/a"
        print(f"  {r['nom']:24s} {'long-only' if r['long_only'] else 'long/short':11s} "
              f"{r['sharpe']:7.2f} {r['cagr']*100:6.1f}% {r['maxdd']*100:6.1f}% "
              f"{r['turnover']:5.1f}× {r['dsr']*100:5.0f}% {pp:>8s} "
              f"{'oui' if r['sabotage'] else 'non':>7s}")
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


def _log(rows: list[dict], promus: list[dict], pbo: float | None) -> None:
    try:
        from datetime import UTC, datetime

        from packages.research.ledger import append_record, trial_count
        for r in rows:
            append_record({"date": datetime.now(UTC).date().isoformat(),
                           "facteur": f"alpha_lab_{r['nom']}"
                                      f"{'_LO' if r['long_only'] else ''}",
                           "classe": ["equity"], "horizon": "mensuel",
                           "dsr": r["dsr"], "sharpe": r["sharpe"], "maxdd": r["maxdd"],
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

    data, _acmap = _load_real_data()
    if data is None:
        return 1
    A, syms = _panel(data)
    if A is None or A.shape[0] < MIN_NAMES:
        print(f"⛔ Univers insuffisant ({0 if A is None else A.shape[0]} titres, "
              f"{MIN_NAMES} requis) : aucune coupe transversale possible.")
        return 1
    cost = CostModel.for_asset_class("equity").round_trip_bps
    print(f"Coût aller-retour appliqué : {cost:.1f} bps (barème {['equity']})")
    rows = []
    for name in SIGNALS:
        for lo in (False, True):
            r = _gate(name, A, lo, cost)
            if r:
                rows.append(r)
    if not rows:
        print("Aucune hypothèse mesurable sur cet historique.")
        return 1
    pbo = _pbo(rows)
    promus = _print(rows, pbo, A.shape[0], A.shape[1])
    _log(rows, promus, pbo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
