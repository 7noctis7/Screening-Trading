"""Gate de publication (andon cord) — ÉCHEC ROUGE si le site construit est vide/périmé.

Empêche le pire défaut connu du pipeline : un déploiement « vert mais muet » (build OK
mais JSON absents/figés un jour ancien). À lancer APRÈS le build du site.

Contrôles (tous bloquants) :
  1. ≥ MIN_JSON fichiers data/*.json présents dans site/
  2. taille cumulée des JSON > MIN_TOTAL_BYTES (détecte un dump tronqué)
  3. data/meta.json lisible et `generated_at` daté d'AUJOURD'HUI (UTC) → fraîcheur
  4. fichiers clés présents et non-triviaux (dashboard, screen)
  5. PLAUSIBILITÉ des chiffres publiés (`packages.common.gate_publication`)

CE QUE LE CONTRÔLE 5 AJOUTE, ET POURQUOI IL MANQUAIT. Le 04/09, le site a publié — et le
téléphone a affiché — gain total −100 %, CAGR −100 %, pire baisse −100 %, avec un Sharpe
de 0,25 et un Sortino de 0,18. Les deux moitiés ne peuvent pas être vraies ensemble. Ce
gate était vert : les fichiers étaient présents, volumineux et datés du jour. **Il ne
regardait jamais les nombres.** Un dump parfaitement formé annonçait la ruine, et c'est
l'utilisateur qui l'a vu.

Le contrôle ne juge PAS la performance — une stratégie a le droit de perdre, et un gate
qui refuse les mauvaises nouvelles finit par cacher les vraies. Il refuse l'IMPOSSIBLE :
un capital anéanti avec un ratio positif, une courbe d'équity percée de `null`.
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

    motifs = _plausibilite(jsons)
    if motifs:
        for m in motifs[:12]:
            print(f"   · {m}")
        _fail(f"{len(motifs)} incohérence(s) dans les chiffres publiés")

    print(f"✅ Gate OK : {len(jsons)} JSON, {total // 1024} Ko, frais ({gen}), "
          "chiffres cohérents.")
    return 0


def _plausibilite(jsons: list[Path]) -> list[str]:
    """Motifs de refus trouvés dans les JSON publiés. Liste vide = rien d'impossible.

    Le module d'audit vit dans `packages/` pour être testable hors CI : un gate qu'on
    n'exerce pas en test est un gate qu'on découvre en panne le jour où il compte."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from packages.common.coherence_site import auditer as coherence
    from packages.common.coherence_site import dates_d_arrete
    from packages.common.gate_publication import auditer as plausibilite
    motifs: list[str] = []
    arretes: dict[str, str] = {}
    for p in sorted(jsons):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue              # illisible : déjà couvert par les contrôles 1-4
        if not isinstance(payload, dict):
            continue
        motifs += [f"{p.name}{m}" for m in plausibilite(payload)]
        motifs += [f"{p.name}{m}" for m in coherence(payload)]
        for chemin, jour in dates_d_arrete(payload).items():
            arretes[f"{p.name}{chemin}"] = jour
    _inventaire_arretes(arretes)
    return motifs


def _inventaire_arretes(arretes: dict[str, str]) -> None:
    """Recense les dates d'arrêté SANS bloquer. Elles diffèrent légitimement entre
    domaines — la crypto cote le week-end, les actions non — donc en faire une règle
    produirait un faux positif chaque samedi. On les rend LISIBLES : une divergence
    inattendue saute aux yeux dans le log, là où personne n'irait la chercher."""
    if not arretes:
        return
    par_jour: dict[str, list[str]] = {}
    for chemin, jour in arretes.items():
        par_jour.setdefault(jour, []).append(chemin)
    print(f"   dates d'arrêté publiées : {len(par_jour)} distincte(s)")
    for jour in sorted(par_jour, reverse=True):
        exemples = ", ".join(sorted(par_jour[jour])[:4])
        print(f"     {jour} — {len(par_jour[jour])} bloc(s) : {exemples}")


if __name__ == "__main__":
    raise SystemExit(main())
