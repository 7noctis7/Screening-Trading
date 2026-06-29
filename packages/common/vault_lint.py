"""Lint du vault — intégrité de la MÉMOIRE (liens morts, orphelins, ADR en double).

Même esprit que l'audit data : un gate qui empêche le pourrissement de la doc. Détecte
ce qui se vérifie de façon FIABLE (structurel) — pas de détection floue de « claims »
(trop de faux positifs). stdlib pur, testable hors-ligne.
"""

from __future__ import annotations

import re
from pathlib import Path

_EXCLUDE_DIRS = {".obsidian", ".smart-env", ".trash", "04_Companies"}
_EXCLUDE_NAMES = {"_TOP200.md", "Performance_Report.md", "Preset_Performance.md"}
_WIKILINK = re.compile(r"\[\[([^\]\|#]+)")    # [[Note]] / [[Note|a]] / [[Note#h]]
_MDLINK = re.compile(r"\]\(([^)]+\.md)[^)]*\)")      # [txt](chemin.md)
_ADR = re.compile(r"^#+\s*ADR-(\d{3,4})", re.MULTILINE)


def _iter_md(vault: Path):
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if set(rel.parts) & _EXCLUDE_DIRS or p.name in _EXCLUDE_NAMES:
            continue
        yield p


def extract_links(text: str) -> tuple[set[str], set[str]]:
    """(wikilinks, liens-chemin .md) d'un texte Markdown."""
    return ({m.strip() for m in _WIKILINK.findall(text)},
            {m.strip() for m in _MDLINK.findall(text)})


def _is_index_like(p: Path) -> bool:
    n = p.stem
    return (n[:2].isdigit() or n.startswith("_") or "Dashboard" in n
            or "TEMPLATE" in n or "INDEX" in n)


def lint_vault(vault: str | Path) -> dict:
    """Scanne le vault → {dead_links, orphans, duplicate_adrs, n_notes, ok}.

    - dead_links : `[[X]]` ou `chemin.md` ne résolvant vers aucun fichier (gate dur).
    - orphans : note de sous-dossier référencée par PERSONNE (avertissement).
    - duplicate_adrs : même numéro ADR deux fois dans 02_DECISIONS (gate dur).
    """
    vault = Path(vault)
    files = list(_iter_md(vault))
    by_stem: dict[str, Path] = {p.stem: p for p in files}
    known = set(by_stem) | {n[:-3] for n in _EXCLUDE_NAMES}   # exclus = existants
    referenced: set[str] = set()
    dead: list[dict] = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        wikis, paths = extract_links(text)
        for w in wikis:
            if Path(w).suffix and Path(w).suffix.lower() != ".md":
                continue                                 # embed (.svg/.png) → ignoré
            stem = Path(w).name                          # gère [[dossier/note]]
            if w in known or stem in known:
                referenced.add(stem)
            else:
                dead.append({"in": p.name, "link": f"[[{w}]]"})
        for rel in paths:
            stem = Path(rel).stem
            resolved = ((vault / rel.replace("vault/", "")).exists()
                        or (p.parent / rel).exists() or stem in known)
            referenced.add(stem) if resolved else dead.append(
                {"in": p.name, "link": rel})
    orphans = sorted(p.name for p in files
                     if p.parent != vault and not _is_index_like(p)
                     and p.stem not in referenced)
    adrs: list[str] = []
    dec = by_stem.get("02_DECISIONS")
    if dec:
        adrs = _ADR.findall(dec.read_text(encoding="utf-8", errors="ignore"))
    dups = sorted({a for a in adrs if adrs.count(a) > 1})
    return {"n_notes": len(files), "dead_links": dead, "orphans": orphans,
            "duplicate_adrs": dups, "ok": not dead and not dups}
