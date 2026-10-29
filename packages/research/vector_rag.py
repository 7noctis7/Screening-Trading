"""RAG vectoriel génératif ancré + hybrid ontology.

Retrieval vault + vector_store + entités ontologie. Synthèse LLM citée.
Toujours grounding + guard anti-nombres.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.llm.client import Config, complete
from packages.llm.guard import guard_numbers
from packages.research.vault_rag import grounded_answer
from packages.storage.vector_store import VectorStore
from packages.storage.ontology import Ontology


def generative_answer(
    query: str,
    vault: Path | None = None,
    k: int = 4,
    cfg: Config | None = None,
    max_tokens: int = 800,
    use_hybrid: bool = True,
) -> dict:
    """Récupère (vault + vecteurs + ontologie) puis génère."""
    base = grounded_answer(query, vault=vault, k=k, max_sentences=6)
    extra = []
    if use_hybrid:
        try:
            vs = VectorStore()
            hits = vs.search(query, k=3)
            vs.close()
            extra.extend([h["text"] for h in hits])
            onto = Ontology()
            ents = onto.search_entities(query, limit=5)
            onto.close()
            extra.extend([f"{e['type']}: {e['name']}" for e in ents])
        except Exception:
            pass

    sources = base["answer"]
    if extra:
        sources += "\n\nAUTRES: " + " | ".join(extra[:4])

    if not base["grounded"] and not extra:
        return {
            "query": query,
            "grounded": False,
            "answer": base["answer"],
            "citations": base["citations"],
            "generated": False,
        }

    context = json.dumps(
        {"sources": sources, "citations": base["citations"]},
        ensure_ascii=False,
    )[:20_000]

    system = (
        "Tu es un copilote quantitatif READ-ONLY. Synthétise UNIQUEMENT à partir des SOURCES. "
        "Cite [n]. Distingue FAIT / INFÉRENCE. N'invente aucun nombre. "
        "Si insuffisant : UNCALIBRATED. Pas d'ordre ni de recommandation."
    )
    prompt = f"QUESTION:\n{query}\n\nSOURCES:\n{context}"

    result = complete(prompt, system=system, temperature=0.1, max_tokens=max_tokens, cfg=cfg)
    if not result.get("available"):
        return {
            "query": query,
            "grounded": bool(base["grounded"] or extra),
            "answer": sources,
            "citations": base["citations"],
            "generated": False,
            "reason": result.get("reason", "LLM indisponible"),
        }

    answer, violations = guard_numbers(result.get("text", ""), context, policy="reject")
    if violations:
        answer = sources
        generated = False
    else:
        generated = True

    return {
        "query": query,
        "grounded": True,
        "answer": answer,
        "citations": base["citations"],
        "generated": generated,
        "violations": violations,
    }
