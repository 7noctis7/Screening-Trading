#!/usr/bin/env python3
"""Combien de moyennes ? Une question de FRÉQUENCE, pas de performance.

POURQUOI CE BANC NE MESURE AUCUN SHARPE, ET C'EST DÉLIBÉRÉ. Chercher « le meilleur
réglage » en comparant des performances, c'est faire un essai par configuration — et
le maximum de N Sharpe bruités croît en sqrt(2 ln N). Sur cinq configurations on gagne
« gratuitement » près d'un écart-type, et le DSR de TOUT le reste s'en trouve déflaté.

Or COMPTER LES DÉCLENCHEMENTS N'EST PAS UN ESSAI. La fréquence d'un setup et son
recouvrement avec le filtre existant sont des propriétés STRUCTURELLES : les mesurer
n'expose à aucun surapprentissage, puisqu'aucune performance n'entre dans le choix.
On explore donc librement cette dimension, on arrête UNE configuration, et elle seule
va au banc de performance.

RÈGLE DE CHOIX : on retient la configuration la PLUS RESTRICTIVE — la plus proche de
la thèse d'origine — gardant au moins 4 lignes détenues en moyenne et un phi < 0,50
face au filtre de production. Jamais celle qui « performe » le mieux : aucune
performance n'est calculée ici.

LE PREMIER CRITÈRE ÉTAIT MAL POSÉ, et le corriger n'est pas se dédire. J'avais écrit
« part investie >= 20 % ». Cette mesure dit seulement si le portefeuille détient AU
MOINS UNE ligne : avec 150 titres et 21 jours de détention, elle vaut ~100 % quelle que
soit la configuration. Elle ne discriminait rien — ce n'est pas un résultat qui déplaît,
c'est une grandeur qui ne mesure pas ce qu'on croyait. Le nombre MOYEN de lignes, lui,
distingue bien (3,2 contre 8,2) et dit ce qui compte : à trois lignes, un seul titre
porte un tiers du rendement quotidien.

Un setup qui ne se déclenche que vingt fois en onze ans ne produira jamais de preuve,
quel que soit son mérite. C'est cela qu'on élimine d'abord.

    python scripts/reglage_capitulation.py          # ~150 titres
    python scripts/reglage_capitulation.py 300
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Configurations DÉCLARÉES D'AVANCE, et conventionnelles plutôt qu'ajustées : 50/200 est
# la paire canonique (l'état « croix de la mort »), pas un choix tiré des données.
CONFIGS = (
    ("4 MM  20/50/100/200", (20, 50, 100, 200)),
    ("3 MM     50/100/200", (50, 100, 200)),
    ("2 MM        50/200", (50, 200)),
    ("2 MM         20/50", (20, 50)),
    ("1 MM           200", (200,)),
)
LIGNES_MIN = 4.0
PHI_MAX = 0.50


def main() -> None:
    from packages.research.flux_candidat import flux_quotidien
    from scripts.candidats_lab import _capitulation
    from scripts.signal_lab import _phi
    from scripts.sizing_lab import _donnees, _vix, empreinte

    n_max = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    data, _acmap, mode, n_reels, debut, fin = _donnees()
    if n_reels < 30:
        print("⚠️  Aucune base réelle branchée — ce banc ne décide de rien.")
        return
    data = {s: data[s] for s in sorted(data)[:n_max]}
    _, prov = _vix(data, debut, fin)
    print(f"\nmode {mode}\nempreinte : {empreinte(data, prov)}")
    print("\nAucun Sharpe ici : compter les déclenchements n'est pas un essai,")
    print("comparer des performances en est un. Voir l'en-tête du script.\n")

    prod = _reference(data)
    entete = ("configuration", "résolution", "signaux", "titres", "lignes", "phi")
    larg = (20, 10, 8, 6, 7, 6)
    print("  " + " | ".join(f"{c:>{w}}" for c, w in zip(entete, larg, strict=True)))
    print("  " + "-" * 70)
    for nom, mm in CONFIGS:
        for label, hebdo in (("hebdo", True), ("daily", False)):
            _ligne(data, prod, nom, mm, label, hebdo, flux_quotidien,
                   _capitulation, _phi)
    print("\n  Retenu : la configuration la PLUS RESTRICTIVE gardant "
          f"lignes >= {LIGNES_MIN:.0f} et phi < {PHI_MAX:.2f}.")
    print("  Un setup qui se déclenche vingt fois en onze ans ne prouvera rien.\n")


def _reference(data: dict) -> list[bool]:
    """Le filtre de production, échantillonné aux mêmes dates que les candidats."""
    from scripts.signal_lab import _filtre_production
    out = []
    for s in sorted(data):
        b = data[s]
        out.extend(_filtre_production(b, i) for i in range(250, len(b), 5))
    return out


def _ligne(data, prod, nom, mm, label, hebdo, flux_quotidien, capitulation,
           phi) -> None:
    fn = capitulation(data, hebdo=hebdo, moyennes=mm)
    f = flux_quotidien(data, fn, fenetre=2, pas=5)
    if not f.get("available"):
        print(f"  {nom:>20} | {label:>10} | {f.get('motif', '—')}")
        return
    # DÉCLENCHEMENTS BRUTS, pas l'état « détenu » : compter l'état revient à compter la
    # durée de détention. Le phi, lui, se lit sur l'état — c'est bien ce qu'un
    # portefeuille détiendrait face au filtre de production.
    decl = getattr(fn, "declenchements", {})
    n_sig = sum(len(v) for v in decl.values())
    titres = sum(1 for v in decl.values() if v)
    etat = []
    for s in sorted(data):
        b = data[s]
        etat.extend(fn(b[max(0, i - 1):i + 1], s) for i in range(250, len(b), 5))
    coef = phi(prod, etat) if len(prod) == len(etat) else float("nan")
    print(f"  {nom:>20} | {label:>10} | {n_sig:>8,} | {titres:>6} "
          f"| {f['lignes_moyen']:>6.1f} | {coef:>+6.2f}")


if __name__ == "__main__":
    main()
