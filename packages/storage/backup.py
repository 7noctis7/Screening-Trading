"""Sauvegarde & restauration SQLite (API backup native, cohérente à chaud)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def backup_sqlite(src_path: str | Path, dst_path: str | Path) -> Path:
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(src_path))
    out = sqlite3.connect(str(dst))
    with out:
        src.backup(out)
    src.close(); out.close()
    return dst


def restore_sqlite(backup_path: str | Path, target_path: str | Path) -> Path:
    return backup_sqlite(backup_path, target_path)
