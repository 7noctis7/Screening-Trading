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


def deflation_params(path: str | Path = DEFAULT_PATH,
                     min_trials: int = 1) -> tuple[int, float | None]:
    """(N, sr_std) pour déflater le DSR sur TOUT le programme de recherche.

    `sr_std` doit être exprimé dans la MÊME PÉRIODICITÉ que le Sharpe passé au DSR
    (les appelants passent un Sharpe PAR PÉRIODE). Or les scripts historiques
    enregistrent au ledger un Sharpe **annualisé** : les mélanger plaçait le seuil à
    ~1,72 par barre, soit un Sharpe annualisé de **27** en quotidien — inatteignable
    par construction, donc un DSR jamais franchissable dès que le ledger contenait
    deux Sharpes. C'était un artefact d'unités, pas un verdict de marché
    (audit 2026-08-20, ADR à écrire).

    Règle désormais : n'entrent dans `sr_std` que les enregistrements dont la
    périodicité est CONNUE — `sharpe_period` explicite, ou `sharpe` accompagné de
    `periods_per_year`. Les autres sont **exclus**, jamais devinés. Moins de deux
    utilisables ⇒ None ⇒ le DSR replie sur √(1/n) (hypothèse H0 de Bailey-LdP), qui
    est falsifiable.

    `N` (nombre d'essais) reste compté sur TOUS les facteurs distincts : la déflation
    par le multiple testing ne dépend pas, elle, de la périodicité.
    """
    recs = read_records(path)
    by_facteur: dict[str, float] = {}
    distinct: set[str] = set()
    ignores = 0
    for r in recs:
        f = r.get("facteur")
        if not f:
            continue
        distinct.add(f)
        sp = r.get("sharpe_period")
        if isinstance(sp, (int, float)):
            by_facteur[f] = float(sp)
            continue
        ppy, sh = r.get("periods_per_year"), r.get("sharpe")
        if isinstance(ppy, (int, float)) and ppy > 0 and isinstance(sh, (int, float)):
            by_facteur[f] = float(sh) / float(ppy) ** 0.5
        elif isinstance(sh, (int, float)):
            ignores += 1                      # périodicité inconnue → EXCLU, jamais deviné
    n = max(min_trials, len(distinct) or len(recs))
    sharpes = list(by_facteur.values())
    if len(sharpes) < 2:
        return n, None
    mean = sum(sharpes) / len(sharpes)
    var = sum((s - mean) ** 2 for s in sharpes) / (len(sharpes) - 1)
    return n, max(1e-6, var ** 0.5)


def deflation_diagnostic(path: str | Path = DEFAULT_PATH) -> dict:
    """Pourquoi le seuil du DSR vaut ce qu'il vaut — rend la déflation auditable."""
    recs = read_records(path)
    connus, inconnus = 0, 0
    for r in recs:
        if not r.get("facteur"):
            continue
        if isinstance(r.get("sharpe_period"), (int, float)) or (
                isinstance(r.get("periods_per_year"), (int, float))
                and isinstance(r.get("sharpe"), (int, float))):
            connus += 1
        elif isinstance(r.get("sharpe"), (int, float)):
            inconnus += 1
    n, sr_std = deflation_params(path)
    return {"n_trials": n, "sr_std": sr_std,
            "records_periodicite_connue": connus,
            "records_exclus_periodicite_inconnue": inconnus,
            "repli_bailey": sr_std is None,
            "note": ("sr_std mesuré sur les essais à périodicité connue"
                     if sr_std is not None else
                     "moins de 2 essais à périodicité connue → repli √(1/n) (Bailey-LdP)")}


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
