"""Chargement de config YAML — tout est config-driven (règle d'or 5).

Stratégies, filtres, seuils, univers, risque, pondérations de facteurs :
en YAML, jamais en dur. Un seul point d'entrée typé.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # dépendance externe → seulement dans `common`, jamais dans `core`
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def load_yaml(path: str | Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("pyyaml non installé : `uv add pyyaml`")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config introuvable : {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config YAML invalide (dict attendu) : {p}")
    return data


def load_config_dir(config_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Charge tous les .yaml/.yml d'un dossier, indexés par nom de fichier."""
    d = Path(config_dir)
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(d.glob("*.y*ml")):
        out[f.stem] = load_yaml(f)
    return out
