"""RAG ancré sur le vault — réponse EXTRACTIVE citée (zéro hallucination).

Philosophie (façon Fiscal.ai, mais déterministe) : on ne *génère* rien. On RÉCUPÈRE
les sections les plus pertinentes (TF-IDF/Ollama via vault_search) puis on
ASSEMBLE une réponse uniquement à partir de phrases sources VERBATIM, chacune suivie
d'une citation [n] → fichier › section. Si rien de pertinent : on le dit (0 invention).

Un LLM (Claude/Ollama) peut ensuite *synthétiser* depuis ces spans ancrés, mais le
grounding (citations vérifiables) est le livrable — c'est ça qui interdit l'hallu.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load_search():
    """Charge scripts/vault_search.py (hors package) sans effet de bord."""
    spec = importlib.util.spec_from_file_location(
        "vault_search", _ROOT / "scripts" / "vault_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sentences(text: str) -> list[str]:
    """Découpe en phrases/puces (granularité de citation)."""
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip(" -•*\t")
        if not line:
            continue
        for s in re.split(r"(?<=[.!?])\s+", line):
            s = s.strip()
            if len(s) > 8:
                out.append(s)
    return out


def grounded_answer(query: str, vault: Path | None = None, k: int = 4,
                    max_sentences: int = 6) -> dict:
    """Réponse extractive citée. {query, grounded, answer, citations}.

    `answer` = phrases sources verbatim avec marqueurs [n] ; `citations` mappe
    [n] → {file, heading, score}. grounded=False si aucune source pertinente.
    """
    vs = _load_search()
    vault = vault or (_ROOT / "vault")
    hits = vs.search(query, Path(vault), k=k)
    if not hits:
        return {"query": query, "grounded": False,
                "answer": "Aucune source pertinente dans le vault.", "citations": []}

    qset = set(vs._tokens(query))
    scored: list[tuple[float, int, str]] = []          # (pertinence, idx_src, phrase)
    for i, h in enumerate(hits):
        for sent in _sentences(h["text"]):
            toks = set(vs._tokens(sent))
            if not toks:
                continue
            overlap = len(qset & toks) / (len(qset) or 1)
            if overlap > 0:
                scored.append((overlap * h["score"], i, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    picks = scored[:max_sentences]
    if not picks:
        return {"query": query, "grounded": False,
                "answer": "Sources trouvées mais aucune phrase ne répond directement.",
                "citations": [{"n": i + 1, "file": h["file"], "heading": h["heading"],
                               "score": h["score"]} for i, h in enumerate(hits)]}

    used = sorted({i for _, i, _ in picks})
    remap = {old: new + 1 for new, old in enumerate(used)}   # renumérote [1..]
    lines = [f"{sent} [{remap[i]}]" for _, i, sent in picks]
    citations = [{"n": remap[i], "file": hits[i]["file"],
                  "heading": hits[i]["heading"], "score": hits[i]["score"]}
                 for i in used]
    return {"query": query, "grounded": True, "answer": " ".join(lines),
            "citations": citations}
