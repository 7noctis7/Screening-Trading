"""make repro — manifeste de reproductibilité (auditabilité « niveau papier »).

Émet `out/repro.json` : empreinte exacte de l'état ayant produit un résultat (code,
config, version de cache snapshot, seed, environnement). Joint à un tear-sheet, rend
tout chiffre réplicable par un tiers. 100 % stdlib, best-effort, 0 dépendance.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # exécution directe → `apps`/`packages` importables


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _hash_dir(path: Path, pattern: str) -> str:
    h = hashlib.sha256()
    for f in sorted(path.glob(pattern)):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _snap_version() -> str:
    try:
        from apps.api.main import _SNAP_VERSION
        return _SNAP_VERSION
    except Exception:  # noqa: BLE001
        return "unavailable"


def _key_packages() -> dict:
    from importlib.metadata import PackageNotFoundError, version
    out = {}
    for p in ("numpy", "pandas", "scipy", "scikit-learn", "duckdb", "fastapi"):
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def main() -> int:
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "config_hash": _hash_dir(ROOT / "config", "*.yaml"),
        "snapshot_version": _snap_version(),
        "seed": 7,  # seed déterministe du snapshot/backtest
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": _key_packages(),
    }
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "repro.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ Manifeste de reproductibilité → {path}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
