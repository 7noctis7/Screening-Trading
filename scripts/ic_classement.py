"""make ic-classement — IC du classement momentum RÉELLEMENT TRADÉ (audit, rang 1).

Mesure, sur les mêmes séries négociables que `make preset-replay`, si le classement qui
choisit les 12 lignes de production prédit le rendement à 1, 5, 10, 20 et 60 séances,
contre une distribution nulle (scores permutés au sein de chaque date).

  make ic-classement                    # production : momentum 12-0
  make ic-classement ARGS="--saut 21"   # variante 12-1 : un AUTRE essai

Chaque horizon est consigné au registre des hypothèses comme un essai (compteur DSR).
Lecture seule : aucune donnée, aucun réglage de production n'est modifié.
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

SORTIE = ROOT / "out" / "ic_classement.json"


def _arguments() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saut", type=int, default=0,
                   help="0 = production (12-0), 21 = 12-1")
    p.add_argument("--nulles", type=int, default=200,
                   help="tirages de la distribution nulle")
    p.add_argument("--horizons", default="1,5,10,20,60")
    return p.parse_args()


def _ligne(r: dict) -> str:
    if not r.get("available"):
        return f"  h={r['horizon']:>3} j : UNCALIBRATED ({r.get('n_dates', 0)} dates)"
    t = r["t_stat"]
    return (f"  h={r['horizon']:>3} j : RankIC {r['ic_moyen']:+.4f}  t {t:+.2f}  "
            f"p_perm {r['p_permutation']:.3f}  (nulle |IC| p95 {r['nulle_p95']:.4f})  "
            f"top-12 − médiane {r['ecart_top12_moyen'] * 100:+.2f} %  "
            f"moitiés {r['ic_premiere_moitie']:+.3f} / {r['ic_seconde_moitie']:+.3f}  "
            f"n={r['n_dates']}")


def _consigner(res: dict, saut: int, mode: str) -> int:
    """Un essai par horizon MESURÉ, sur données réelles seulement : un passage
    synthétique ou une fenêtre UNCALIBRATED n'a rien testé et fausserait le compteur."""
    from packages.research.ledger import append_record
    if mode == "synthetic":
        return 0
    jour = datetime.now(UTC).date().isoformat()
    mesures = [r for r in res["resultats"] if r.get("available")]
    for r in mesures:
        append_record({
            "date": jour,
            "facteur": f"ic_classement:momentum_saut{saut}:h{r['horizon']}",
            "statut": "mesure", "horizon": r["horizon"], "n_essais": 1,
            "these": "Le classement momentum de production prédit le rendement futur.",
            "ic_moyen": r.get("ic_moyen"), "t_stat": r.get("t_stat"),
            "p_permutation": r.get("p_permutation"), "n_obs": r.get("n_dates"),
            "protocole": "RankIC par date, fenêtres disjointes, nulle par permutation",
            "source": "make ic-classement (réel)"})
    return len(mesures)


def main() -> int:
    a = _arguments()
    from packages.research.ic_classement import mesurer
    from scripts.preset_replay import _donnees
    data, _acmap, mode = _donnees()
    if len(data) < 30 and os.environ.get("QUANT_ALLOW_SYNTHETIC") != "1":
        print(f"⛔ {len(data)} séries réelles négociables ({mode}) — sans objet.")
        return 1
    horizons = tuple(int(h) for h in a.horizons.split(",") if h.strip())
    print(f"IC du classement tradé : {len(data)} séries ({mode}), saut {a.saut}, "
          f"horizons {horizons}, {a.nulles} tirages nuls.")
    res = mesurer(data, horizons=horizons, saut=a.saut, n_nulles=a.nulles)
    for r in res["resultats"]:
        print(_ligne(r))
    print(f"\n{res['horizons_testes']} horizons testés ensemble : aucun ne se lit "
          "seul.")
    n = _consigner(res, a.saut, mode)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({**res, "mode": mode}, ensure_ascii=False, indent=1))
    print(f"Écrit : {SORTIE.relative_to(ROOT)} · {n} essai(s) consigné(s) au registre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
