"""make preset-lab — le LABO Sharpe/Sortino : chaque levier candidat mesuré puis GATÉ.

Leviers testés (paramètres fixés A PRIORI — aucune grille, donc pas de sélection in-sample) :
  1. base                  : preset de prod actuel (référence) ;
  2. +cap adaptatif        : plafond 10 % resserré ×0,5 si corr moyenne > 0,60 (corr_tighten) ;
  3. +overlay risque       : taper drawdown + frein vol EWMA (risk_overlay, déjà codé, jamais gaté) ;
  4. +les deux ;
  5. fill t+1              : exécution au close t+1 (chiffre le mini look-ahead) ;
  6. +covariance débruitée : Marcenko-Pastur + repli inverse-vol si moins de 2 directions
                             exploitables (M1). Le DIAGNOSTIC est imprimé même sans le levier.

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

# Quel compteur de déclenchement prouve qu'un levier a réellement AGI ? Sans ça, « rejeté »
# et « jamais activé » s'impriment à l'identique — c'est ce qui s'est passé le 24/08.
DECLENCHEURS = {
    "+cap adaptatif corr": ("plafond",),
    "+overlay DD/vol EWMA": ("taper_dd", "frein_vol"),
    "+cap adaptatif + overlay": ("plafond", "taper_dd", "frein_vol"),
}

# Lignes DIAGNOSTIQUES : imprimées pour chiffrer un défaut connu, jamais promues, jamais loguées
# au ledger (ce ne sont pas des essais d'alpha — les compter déflaterait le DSR pour rien).
DIAGNOSTICS = {"panel tronqué (ancien min)"}

CONFIGS = [
    ("base (prod actuelle)", {}),
    ("panel tronqué (ancien min)", {"panel_couverture": 1.0}),   # chiffre la troncature du panel
    ("+cap adaptatif corr", {"max_weight": 0.10, "corr_tighten": True}),
    ("+overlay DD/vol EWMA", {"risk_overlay": True}),
    ("+cap adaptatif + overlay", {"max_weight": 0.10, "corr_tighten": True,
                                  "risk_overlay": True}),
    ("fill t+1 (réaliste, M-1)", {"exec_lag": 1}),   # écart vs fill au signal = mini look-ahead
    ("+covariance débruitée RMT", {"cov_denoise": True}),   # M1 : repli inverse-vol si k < 2
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
                     "periods_per_year": round(per_year, 4),
                     "sortino": _sortino(r["curves"]["preset"], per_year),
                     "maxdd": st["max_drawdown"], "turnover": r["turnover_annual"],
                     "cov_diag": r.get("cov_diag"), "panel": r.get("panel"),
                     "n_steps": r.get("n_steps"), "decl": r.get("declenchements") or {}})
    return rows


def _panel_report(rows: list[dict]) -> None:
    """Profondeur EFFECTIVE du backtest — à lire avant tout ratio.

    `min(len)` laissait la série la plus courte fixer la fenêtre de tout le panel. Un Sharpe
    annualisé sur 7 rebalancements n'a pas d'intervalle de confiance utilisable ; le publier
    sans ce compte, c'est publier un chiffre qu'on ne peut pas contredire."""
    d = (rows[0].get("panel") or {}) if rows else {}
    print("\n" + "=" * 60 + "\nPANEL — PROFONDEUR EFFECTIVE\n" + "=" * 60)
    if not d.get("available"):
        print("  Diagnostic indisponible."); return
    print(f"  fenêtre commune L     : {d['L']} barres "
          f"(série la plus courte : {d['L_min']} → ×{d['gain_vs_min']})")
    print(f"  noms retenus          : {d['n_retenus']}/{d['n_eligibles']} "
          f"({d['n_ecartes']} écartés : historique trop court, filtre d'ancienneté de cotation)")
    print(f"  rebalancements        : {rows[0].get('n_steps')}")
    if (rows[0].get("n_steps") or 0) < 20:
        print("  ⚠️  moins de 20 pas : AUCUN ratio ci-dessous n'est interprétable.")


def _decl_report(rows: list[dict]) -> None:
    """Chaque garde-fou a-t-il MORDU ? Un filtre qui n'a jamais filtré est inutile ou cassé."""
    d = (rows[0].get("decl") or {}) if rows else {}
    n = rows[0].get("n_steps") or 0
    if not d:
        return
    print("\n" + "=" * 60 + f"\nDÉCLENCHEMENTS (base, sur {n} pas)\n" + "=" * 60)
    for k, v in d.items():
        etat = ("ACTIF mais jamais déclenché ⚠️" if v == 0
                else f"{v}/{n} pas ({v / n:.0%})" if n else str(v))
        print(f"  {k:12s} : {etat}")
    print("  (un garde-fou absent de cette liste est DÉSACTIVÉ dans la config de base)")


