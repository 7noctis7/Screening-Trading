"""make macro-verify — contrôle que CHAQUE identifiant FRED existe et publie encore.

Pourquoi ce script existe : les identifiants ajoutés le 25/08 n'ont PAS pu être vérifiés depuis
l'environnement de développement (policy réseau refusant api.stlouisfed.org). Plutôt que de les
déclarer bons sur la foi d'une mémoire de modèle, on livre la commande qui tranche.

Aucune écriture, aucune clé affichée. Sortie ≠ 0 si une série est morte ou périmée : utilisable
en gate CI le jour où la clé y sera disponible.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from packages.macro.fred import POURQUOI, SERIES, _fetch

    cle = os.environ.get("FRED_API_KEY")
    if not cle:
        print("⛔ FRED_API_KEY absente. `export FRED_API_KEY=...` (clé gratuite sur "
              "fred.stlouisfed.org → My Account → API Keys), puis relancer.")
        return 2

    print(f"Vérification de {len(SERIES)} séries FRED…\n")
    print(f"  {'ID':16s} {'statut':9s} {'dernière obs':13s} {'retard':>7s}  libellé")
    morts, perimees = [], []
    for sid, label, _groupe, units, _unit in SERIES:
        d = _fetch(sid, units, cle)
        if not d:
            print(f"  {sid:16s} {'MORTE':9s} {'—':13s} {'—':>7s}  {label}")
            morts.append((sid, label))
            continue
        etat = "PÉRIMÉE" if d.get("perimee") else "ok"
        print(f"  {sid:16s} {etat:9s} {d['date']:13s} {d['retard_jours']:5d} j  {label}")
        if d.get("perimee"):
            perimees.append((sid, label, d["retard_jours"]))

    print()
    if morts:
        print(f"⛔ {len(morts)} série(s) INTROUVABLE(S) — identifiant erroné ou série retirée :")
        for sid, label in morts:
            print(f"   {sid} ({label})")
            if sid in POURQUOI:
                print(f"      apportait : {POURQUOI[sid]}")
    if perimees:
        print(f"⚠️  {len(perimees)} série(s) PÉRIMÉE(S) — elles répondent mais ne publient plus :")
        for sid, label, r in perimees:
            print(f"   {sid} ({label}) — {r} jours de retard")
    if not morts and not perimees:
        print("✅ toutes les séries répondent et publient à jour.")
    return 1 if morts else 0


if __name__ == "__main__":
    sys.exit(main())
