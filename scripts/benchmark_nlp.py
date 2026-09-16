#!/usr/bin/env python3
"""Comparer les modèles locaux sur le MÊME jeu — latence, stabilité, conformité, accord.

  python scripts/benchmark_nlp.py                       # tous les modèles chargés
  python scripts/benchmark_nlp.py --modeles qwen2.5-7b-instruct gemma-2-2b-it
  python scripts/benchmark_nlp.py --repetitions 5       # stabilité plus exigeante

CE QU'IL NE MESURE PAS, ET IL FAUT LE LIRE AVANT LE TABLEAU : la valeur PRÉDICTIVE. Aucun
classement obtenu ici ne dit qu'un modèle fait gagner de l'argent. Un modèle peut être
rapide, stable, d'accord avec ses pairs, et parfaitement inutile. Seul `make alpha-nlp`,
sur des rendements réalisés, tranche la question qui compte.

L'usage juste de ce banc est d'ÉLIMINER : écarter ce qui est trop lent pour la séance, trop
instable pour être reproductible, ou qui ne tient pas le schéma. Ce qui survit va au banc
d'alpha.

Les modèles sont éprouvés EN SÉRIE. Sur 16 Go unifiés, alterner entre deux modèles chargés
fait payer un rechargement à chaque bascule : les latences mesurées décriraient alors
l'ordre des appels, pas les modèles.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _modeles_disponibles(pilote_nom: str, base: str) -> list[str]:
    from packages.nlp.config import ConfigNLP
    from packages.nlp.pilotes import choisir
    cfg = ConfigNLP.depuis_env()
    p = choisir(cfg.modele, pilote_nom or cfg.pilote, base or cfg.base)
    return p.modeles() if p is not None else []


def _ram() -> str:
    """Mémoire du processus d'inférence — best-effort, et DIT quand il ne sait pas.

    Le modèle est chargé par LM Studio ou Ollama, pas par nous : sans `psutil`, ce
    processus est invisible. Afficher « n/d » vaut mieux qu'un chiffre plausible obtenu en
    mesurant la mémoire du mauvais processus.
    """
    try:
        import psutil
    except Exception:  # noqa: BLE001
        return "n/d (installer psutil, ou lire la RAM dans LM Studio)"
    total = 0
    for proc in psutil.process_iter(["name", "memory_info"]):
        nom = (proc.info.get("name") or "").lower()
        if any(k in nom for k in ("lm studio", "lmstudio", "ollama", "llama-server")):
            total += (proc.info.get("memory_info").rss if proc.info.get("memory_info") else 0)
    return f"{total / 1e9:.2f} Go" if total else "n/d (processus d'inférence non trouvé)"


def _tableau(resultats: list) -> None:
    print("\n  " + "─" * 96)
    print(f"  {'modèle':28s} {'bon sens':>9s} {'conf.':>6s} {'repli':>6s} "
          f"{'stable':>7s} {'médiane':>9s} {'p90':>8s} {'jet/s':>7s}")
    print("  " + "─" * 96)
    for r in resultats:
        d = r.en_dict()
        stable = {True: "oui", False: "NON", None: "—"}[d["stable"]]
        print(f"  {d['modele'][:28]:28s} {d['bon_sens']:8.0%} "
              f"{d['conformes']:5d}/{d['n']:<1d} {d['replis']:6d} {stable:>7s} "
              f"{_ms(d['latence_mediane_ms']):>9s} {_ms(d['latence_p90_ms']):>8s} "
              f"{d['jetons_par_s'] or '—':>7}")
        for i in d["incidents"]:
            print(f"      ⚠ {i}")
    print("  " + "─" * 96)


def _ms(v) -> str:
    return f"{v:.0f} ms" if v else "—"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--modeles", nargs="*", default=None)
    ap.add_argument("--pilote", default="", choices=["", "auto", "lmstudio", "ollama"])
    ap.add_argument("--repetitions", type=int, default=3)
    a = ap.parse_args()

    from packages.nlp.banc import accord, eprouver

    modeles = a.modeles or _modeles_disponibles(a.pilote, "")
    if not modeles:
        print("⛔ Aucun modèle : le fournisseur ne répond pas, ou rien n'est chargé.",
              file=sys.stderr)
        print("   LM Studio → onglet Developer → Start Server (port 1234).", file=sys.stderr)
        return 2

    print(f"\n  {len(modeles)} modèle(s) à éprouver, EN SÉRIE · RAM inférence : {_ram()}")
    resultats = []
    for m in modeles:
        print(f"  … {m}")
        r = eprouver(m, a.pilote or "auto", repetitions=a.repetitions)
        if r is None:
            print(f"      ⛔ {m} : aucun fournisseur")
            continue
        resultats.append(r)
    if not resultats:
        return 2

    _tableau(resultats)
    for x in accord(resultats):
        print(f"  accord {x['a']} ↔ {x['b']} : {x['accord']:.0%} sur {x['n']} cas")
    if len(resultats) > 1:
        print("\n  ⚠ L'accord mesure la RESSEMBLANCE, pas la justesse : deux modèles "
              "entraînés\n    sur le même web se ressemblent, et restent d'accord sur "
              "une erreur.")
    print("\n  ⚠ Ce banc n'établit AUCUNE valeur prédictive. Il sert à ÉLIMINER ce qui est "
          "trop lent,\n    trop instable ou non conforme. Le verdict qui compte est "
          "`make alpha-nlp`.\n")
    # Fail-loud : un modèle qui rate les contrôles de bon sens ou part en repli est
    # disqualifié, et une chaîne doit pouvoir s'y arrêter.
    return 0 if any(r.taux_bon_sens >= 0.8 and not r.replis for r in resultats) else 1


if __name__ == "__main__":
    raise SystemExit(main())
