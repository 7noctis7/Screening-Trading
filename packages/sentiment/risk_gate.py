"""Garde-fou SÉMANTIQUE (Taleb : éviter la ruine par mauvaise interprétation NLP).

Un signal NLP n'agit sur le capital que (1) s'il est CONFIANT, (2) s'il est CORROBORÉ par
plusieurs sources, (3) de façon BORNÉE et ASYMÉTRIQUE (on coupe vite sur signal négatif fiable,
on n'ajoute que prudemment sur signal positif). Aucune position binaire « tout ou rien » sur une
phrase. Équations explicites, numpy non requis.

Impact ∈ [-cap_neg, +cap_pos] :
    raw      = score · confidence
    corrob   = min(1, n_sources / k_required)            # corroboration multi-sources
    gated    = raw · corrob · 1{confidence ≥ conf_min}
    impact   = clip(gated, -cap_neg, +cap_pos)           # asymétrie : cap_neg ≥ cap_pos
"""

from __future__ import annotations


def semantic_gate(score: float, confidence: float, n_sources: int = 1,
                  conf_min: float = 0.35, k_required: int = 3,
                  cap_pos: float = 0.05, cap_neg: float = 0.10) -> dict:
    """Convertit (score, confiance) NLP en IMPACT borné et asymétrique sur l'exposition.

    cap_pos < cap_neg : on laisse le négatif réduire plus fort qu'il ne laisse le positif ajouter
    (convexité défensive : se tromper en restant petit coûte peu, se tromper en grand ruine).
    """
    conf = max(0.0, min(1.0, confidence))
    corrob = min(1.0, max(0, n_sources) / max(1, k_required))
    raw = score * conf * corrob
    if conf < conf_min:                       # interprétation trop ambiguë → aucun impact
        raw = 0.0
    impact = max(-abs(cap_neg), min(abs(cap_pos), raw))
    blocked = conf < conf_min or corrob < 1.0
    return {"impact": round(impact, 4), "raw": round(score * conf * corrob, 4),
            "corroboration": round(corrob, 3), "confidence": round(conf, 3),
            "blocked": blocked,
            "reason": ("confiance insuffisante" if conf < conf_min else
                       "corroboration incomplète (réduit)" if corrob < 1.0 else "ok")}


def aggregate_with_confidence(items: list[dict]) -> dict:
    """Agrège des `score_detail` en pondérant par la CONFIANCE (les titres ambigus pèsent moins)."""
    rows = [i for i in items if i.get("n_terms")]
    if not rows:
        return {"score": 0.0, "confidence": 0.0, "n": 0}
    wsum = sum(i["confidence"] for i in rows) or 1.0
    score = sum(i["score"] * i["confidence"] for i in rows) / wsum
    conf = sum(i["confidence"] for i in rows) / len(rows)
    return {"score": round(score, 4), "confidence": round(conf, 3), "n": len(rows)}
