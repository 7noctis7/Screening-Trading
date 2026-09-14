#!/usr/bin/env python3
"""Brief unifié — un one-pager qui agrège l'état du projet (anti-friction, gratuit, stdlib).

Rassemble : changements récents du vault (git), dernière entrée du JOURNAL, priorités P0/P1 du
TODO, et un résumé de l'audit data (best-effort). Affiche en Markdown ; `--write` l'enregistre dans
`vault/_BRIEF.md` (à consulter le matin). Aucune dépendance externe.

  python scripts/daily_brief.py
  python scripts/daily_brief.py --write --since "24 hours ago"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _recent_vault_changes(since: str) -> list[str]:
    out = _git("log", f"--since={since}", "--name-only", "--pretty=format:", "--", "vault/")
    files = sorted({ln for ln in out.splitlines() if ln.strip()})
    return files


def _latest_journal() -> str:
    f = VAULT / "04_JOURNAL.md"
    if not f.exists():
        return "(journal absent)"
    block: list[str] = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        if ln.startswith("## ") and block:
            break
        if ln.startswith("## ") or block:
            block.append(ln)
    return "\n".join(block[:14]).strip() or "(vide)"


def _priorities() -> list[str]:
    f = VAULT / "03_TODO.md"
    if not f.exists():
        return []
    return [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines()
            if ("P0" in ln or "P1" in ln) and ln.strip().startswith(("-", "*", "|"))][:8]


def _data_audit() -> str:
    """L'audit des bases, lancé avec l'interpréteur QUI FAIT TOURNER CE BRIEF.

    `["python", ...]` cherchait un binaire nommé exactement `python` dans le PATH.
    Sur le VPS il n'y en a pas — Ubuntu n'expose que `python3` — et le brief
    affichait « (audit indisponible) » chaque matin, message qui se lit comme
    un état normal.
    Même famille que les treize commandes mortes : un appel cassé qu'un `except` général
    déguise en situation prévue. `sys.executable` est le `.venv/bin/python` que le
    Makefile a déjà choisi, donc celui qui a les dépendances de l'audit.

    Et quand ça rate quand même, on DIT quoi : un diagnostic vaut mieux qu'un mot poli.
    """
    try:
        r = subprocess.run([sys.executable, "scripts/data_audit.py"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        return f"(audit non lancé : {type(e).__name__} — {e})"
    lignes = [ln for ln in r.stdout.splitlines() if ln.startswith("·")]
    if lignes:
        return "\n".join(lignes)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout).strip().splitlines()
        fin = detail[-1] if detail else "aucune sortie"
        return f"(audit en échec, code {r.returncode} : {fin})"
    return "(pas de base locale auditée)"


def build() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    changes = _recent_vault_changes("24 hours ago")
    parts = [f"# 🗞️ Brief — {today}", ""]
    parts += ["## 🎯 Priorités (P0/P1)"]
    pr = _priorities()
    parts += (pr or ["(aucune priorité P0/P1 listée dans 03_TODO)"])
    parts += ["", "## 📓 Dernière entrée de journal", _latest_journal()]
    parts += ["", "## 🔄 Notes du vault modifiées (24 h)"]
    parts += ([f"- {c}" for c in changes] or ["(aucune)"])
    parts += ["", "## 🩺 Audit données", "```", _data_audit(), "```"]
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="écrit dans vault/_BRIEF.md")
    a = ap.parse_args()
    brief = build()
    if a.write:
        (VAULT / "_BRIEF.md").write_text(brief, encoding="utf-8")
        print(f"✅ vault/_BRIEF.md écrit ({len(brief)} car.)")
    else:
        print(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
