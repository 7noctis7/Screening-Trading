"""Gate de publication (andon cord) — ÉCHEC ROUGE si le site construit est vide/périmé.

Empêche le pire défaut connu du pipeline : un déploiement « vert mais muet » (build OK
mais JSON absents/figés un jour ancien). À lancer APRÈS le build du site.

Contrôles (tous bloquants) :
  1. ≥ MIN_JSON fichiers data/*.json présents dans site/
  2. taille cumulée des JSON > MIN_TOTAL_BYTES (détecte un dump tronqué)
  3. data/meta.json lisible et `generated_at` daté d'AUJOURD'HUI (UTC) → fraîcheur
  4. fichiers clés présents et non-triviaux (dashboard, screen)
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SITE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("site")
MIN_JSON = 15
MIN_TOTAL_BYTES = 50_000
KEY_FILES = {"dashboard.json": 200, "screen.json": 50, "meta.json": 50}


def _fail(msg: str) -> None:
    print(f"❌ GATE PUBLICATION : {msg}")
    sys.exit(1)


def main() -> int:
    if not SITE.exists():
        _fail(f"dossier introuvable : {SITE}")
    jsons = list(SITE.rglob("data/*.json"))
    if len(jsons) < MIN_JSON:
        _fail(f"{len(jsons)} JSON < {MIN_JSON} attendus (dump incomplet ?)")
    total = sum(p.stat().st_size for p in jsons)
    if total < MIN_TOTAL_BYTES:
        _fail(f"taille cumulée {total} o < {MIN_TOTAL_BYTES} (dump tronqué ?)")

    by_name = {p.name: p for p in jsons}
    for name, min_bytes in KEY_FILES.items():
        p = by_name.get(name)
        if p is None:
            _fail(f"fichier clé manquant : data/{name}")
        if p.stat().st_size < min_bytes:
            _fail(f"data/{name} trop petit ({p.stat().st_size} o < {min_bytes})")

    try:
        meta = json.loads(by_name["meta.json"].read_text(encoding="utf-8"))
        gen = str(meta.get("generated_at", ""))[:10]
    except (OSError, ValueError) as e:
        _fail(f"meta.json illisible : {e}")
    today = datetime.now(UTC).date().isoformat()
    if gen != today:
        _fail(f"données périmées : generated_at={gen!r} ≠ aujourd'hui {today!r}")

    print(f"✅ Gate OK : {len(jsons)} JSON, {total // 1024} Ko, frais ({gen}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
