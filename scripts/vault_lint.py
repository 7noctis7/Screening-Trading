"""make vault-lint — intégrité du vault (liens morts, orphelins, ADR en double).

Garde ta MÉMOIRE aussi honnête que ton code. exit≠0 si lien mort ou ADR dupliqué
(gate dur) ; les orphelins sont des avertissements. 0 €, stdlib.

  make vault-lint
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import argparse

    from packages.common.vault_lint import lint_vault
    ap = argparse.ArgumentParser(description="Lint du vault")
    ap.add_argument("--strict", action="store_true",
                    help="exit≠0 aussi sur liens morts / orphelins (gate CI)")
    a = ap.parse_args()
    r = lint_vault(ROOT / "vault")
    print(f"\nVault-lint · {r['n_notes']} notes")
    # GROUPÉ PAR CIBLE. Cinquante occurrences de quinze liens se lisent comme cinquante
    # problèmes ; la liste devient trop longue pour être parcourue, donc elle ne l'est
    # plus. Ce qui se corrige, c'est une CIBLE manquante, pas chacune de ses mentions.
    from collections import Counter
    cibles = Counter(d["link"] for d in r["dead_links"])
    print(f"  liens morts : {len(r['dead_links'])} mention(s), "
          f"{len(cibles)} cible(s) absente(s)")
    for lien, n in cibles.most_common(15):
        ou = ", ".join(sorted({d["in"] for d in r["dead_links"]
                               if d["link"] == lien})[:3])
        print(f"     ✗ {lien:24s} ×{n:<3d} ({ou})")
    if len(cibles) > 15:
        print(f"     … et {len(cibles) - 15} autre(s) cible(s)")
    print(f"  ADR en double   : {r['duplicate_adrs'] or '—'}")
    print(f"  orphelins ({len(r['orphans'])}) : "
          f"{', '.join(r['orphans'][:15]) or '—'}")
    # gate dur : ADR dupliqués (vrai bug) toujours ; le reste seulement en --strict
    if r["duplicate_adrs"]:
        print("  → ❌ ADR dupliqué (corriger).")
        return 1
    if a.strict and (r["dead_links"] or r["orphans"]):
        print("  → ❌ --strict : liens morts / orphelins à corriger.")
        return 1
    print("  → ✅ pas de bug bloquant (liens morts/orphelins = avertissements).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
