"""make preset-sorties — stops et prise partielle améliorent-ils le portefeuille qui TRADE ?

Mêmes décisions de production (`preset_latest_weights_explique`, rejouées date par date),
simulées SANS puis AVEC sorties : l'écart ne peut venir que des sorties
(`backtest/rejeu_sorties.py`). Trois modes PRÉ-ENREGISTRÉS, réglages conventionnels
jamais retouchés après lecture — chacun est un essai consigné au registre :

    atr              Chandelier : plus haut de clôture − 3 ATR(14)
    structure        stop sous le dernier creux confirmé suivi d'un sommet, tampon 0,5 ATR
    structure_prise  idem + un tiers vendu à la liquidité opposée (≥ 2 R)

RÈGLE DE DÉCISION ÉCRITE AVANT LA MESURE (ADR-0208) : un mode n'est ADOPTABLE que si
(1) ΔSharpe apparié avec − sans ≥ 0 en estimation ponctuelle ET (2) le maxDD s'améliore
d'au moins 3 points. Sinon : REJETÉ. Adoptable ne veut pas dire adopté : la production
ne change que sur décision explicite. Précédent : ADR-0052 (suiveur retiré du swing).

    export QUANT_PRICE_DB=/chemin/YAHOO.db     # données RÉELLES obligatoires
    make preset-sorties                         # les trois modes, pas de 5 jours
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

SORTIE = ROOT / "out" / "preset_sorties.json"
MODES = {"atr": ("atr", False), "structure": ("structure", False),
         "structure_prise": ("structure", True)}
SEUIL_DD = 0.03


def verdict(res: dict) -> str:
    """Applique la règle pré-enregistrée. Aucun autre critère n'est admis a posteriori."""
    d = res.get("delta") or {}
    if not d.get("disponible"):
        return "INDÉTERMINÉ (ΔSharpe non calculable)"
    gain_dd = res["avec"]["stats"]["max_drawdown"] - res["sans"]["stats"]["max_drawdown"]
    # Tolérance à l'erreur flottante : −0,27 − (−0,30) vaut 0,0299… en binaire, et
    # « au moins 3 points » rejetait exactement 3 points (piège noté dans CLAUDE.md).
    if d["delta"] >= -1e-12 and gain_dd >= SEUIL_DD - 1e-9:
        return "ADOPTABLE (décision explicite requise)"
    return "REJETÉ"


def _imprimer(mode: str, res: dict) -> None:
    from scripts.preset_replay import _ligne
    s = res["sorties"]
    d = res["delta"]
    print(f"\n== {mode} · lignes suivies {s['lignes_suivies']} · sorties {s['sorties']} "
          f"· rachats refusés {s['rachats_refuses']}")
    print(_ligne("sans sorties", res["sans"]["stats"]) + f"  frais {res['sans']['frais']:,.0f} $")
    print(_ligne("avec sorties", res["avec"]["stats"]) + f"  frais {res['avec']['frais']:,.0f} $")
    if d.get("disponible"):
        lo, hi = d["ic95"]
        print(f"  ΔSharpe {d['delta']:+.2f} [{lo:+.2f} ; {hi:+.2f}] p = {d['p']:.3f} "
              f"({d['verdict']})")
    print(f"  → {verdict(res)}")


def _consigner(mode: str, res: dict, pas: int) -> None:
    from packages.research.ledger import append_record
    st = res["avec"]["stats"]
    append_record({"date": datetime.now(UTC).date().isoformat(),
                   "facteur": f"preset_sorties:{mode}", "statut": "mesure",
                   "these": "Sorties entre deux rééquilibrages (ADR-0208).",
                   "params": {"pas": pas, "mode": mode}, "verdict": verdict(res),
                   "sharpe": st.get("sharpe"), "periods_per_year": 252,
                   "n_obs": len(res["avec"]["equity"]), "source": "make preset-sorties (réel)"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=sorted(MODES), action="append",
                    help="un mode (répétable) ; défaut : les trois pré-enregistrés")
    ap.add_argument("--pas", type=int, default=5)
    a = ap.parse_args()
    from packages.backtest.preset_rejeu import cibles_rejouees
    from packages.backtest.rejeu_sorties import comparer_sorties
    from scripts.preset_replay import _coeur, _donnees

    data, acmap, mode_donnees = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode_donnees}) — UNCALIBRATED.")
        return 1
    dd = float(os.environ.get("QUANT_DD_TARGET", "0.25"))
    params = {"dd_target": dd, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    coeur = _coeur(data)
    print(f"Décisions de production : {len(data)} séries ({mode_donnees}), pas {a.pas} j, "
          f"cœur {coeur or 'aucun'} (jamais géré) — calculées une fois pour tous les modes.")
    prep = cibles_rejouees(data, pas=a.pas, params=params, coeur=coeur or None)
    if prep is None:
        print("Indisponible : historique trop court.")
        return 1
    bilan = {}
    for mode in a.mode or list(MODES):
        regle, prise = MODES[mode]
        res = comparer_sorties(data, regle=regle, prise=prise, coeur=coeur or None,
                               classes=acmap, prep=prep)
        if not res.get("available"):
            print(f"{mode} : indisponible ({res.get('raison')})")
            continue
        _imprimer(mode, res)
        _consigner(mode, res, a.pas)
        bilan[mode] = {"verdict": verdict(res), "sans": res["sans"]["stats"],
                       "avec": res["avec"]["stats"], "delta": res["delta"],
                       "sorties": res["sorties"]}
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({"mesure_le": datetime.now(UTC).isoformat(timespec="seconds"),
                                  "mode_donnees": mode_donnees, "modes": bilan},
                                 ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    chemin = SORTIE.relative_to(ROOT) if SORTIE.is_relative_to(ROOT) else SORTIE
    print(f"\n→ {chemin} · {len(bilan)} essai(s) consigné(s) au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
