#!/usr/bin/env python3
"""Vérifie les contrats de Skills (`skills/**/*.skill.yaml`). Sort ≠ 0 si un écart."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.common.skills_contrat import message, rapport  # noqa: E402

if __name__ == "__main__":
    r = rapport()
    print(message(r))
    raise SystemExit(1 if r.get("ecarts") or r.get("sans_schema") else 0)
