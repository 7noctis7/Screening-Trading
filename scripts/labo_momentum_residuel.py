#!/usr/bin/env python3
"""make labo-momentum-residuel — l'essai figé du momentum résiduel, de la mesure au verdict.

Lit `config/essais/2026-11-10_momentum_residuel.yaml` (déposé AVANT toute mesure) et les
mêmes séries négociables que `make preset-replay`. Publie l'IC de chaque variante face au
momentum 12-1, le portefeuille net de coûts, les quatre étages du gate, l'espérance par
épisode de détention et les compteurs. Sans base de prix réelle : UNCALIBRATED, rien n'est
mesuré ni consigné. Lecture seule : aucun réglage de production, aucun ordre.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ESSAI = ROOT / "config" / "essais" / "2026-11-10_momentum_residuel.yaml"
SORTIE = ROOT / "out" / "labo_momentum_residuel.json"


def _couts(syms: list[str], acmap: dict):
    """Coût par côté de chaque titre, selon sa classe (barème courtier du dépôt)."""
    import numpy as np

    from packages.execution import CostModel
    return np.array([CostModel.for_asset_class(acmap.get(s, "equity")).round_trip_bps
                     / 2.0 / 1e4 for s in syms])


def _consigner(res: dict, essai: dict, empreinte: str) -> int:
    """Un essai par (variante, horizon) mesuré + un pour le portefeuille. Réel seulement."""
    from packages.research.ledger import append_record
    jour = datetime.now(UTC).date().isoformat()
    n = 0
    for cle, r in res["ic"].items():
        e = r.get("ecart") or {}
        if cle.startswith("temoin") or not e.get("available"):
            continue
        append_record({"date": jour, "facteur": f"momentum_residuel:{cle}", "n_essais": 1,
                       "statut": "mesure", "essai": essai["nom"], "empreinte": empreinte,
                       "ecart_ic": e["ecart_ic_moyen"], "t_stat": e["t_stat"],
                       "p_signes": e["p_signes"], "n_obs": e["n_dates"],
                       "source": "make labo-momentum-residuel (réel)"})
        n += 1
    g, d = res["gate"], res["decision"]
    append_record({"date": jour, "facteur": "momentum_residuel:portefeuille", "n_essais": 1,
                   "statut": "promu" if d["strategie_promouvable"] else "rejete",
                   "essai": essai["nom"], "empreinte": empreinte,
                   "dsr": g.get("dsr_calcule"), "pbo": res["pbo"].get("pbo"),
                   "motifs": d["motifs"], "source": "make labo-momentum-residuel (réel)"})
    return n + 1


def _afficher(res: dict, essai: dict) -> None:
    print("\nIC apparié (candidat − momentum 12-1), fenêtres disjointes :")
    for cle, r in res["ic"].items():
        e = r.get("ecart")
        if e is None:
            continue
        if not e.get("available"):
            print(f"  {cle:16} UNCALIBRATED ({e.get('n_dates', 0)} dates)")
            continue
        c = r["compteurs"]
        print(f"  {cle:16} écart {e['ecart_ic_moyen']:+.4f}  t {e['t_stat'] or 0:+.2f}  "
              f"p {e['p_signes']:.3f}  moitiés {e['ecart_premiere_moitie']:+.3f} / "
              f"{e['ecart_seconde_moitie']:+.3f}  n={e['n_dates']}  "
              f"classés {c['titres_classes_mediane']}, écartés {c['titres_ecartes_mediane']}")
    g, ep = res["gate"], res["episodes"]
    print(f"\nPlacebo p {res['placebo']['p']:.3f} · PBO {res['pbo'].get('pbo')} · "
          f"sabotage survécu : {res['sabotage'].get('survives')}")
    if g.get("available"):
        print(f"DSR {g['dsr_calcule']} pour {g['n_essais']} essais · Sharpe actif hors "
              f"échantillon {g['sharpe_oos_annualise']:+.2f} (exigé : "
              f"{g['sharpe_exige_promouvable']:.2f} promouvable, "
              f"{g['sharpe_exige_deployable']:.2f} déployable)")
    f = res["face_temoin"]
    if f.get("available"):
        print(f"Top-{essai['top_k']} candidat − témoin : {f['ecart_annualise'] * 100:+.2f} %/an "
              f"[{f['ic95'][0] * 100:+.2f} ; {f['ic95'][1] * 100:+.2f}]")
    if ep.get("available"):
        print(f"Épisodes nets : n={ep['n']}  espérance {ep['esperance_simple'] * 100:+.2f} % "
              f"[{ep['ic95'][0] * 100:+.2f} ; {ep['ic95'][1] * 100:+.2f}]  gain "
              f"{ep['taux_gain'] * 100:.0f} %  PF {ep['profit_factor']}")
    print(f"Compteurs : {res['compteurs']}")
    d = res["decision"]
    print(f"\nFACTEUR retenu : {d['facteur_retenu']} · STRATÉGIE promouvable : "
          f"{d['strategie_promouvable']}")
    for m in d["motifs"]:
        print(f"  · {m}")


def main() -> int:
    import yaml

    from packages.research.essai_classement import mesurer
    from packages.research.labo_classement import panneau
    from scripts.preset_replay import _donnees
    essai = yaml.safe_load(ESSAI.read_text(encoding="utf-8"))
    empreinte = hashlib.sha256(ESSAI.read_bytes()).hexdigest()[:12]
    data, acmap, mode = _donnees()
    if mode == "synthetic" or (len(data) < 30
                               and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1"):
        print(f"UNCALIBRATED : {len(data)} séries réelles négociables ({mode}). "
              "Rien n'est mesuré, rien n'est consigné.")
        return 1
    pan = panneau(data)
    print(f"Essai {essai['nom']} [{empreinte}] · {len(pan['syms'])} séries ({mode}) · "
          f"{len(pan['jours'])} séances.")
    res = mesurer(pan, essai, _couts(pan["syms"], acmap))
    if not res.get("available"):
        print("UNCALIBRATED : historique trop court pour une seule décision.")
        return 1
    _afficher(res, essai)
    n = _consigner(res, essai, empreinte)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**res, "essai": essai["nom"], "empreinte": empreinte,
                                  "mode": mode}, ensure_ascii=False, indent=1, default=str))
    print(f"\nÉcrit : {SORTIE.relative_to(ROOT)} · {n} essai(s) consigné(s) au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
