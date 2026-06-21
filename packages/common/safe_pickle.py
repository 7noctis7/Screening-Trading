"""Chargement `pickle` DURCI — defense-in-depth.

`pickle.load` exécute du code arbitraire à la désérialisation. Dans ce projet, le pickle ne sert
QU'À des artefacts **auto-générés et locaux** (snapshot de l'API, modèle ML). Ce module mitige le
vecteur « un attaquant remplace le fichier sur le disque » :
  - refuse les liens symboliques (signal clair de falsification / traversée) ;
  - avertit si le fichier est inscriptible par le groupe/les autres (permissions trop larges) ;
  - vérifie une empreinte SHA-256 optionnelle (sidecar `.sha256`) quand elle existe (provenance).

⚠️ Ne JAMAIS charger via ce module un pickle d'origine externe/réseau/non vérifiée.
"""
from __future__ import annotations

import hashlib
import logging
import os
import pickle
import stat
from pathlib import Path

log = logging.getLogger("quant.safe_pickle")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(obj, path) -> None:
    """Sérialise + écrit un sidecar `.sha256` (provenance vérifiable au chargement)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        pickle.dump(obj, f)
    try:
        p.with_suffix(p.suffix + ".sha256").write_text(_sha256(p), encoding="utf-8")
    except OSError:  # sidecar best-effort — ne bloque pas l'écriture
        pass


def load(path):
    """Charge un pickle LOCAL de confiance avec garde-fous. Lève en cas de falsification évidente."""
    p = Path(path)
    if p.is_symlink():
        raise OSError(f"refus de charger un pickle via lien symbolique (falsification possible) : {p}")
    try:
        mode = p.lstat().st_mode
        if os.name == "posix" and (mode & (stat.S_IWGRP | stat.S_IWOTH)):
            log.warning("pickle %s inscriptible par d'autres utilisateurs (mode %o) — restreins les permissions",
                        p, mode & 0o777)
    except OSError:
        pass
    sidecar = p.with_suffix(p.suffix + ".sha256")
    if sidecar.exists():
        expected = sidecar.read_text(encoding="utf-8").strip()
        if expected and _sha256(p) != expected:
            raise OSError(f"empreinte SHA-256 invalide pour {p} — artefact altéré, chargement refusé")
    with p.open("rb") as f:
        return pickle.load(f)  # noqa: S301 — artefact local auto-généré, chemin contrôlé + anti-symlink/hash
