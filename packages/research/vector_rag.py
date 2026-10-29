"""RAG vectoriel génératif ancré — retrieval (TF-IDF ou Ollama) + synthèse LLM citée.

Réutilise vault_search (embeddings optionnels) et packages.llm.client.
Toujours grounding + guard anti-nombres. Zéro invention de chiffres.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.llm.client import Config, complete
from packages.llm.guard import guard_numbers
from packages.research.vault_rag import grounded_answer


def generative_answer(
    query: str,
    vault: Path | None = None,
    k: int = 4,
    cfg: Config | None = None,
    max_tokens: int = 800,
) -> dict:
    """Récupère puis génère une synthèse ancrée sur les sources."""
    base = grounded_answer(query, vault=vault, k=k, max_sentences=8)
    if not base["grounded"]:
        return {
            "query": query,
            "grounded": False,
            "answer": base["answer"],
            "citations": base["citations"],
            "generated": False,
        }

    context = json.dumps(
        {"sources": base["answer"], "citations": base["citations"]},
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
            "grounded": True,
            "answer": base["answer"],  # repli extractif
            "citations": base["citations"],
            "generated": False,
            "reason": result.get("reason", "LLM indisponible"),
        }

    answer, violations = guard_numbers(result.get("text", ""), context, policy="reject")
    if violations:
        answer = base["answer"]  # repli sécurisé
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