def _cov_report(rows: list[dict]) -> None:
    """LA question de M1 : le preset optimise-t-il du signal ou du bruit ?

    Diagnostic OBSERVATIONNEL de la configuration de base — il ne change aucun chiffre.
    k = nombre de directions distinguables du bruit (Marcenko-Pastur + écart spectral) ;
    q = n/T. k < 2 signifie qu'aucune optimisation transversale n'est justifiée.
    """
    d = (rows[0].get("cov_diag") or {}) if rows else {}
    print("\n" + "=" * 60 + "\nCOVARIANCE — EXPLOITABILITÉ (M1, observationnel)\n" + "=" * 60)
    if not d.get("available"):
        print("  Diagnostic indisponible (échantillon trop court)."); return
    print(f"  q = n/T médian        : {d['q_median']}")
    print(f"  directions fiables k  : médiane {d['k_signal_median']:.0f} "
          f"(min {d['k_signal_min']}, max {d['k_signal_max']}) sur {d['n_steps']} rebalancements")
    print(f"  verdict               : {d['verdict']}")
    if d["k_signal_median"] < 2:
        print("  → l'ERC répartit un risque estimé sur du bruit. Le levier « covariance")
        print("    débruitée RMT » replie alors sur l'inverse-vol : comparer sa ligne ci-dessus.")


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
        if r["label"] in DIAGNOSTICS:
            print(f"  🔎 diagnostic {r['label']}  (ΔSharpe {r['sharpe']-base['sharpe']:+.2f} — "
                  f"{r.get('n_steps')} pas contre {base.get('n_steps')})")
            continue
        ok = r["sharpe"] >= base["sharpe"] + 0.05 and r["maxdd"] >= base["maxdd"] - 1e-9
        cles = DECLENCHEURS.get(r["label"], ())
        tirs = sum(int((r.get("decl") or {}).get(k, 0)) for k in cles)
        inerte = bool(cles) and tirs == 0
        tag = "⚪ INERTE  " if inerte else ("✅ CANDIDAT" if ok else "❌ rejeté  ")
        print(f"  {tag} {r['label']}"
              f"  (ΔSharpe {r['sharpe']-base['sharpe']:+.2f}, ΔmaxDD "
              f"{(r['maxdd']-base['maxdd'])*100:+.1f} pts"
              + (", jamais déclenché — non testé, pas rejeté)" if inerte
                 else f", {tirs} déclenchements)" if cles else ")"))
        if ok and not inerte:
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
            if r["label"] in DIAGNOSTICS:
                continue
            append_record({"date": datetime.now(UTC).date().isoformat(),
                           "facteur": f"preset_lab_{'_'.join(sorted(r['kw']))}",
                           "classe": ["equity", "etf", "crypto"], "horizon": "swing",
                           "dsr": r["dsr"], "sharpe": r["sharpe"], "maxdd": r["maxdd"],
                           "periods_per_year": r.get("periods_per_year"),
                           "params": r["kw"],
                           "statut": "en_test" if r in promoted else "rejete",
                           "these": "Levier risque preset (labo Sharpe/Sortino)."})
        print(f"📒 Essais logués (ledger N={trial_count()}).")
    except Exception as e:  # noqa: BLE001
        print(f"(ledger non mis à jour : {e})")


def _survivorship(data, acmap) -> None:
    """XL-1 : delta de biais du survivant si des prix de délistés sont EN BASE (sinon skip honnête)."""
    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.backtest.survivorship_delta import survivorship_delta
    from packages.data.survivorship import load_delisted
    dl = load_delisted()
    if not dl:
        return
    instr = [{"symbol": d["symbol"], "sector": d.get("sector", ""), "asset_class": "equity"} for d in dl]
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    dd_data, _mode, real = _load_prices(instr, {i["symbol"]: _sector_of(i) for i in instr},
                                        end - timedelta(days=_HISTORY_DAYS), end, 7)
    dd_real = {s: b for s, b in dd_data.items() if s in real}     # prix RÉELS uniquement
    print("\n" + "=" * 60 + "\nBIAIS DU SURVIVANT (XL-1)\n" + "=" * 60)
    out = survivorship_delta(data, delisted_data=dd_real, top_k=30)
    if not out.get("available"):
        print(f"  Indisponible : {out.get('reason')}")
        return
    d = out["delta"]
    print(f"  {out['n_delisted']} délistés réels ajoutés · Δ Sharpe {d['sharpe']:+.2f} · "
          f"Δ CAGR {d['annualized']*100:+.1f} pts · Δ maxDD {d['max_drawdown']*100:+.1f} pts")
    if abs(d["sharpe"]) < 1e-9 and abs(d["annualized"]) < 1e-9:
        print("  → Δ nul : les délistés ne sont JAMAIS entrés dans le top-30 — le test ne mesure")
        print("    donc rien. Il faut des délistés qui auraient été SÉLECTIONNÉS pour conclure.")
    elif d["sharpe"] < 0:
        print("  → Δ Sharpe négatif : le backtest survivant était bien optimiste. À publier sur /echecs.")
    else:
        print("  → Δ Sharpe positif : les délistés AIDAIENT le portefeuille sur la période —")
        print("    contre-intuitif, à instruire avant d'en tirer quoi que ce soit.")


def main() -> int:
    data, acmap = _load_real_data()
    if data is None:
        return 1
    rows = _run_configs(data, acmap)
    if not rows:
        print("Rien à comparer."); return 1
    _panel_report(rows)
    _decl_report(rows)
    _cov_report(rows)
    promoted = _verdict(rows)
    _log_ledger(rows, promoted)
    try:
        _survivorship(data, acmap)
    except Exception as e:  # noqa: BLE001 — mesure best-effort, ne casse pas le labo
        print(f"\n(survivorship non calculé : {str(e)[:80]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
