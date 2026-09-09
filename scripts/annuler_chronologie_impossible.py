#!/usr/bin/env python3
"""Retire les round-trips dont la sortie précède l'entrée — chronologie impossible.

Cf. `packages/research/chronologie_impossible.py` pour la mécanique complète (le
bug d'appariement déjà corrigé dans `reconcilier_journal`, et pourquoi on retire
plutôt que corriger). Sauvegarde la base et archive chaque ligne retirée
en JSON avant tout retrait.

    python scripts/annuler_chronologie_impossible.py              # SIMULATION (défaut)
    python scripts/annuler_chronologie_impossible.py --appliquer  # retire, archivé
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _resume(mauvais: list) -> None:
    pnl = sum(float(t.pnl_net or 0.0) for t in mauvais)
    print(f"\n  PLAN — {len(mauvais)} round-trip(s) avec une sortie antérieure à "
          f"leur entrée · {pnl:+,.2f} $ de « réalisé » fictif\n".replace(",", " "))
    for t in sorted(mauvais, key=lambda x: -abs(float(x.pnl_net or 0))):
        print(f"    {t.instrument:<10} entrée {str(t.entry_ts)[:10]} · "
              f"sortie {str(t.exit_ts)[:10]} · {float(t.pnl_net or 0):+10.2f} $")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.chronologie_impossible import archive, identifier
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    mauvais = identifier(journal.all())
    if not mauvais:
        print("\n  Aucune sortie antérieure à son entrée : rien à retirer.")
        return
    _resume(mauvais)
    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été retiré. Relancer avec `--appliquer`.")
        return
    horo = f"{datetime.now():%Y%m%d-%H%M%S}"
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-chronologie-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    piste = ROOT / "data" / f"chronologie-impossible-{horo}.json"
    piste.write_text(json.dumps([archive(t) for t in mauvais],
                                indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Archive des lignes retirées : {piste.name}")
    n = journal.supprimer([t.id for t in mauvais])
    print(f"  {n} round-trip(s) retiré(s).")
    print("  Relancer `make diag-journal` : le bloc « SORTIES ANTÉRIEURES » doit "
          "être vide, et `make turnover-audit` n'inclura plus ce faux réalisé.")


if __name__ == "__main__":
    main()
