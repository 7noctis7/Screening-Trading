"""make preset-lab — le LABO Sharpe/Sortino : chaque levier candidat mesuré puis GATÉ.

Leviers testés (paramètres fixés A PRIORI — aucune grille, donc pas de sélection in-sample) :
  1. base                  : preset de prod actuel (référence) ;
  2. +cap adaptatif        : plafond 10 % resserré ×0,5 si corr moyenne > 0,60 (corr_tighten) ;
  3. +overlay risque       : taper drawdown + frein vol EWMA (risk_overlay, déjà codé, jamais gaté) ;
  4. +les deux.

VERDICT honnête : un levier n'est PROMU que si son Sharpe déflaté (DSR, N du ledger) et son
maxDD s'améliorent — sinon il reste « rejeté » et se publie sur /echecs comme les autres.
Chaque run s'ajoute au ledger (déflation N croissante = anti p-hacking).

  export QUANT_PRICE_DB=/chemin/YAHOO.db     # données RÉELLES obligatoires
  make preset-lab
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIGS = [
    ("base (prod actuelle)", {}),
    ("+cap adaptatif corr", {"max_weight": 0.10, "corr_tighten": True}),
    ("+overlay DD/vol EWMA", {"risk_overlay": True}),
    ("+cap adaptatif + overlay", {"max_weight": 0.10, "corr_tighten": True,
                                  "risk_overlay": True}),
]


def _sortino(curve: list[float], per_year: float) -> float:
    import numpy as np
    e = np.asarray(curve, float)
    r = e[1:] / e[:-1] - 1
    dn = r[r < 0]
    sd = float(dn.std()) if dn.size else 0.0
    return round(float(r.mean() / sd * (per_year ** 0.5)), 2) if sd > 0 else 0.0


def _load_real_data():
    """(data, acmap) RÉELS ou None (synthétique interdit — mandat données-réelles)."""
    import os

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe,
                                   _sector_of, datetime, timedelta, timezone)
    instruments = _seed_universe()
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    acmap = {m["symbol"]: m.get("asset_class", "equity") for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    print("Chargement des prix…")
    data, mode, _ = _load_prices(instruments, sector_of,
                                 end - timedelta(days=_HISTORY_DAYS), end, 7)
    print(f"Mode : {mode} · univers {len(data)}")
    if mode.startswith("synthetic") and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print("\n⛔ DONNÉES SYNTHÉTIQUES — labo UNCALIBRATED, aucun verdict possible.")
        print("   export QUANT_PRICE_DB=/chemin/YAHOO.db puis relance make preset-lab.")
        return None, None
    return data, acmap


def _run_configs(data, acmap) -> list[dict]:
    from packages.backtest.preset_backtest import preset_backtest
    rows = []
    for label, kw in CONFIGS:
        r = preset_backtest(data, asset_classes=acmap, **kw)
        if not r.get("available"):
            print(f"  {label:28s} indisponible (échantillon insuffisant)"); continue
        st, per_year = r["preset"], 252.0 / r["step_days"]
        rows.append({"label": label, "kw": kw, "cagr": st["annualized"],
                     "sharpe": st["sharpe"], "dsr": st["dsr"],
                     "sortino": _sortino(r["curves"]["preset"], per_year),
                     "maxdd": st["max_drawdown"], "turnover": r["turnover_annual"]})
    return rows


def _verdict(rows: list[dict]) -> list[dict]:
    """Gate honnête : promu seulement si mieux sur Sharpe ET maxDD. Sinon rejeté (→ /echecs)."""
    base, promoted = rows[0], []
    print(f"\n  {'Config':28s} {'CAGR':>7s} {'Sharpe':>7s} {'Sortino':>8s} "
          f"{'DSR':>6s} {'maxDD':>7s} {'turn.':>6s}")
    for r in rows:
        print(f"  {r['label']:28s} {r['cagr']*100:6.1f}% {r['sharpe']:7.2f} "
              f"{r['sortino']:8.2f} {r['dsr']*100:5.0f}% {r['maxdd']*100:6.1f}% "
              f"{r['turnover']:5.2f}×")
    print("\nVERDICT (gate honnête — mieux sur Sharpe ET maxDD, sinon rejeté) :")
    for r in rows[1:]:
        ok = r["sharpe"] >= base["sharpe"] + 0.05 and r["maxdd"] >= base["maxdd"] - 1e-9
        print(f"  {'✅ CANDIDAT' if ok else '❌ rejeté  '} {r['label']}"
              f"  (ΔSharpe {r['sharpe']-base['sharpe']:+.2f}, ΔmaxDD "
              f"{(r['maxdd']-base['maxdd'])*100:+.1f} pts)")
        if ok:
            promoted.append(r)
    print("\n→ " + ("Activer le(s) flag(s) en prod via une PR avec CES chiffres, puis make "
                    "vault-sync (jamais d'activation silencieuse)." if promoted else
                    "Aucun levier ne bat la base : on ne touche à rien (résultat à publier "
                    "sur /echecs si confirmé une 2e fois)."))
    return promoted


def _log_ledger(rows: list[dict], promoted: list[dict]) -> None:
    """Trace anti p-hacking : chaque essai compte dans N (déflation du DSR)."""
    try:
        from datetime import UTC, datetime
        from packages.research.ledger import append_record, trial_count
        for r in rows[1:]:
            append_record({"date": datetime.now(UTC).date().isoformat(),
                           "facteur": f"preset_lab_{'_'.join(sorted(r['kw']))}",
                           "classe": ["equity", "etf", "crypto"], "horizon": "swing",
                           "dsr": r["dsr"], "sharpe": r["sharpe"], "maxdd": r["maxdd"],
                           "params": r["kw"],
                           "statut": "en_test" if r in promoted else "rejete",
                           "these": "Levier risque preset (labo Sharpe/Sortino)."})
        print(f"📒 Essais logués (ledger N={trial_count()}).")
    except Exception as e:  # noqa: BLE001
        print(f"(ledger non mis à jour : {e})")


def main() -> int:
    data, acmap = _load_real_data()
    if data is None:
        return 1
    rows = _run_configs(data, acmap)
    if not rows:
        print("Rien à comparer."); return 1
    promoted = _verdict(rows)
    _log_ledger(rows, promoted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
