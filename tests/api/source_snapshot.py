"""Texte source COMPLET du snapshot : la façade `snapshot.py` + ses morceaux (découpage 31/10).

Plusieurs tests vérifient une propriété du CODE du snapshot en lisant son texte (« aucun
appel sans tel paramètre », « la formule n'est écrite qu'une fois »). Depuis le découpage,
`apps/api/snapshot.py` n'est plus qu'une façade : un test qui ne lirait qu'elle passerait
sur du vide dès qu'il vérifie une ABSENCE. Ce module rend le texte de tous les fichiers.
"""
from pathlib import Path

API = Path(__file__).resolve().parents[2] / "apps" / "api"


def fichiers_snapshot() -> list[Path]:
    return [API / "snapshot.py", *sorted((API / "snapshot_parts").glob("*.py"))]


def source_snapshot() -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in fichiers_snapshot())
