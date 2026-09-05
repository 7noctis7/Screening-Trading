#!/usr/bin/env python3
"""Retire les lots dont le « réalisé » double celui d'une correction nommée.

Cf. `packages/research/doublons_correction.py` pour la mécanique complète et la
règle de détection (même symbole, même date+prix de sortie, un enregistrement qui
cite un ordre réel + un qui n'en cite aucun). Sauvegarde la base et archive chaque
paire (doublon retiré + correction gardée) en JSON avant tout retrait.

SEUL le lot SANS NOM est retiré. La correction NOMMÉE — vérifiée contre l'ordre réel
du courtier — reste intacte : c'est elle qui a droit au « réalisé ».

    python scripts/annuler_doublons_correction.py              # SIMULATION (défaut)
    python scripts/annuler_doublons_correction.py --appliquer  # retire, archivé
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
    pnl = sum(float(d.doublon.pnl_net or 0.0) for d in doublons)
    print(f"\n  PLAN — {len(doublons)} doublon(s) de fermeture · "
          f"{pnl:+,.2f} $ de « réalisé » en double\n".replace(",", " "))
    for d in sorted(doublons, key=lambda x: -abs(float(x.doublon.pnl_net or 0))):
        t, n = d.doublon, d.nomme
        print(f"    {t.instrument:<10} sortie {str(t.exit_ts)[:10]} @ "
              f"{t.exit_price:.4f} · {t.qty:12.6f} unité(s) · "
              f"{float(t.pnl_net or 0):+10.2f} $")
        print(f"      ↳ doublonne {n.id} ({n.exit_reason})")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from packages.research.doublons_correction import archive, identifier
    from packages.storage import SqliteTradeJournal
    journal = SqliteTradeJournal()
    doublons = identifier(journal.all())
    if not doublons:
        print("\n  Aucun doublon détecté : rien à retirer.")
        return
    _resume(doublons)
    if "--appliquer" not in sys.argv:
        print("\n  SIMULATION — rien n'a été retiré. Relancer avec `--appliquer`.")
        return
    horo = f"{datetime.now():%Y%m%d-%H%M%S}"
    src = ROOT / "data" / "journal.db"
    if src.exists():
        dest = src.with_suffix(f".avant-doublons-{horo}.db")
        shutil.copy2(src, dest)
        print(f"\n  Sauvegarde : {dest.name}")
    piste = ROOT / "data" / f"doublons-correction-{horo}.json"
    piste.write_text(json.dumps([archive(d) for d in doublons],
                                indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Archive des paires (doublon + correction gardée) : {piste.name}")
    n = journal.supprimer([d.doublon.id for d in doublons])
    print(f"  {n} doublon(s) retiré(s). Les corrections nommées restent intactes.")
    print("  Relancer `make diag-surfermeture` : le total INVENTÉ doit baisser d'au")
    print("  moins la somme retirée ici (le résidu restant = ventes non journalisées,")
    print("  un trou différent, pas une invention).")


if __name__ == "__main__":
    main()
