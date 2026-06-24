"""Ledger d'hypothèses d'alpha (anti-réinvention + anti p-hacking), 0 dépendance.

Chaque essai de calibration s'écrit en JSONL append-only : on garde la TRACE de tous
les essais → (1) on ne re-teste pas une idée rejetée ; (2) on connaît le NOMBRE d'essais
`N` qui déflate le Sharpe (DSR, López de Prado). La recherche devient requêtable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("research/hypotheses.jsonl")
NOTES_DIR = Path("vault/08_Alphas")


def append_record(record: dict, path: str | Path = DEFAULT_PATH) -> None:
    """Ajoute un essai au ledger (JSONL append-only). Crée le fichier si besoin."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_records(path: str | Path = DEFAULT_PATH) -> list[dict]:
    """Lit tous les essais (ignore les lignes vides/corrompues, jamais bloquant)."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def trial_count(path: str | Path = DEFAULT_PATH, *, facteur: str | None = None,
                classe: str | None = None) -> int:
    """Nombre d'essais (filtrable par facteur/classe). Sert de `N` pour le DSR."""
    recs = read_records(path)
    if facteur is not None:
        recs = [r for r in recs if r.get("facteur") == facteur]
    if classe is not None:
        recs = [r for r in recs if classe in (r.get("classe") or [])]
    return len(recs)


def best_by_dsr(path: str | Path = DEFAULT_PATH, top: int = 5) -> list[dict]:
    """Meilleurs essais par Sharpe déflaté (DSR) décroissant."""
    recs = [r for r in read_records(path) if isinstance(r.get("dsr"), (int, float))]
    recs.sort(key=lambda r: r["dsr"], reverse=True)
    return recs[:top]


def summary(path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    """Synthèse : nb d'essais, nb robustes (DSR>0.5), meilleur DSR."""
    recs = read_records(path)
    dsrs = [r["dsr"] for r in recs if isinstance(r.get("dsr"), (int, float))]
    return {
        "n_trials": len(recs),
        "n_robust": sum(1 for d in dsrs if d > 0.5),
        "best_dsr": round(max(dsrs), 4) if dsrs else None,
    }


def _best_by_factor(records: list[dict]) -> dict[str, dict]:
    """Par facteur : le meilleur essai par DSR (sinon le dernier enregistré)."""
    out: dict[str, dict] = {}
    for r in records:
        f = r.get("facteur")
        if f is None:
            continue
        cur = out.get(f)
        rd = r.get("dsr")
        if cur is None:
            out[f] = r
        elif isinstance(rd, (int, float)):
            cd = cur.get("dsr")
            if not isinstance(cd, (int, float)) or rd >= cd:
                out[f] = r
    return out


def _set_frontmatter_key(text: str, key: str, value: Any) -> str:
    """Remplace `key: ...` (1re occurrence ; les clés ne sont qu'en frontmatter)."""
    val = "null" if value is None else value
    pat = re.compile(rf"^({re.escape(key)}:)[ \t]*.*$", re.MULTILINE)
    new, n = pat.subn(rf"\1 {val}", text, count=1)
    return new if n else text


def sync_notes_frontmatter(notes_dir: str | Path = NOTES_DIR,
                           path: str | Path = DEFAULT_PATH) -> int:
    """Propage le ledger vers le frontmatter des notes `08_Alphas/` (dsr/pbo/sharpe/
    maxdd) par correspondance de `facteur`. Retourne le nombre de notes mises à jour."""
    nd = Path(notes_dir)
    if not nd.exists():
        return 0
    by_fac = _best_by_factor(read_records(path))
    updated = 0
    for md in sorted(nd.glob("*.md")):
        if md.name.startswith(("_", "00_")):          # template + dashboard exclus
            continue
        text = md.read_text(encoding="utf-8")
        fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not fm:
            continue
        fac = re.search(r'^facteur:[ \t]*"?([\w]+)"?', fm.group(1), re.MULTILINE)
        rec = by_fac.get(fac.group(1)) if fac else None
        if not rec:
            continue
        new = text
        for key in ("dsr", "pbo", "sharpe", "maxdd"):
            if key in rec:
                new = _set_frontmatter_key(new, key, rec[key])
        if new != text:
            md.write_text(new, encoding="utf-8")
            updated += 1
    return updated
