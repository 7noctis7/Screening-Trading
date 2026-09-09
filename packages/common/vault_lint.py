"""Lint du vault — intégrité de la MÉMOIRE (liens morts, orphelins, ADR en double).

Même esprit que l'audit data : un gate qui empêche le pourrissement de la doc. Détecte
ce qui se vérifie de façon FIABLE (structurel) — pas de détection floue de « claims »
(trop de faux positifs). stdlib pur, testable hors-ligne.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_EXCLUDE_DIRS = {".obsidian", ".smart-env", ".trash", "04_Companies"}
_EXCLUDE_NAMES = {"_TOP200.md", "Performance_Report.md", "Preset_Performance.md"}
# Le `\n` dans la classe exclue est ESSENTIEL : une cible de wikilink ne franchit jamais
# une fin de ligne. Sans lui, un `[[` isolé — dans un exemple, un extrait de code mal
# découpé — avalait tout le fichier jusqu'au prochain `]`, et le rapport affichait un
# « lien mort » de plusieurs paragraphes. Vu le 09/09, produit par le texte d'un ADR.
_WIKILINK = re.compile(r"\[\[([^\]\|#\n]+)")   # [[Note]] / [[Note|a]] / [[Note#h]]
# Un lien CITÉ dans du code n'est pas un lien : c'est de la documentation. `00_INDEX.md`
# explique « suivre un lien `[[...]]` » — le linter y voyait deux liens morts, `[[...]]`
# et `` [[` ]] ``, et les comptait parmi les vrais. Deux fausses alertes noyées dans la
# liste, dans un outil dont le seul travail est de faire remonter les vraies.
_BLOC_CODE = re.compile(r"```.*?```", re.DOTALL)
# Les délimiteurs se comptent : Markdown autorise N accents graves, et il en faut N pour
# refermer. `` `x` `` — deux accents pour citer un accent — est le cas exact qui a piégé
# la première version : elle ne connaissait que le délimiteur simple, coupait au mauvais
# endroit, et laissait derrière elle un `[[` orphelin.
_CODE_INLINE = re.compile(r"(`+)(?:.|\n)+?\1")
_MDLINK = re.compile(r"\]\(([^)]+\.md)[^)]*\)")      # [txt](chemin.md)
_ADR = re.compile(r"^#+\s*ADR-(\d{3,4})", re.MULTILINE)
# HORODATAGE. Une décision et une séance de travail sont des faits PASSÉS : leur date
# ne peut pas être dans le futur. Douze ADR ont pourtant été datés du lendemain
# (09/09), et rien ne l'a signalé — la traçabilité du vault repose entièrement sur
# ces dates. Contrôle volontairement ÉTROIT : seuls les en-têtes, jamais le corps,
# où « rejuger au 2026-12-01 » est un rendez-vous légitime, pas une erreur.
_ADR_DATE = re.compile(r"^#+\s*ADR-(\d{3,4})\b.*\((\d{4}-\d{2}-\d{2})\)\s*$",
                       re.MULTILINE)
_SESSION_DATE = re.compile(r"^#+\s*Session\s+(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _iter_md(vault: Path):
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if set(rel.parts) & _EXCLUDE_DIRS or p.name in _EXCLUDE_NAMES:
            continue
        yield p


def sans_code(text: str) -> str:
    """Texte privé de ses blocs et de ses portions de code.

    Les blocs d'abord : une portion en ligne peut vivre à l'intérieur d'un bloc, jamais
    l'inverse. Remplacés par une espace plutôt que supprimés, pour ne pas coller deux
    mots qui ne se touchaient pas.
    """
    return _CODE_INLINE.sub(" ", _BLOC_CODE.sub(" ", text))


def extract_links(text: str) -> tuple[set[str], set[str]]:
    """(wikilinks, liens-chemin .md) d'un texte Markdown, HORS code."""
    utile = sans_code(text)
    return ({m.strip() for m in _WIKILINK.findall(utile)},
            {m.strip() for m in _MDLINK.findall(utile)})


def dates_futures(vault: str | Path, aujourdhui: date | None = None) -> list[dict]:
    """En-têtes d'ADR et de session portant une date postérieure à `aujourdhui`.

    Un en-tête non daté n'est pas une erreur : les ADR d'avant 0030 n'en portaient pas.
    On ne contrôle que ce qui est écrit.
    """
    vault, jour = Path(vault), aujourdhui or date.today()
    trouves: list[dict] = []
    for nom, motif, groupe in (("02_DECISIONS", _ADR_DATE, 1),
                               ("04_JOURNAL", _SESSION_DATE, 0)):
        f = vault / f"{nom}.md"
        if not f.exists():
            continue
        for m in motif.finditer(f.read_text(encoding="utf-8", errors="ignore")):
            d = m.group(2) if groupe else m.group(1)
            if date.fromisoformat(d) > jour:
                trouves.append({"in": f.name, "entete": m.group(0).strip()[:70],
                                "date": d})
    return trouves


def _est_gabarit(p: Path) -> bool:
    """Un gabarit contient des ESPACES RÉSERVÉS, pas des liens : `[[paper_xxx]]` y
    attend d'être remplacé. Le signaler comme mort à chaque passage est un faux positif
    permanent — et un avertissement permanent finit par être ignoré, y compris les
    jours où il a raison."""
    return "TEMPLATE" in p.stem.upper()


def _is_index_like(p: Path) -> bool:
    n = p.stem
    return (n[:2].isdigit() or n.startswith("_") or "Dashboard" in n
            or "TEMPLATE" in n or "INDEX" in n)


def lint_vault(vault: str | Path, aujourdhui: date | None = None) -> dict:
    """Scanne le vault → {dead_links, orphans, duplicate_adrs, n_notes, ok}.

    - dead_links : `[[X]]` ou `chemin.md` ne résolvant vers aucun fichier (gate dur).
    - orphans : note de sous-dossier référencée par PERSONNE (avertissement).
    - duplicate_adrs : même numéro ADR deux fois dans 02_DECISIONS (gate dur).
    - dates_futures : ADR/session daté après aujourd'hui (gate dur).
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
        if _est_gabarit(p):
            referenced.update(Path(w).name for w in wikis)   # placeholders : pas morts
            continue
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
    futures = dates_futures(vault, aujourdhui)
    return {"n_notes": len(files), "dead_links": dead, "orphans": orphans,
            "duplicate_adrs": dups, "dates_futures": futures,
            "ok": not dead and not dups and not futures}
