#!/usr/bin/env python3
"""Retire les lots OUVERTS enregistrés deux fois (même titre, quantité, prix ET jour).

Cf. `packages/research/doublons_ouverts.py` pour la règle complète : lequel des deux
est gardé (provenance la plus sûre d'abord : `P-`, puis `C-`, puis `LEG-`), et pourquoi
un lot ouvert en double n'est pas cosmétique — il fournit un lot de PLUS à apparier en
FIFO, donc du « réalisé » sans contrepartie chez le courtier.

D'OÙ VIENT CET OUTIL (18/09). `diag-journal` détectait ces doublons depuis le 03/09 et
les imprimait ; AUCUN script de la chaîne ne les retirait. `annuler_doublons_correction`
ne traite que les doublons de FERMETURE. Un défaut détecté sans remède reste, et celui
de QQQ a survécu à trois passages de `make reparer-journal`.

Sauvegarde la base et archive chaque groupe retiré en JSON avant tout retrait — un
retrait sans sa preuve n'est pas rejugeable.

    python scripts/annuler_doublons_ouverts.py               # SIMULATION (défaut)
    python scripts/annuler_doublons_ouverts.py --appliquer   # retire, archivé
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _resume(doublons: list) -> None:
    n = sum(len(d.retires) for d in doublons)
    print(f"\n  PLAN — {len(doublons)} groupe(s), soit {n} lot(s) ouvert(s) "
          "EXCÉDENTAIRE(S)\n")
    for d in doublons:
        print(f"    {d.cle[0]:<12} {d.qty:14.6f} @ {d.prix:11.4f}  le {d.jour}")
        print(f"      ↳ gardé : {d.garde}   ·   retiré(s) : {', '.join(d.retires)}")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.doublons_ouverts import identifiants_retires, plan
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    doublons = plan(journal.all())
    if not doublons:
        print("\n  Aucun lot ouvert en double : rien à retirer.")
        return
    _resume(doublons)
    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été retiré. Relancer avec `--appliquer`.")
        return
    horo = f"{datetime.now():%Y%m%d-%H%M%S}"
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-doublons-ouverts-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    piste = ROOT / "data" / f"doublons-ouverts-{horo}.json"
    piste.write_text(json.dumps([d.en_dict() for d in doublons],
                                indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Archive des groupes (gardé + retirés) : {piste.name}")
    n = journal.supprimer(identifiants_retires(doublons))
    print(f"  {n} lot(s) ouvert(s) en double retiré(s). L'exemplaire à la provenance")
    print("  la plus sûre reste intact — on retire une copie, jamais l'original.")


if __name__ == "__main__":
    main()
