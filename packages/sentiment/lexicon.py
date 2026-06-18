"""Scoreur de sentiment financier **lexical** — stdlib pure, déterministe, hors-ligne.

Sert de socle toujours disponible : aucune dépendance, aucun réseau. FinBERT (optionnel)
prend le relais s'il est installé (cf. `finbert.py`). Inspiré du lexique Loughran-McDonald
(finance) réduit à l'essentiel — suffisant pour un signal directionnel sur des titres courts.
"""

from __future__ import annotations

import re

# Lexique finance condensé (poids 1.0 par défaut). Minuscule, sans ponctuation.
_POS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies", "gain", "gains",
    "jump", "jumps", "record", "upgrade", "upgraded", "outperform", "bullish", "growth",
    "profit", "profits", "strong", "boost", "boosted", "rise", "rises", "rose", "top", "tops",
    "exceed", "exceeds", "win", "wins", "approval", "approved", "expansion", "buyback",
    "dividend", "raise", "raised", "optimistic", "momentum", "breakout", "rebound",
}
_NEG = {
    "miss", "misses", "missed", "plunge", "plunges", "slump", "slumps", "fall", "falls", "fell",
    "drop", "drops", "crash", "crashes", "downgrade", "downgraded", "underperform", "bearish",
    "loss", "losses", "weak", "warning", "warns", "cut", "cuts", "decline", "declines",
    "lawsuit", "probe", "bankruptcy", "default", "recession", "fraud", "selloff", "sell-off",
    "layoff", "layoffs", "fear", "fears", "risk", "risks", "slowdown", "deficit", "concern",
}
_NEGATORS = {"no", "not", "never", "without", "n't", "nt", "neither", "nor", "hardly", "barely"}
_CONTRAST = {"but", "however", "despite", "although", "though", "yet", "nonetheless"}
_HEDGES = {"may", "might", "could", "possibly", "uncertain", "unclear", "rumor", "rumour",
           "reportedly", "allegedly", "expected", "forecast"}
_TOKEN = re.compile(r"[a-zA-Z']+")
_NEG_WINDOW = 3            # portée de la négation (mots suivants) → gère « not a bad surprise »


def score_text(text: str) -> float:
    """Score directionnel d'un texte court ∈ [-1, 1] (0 = neutre). Voir `score_detail`."""
    return score_detail(text)["score"]


def score_detail(text: str) -> dict:
    """Score + CONFIANCE (Taleb : une interprétation ambiguë ne doit pas piloter le capital).

    - Négation à PORTÉE (fenêtre de 3 mots, ne se réinitialise pas sur les mots neutres) →
      « ce rapport n'est pas une mauvaise surprise » est correctement lu comme positif.
    - `confidence` ∈ [0,1] baisse si peu de termes porteurs, si contraste (sarcasme/mais) ou hedging.
    Renvoie `{score, confidence, n_terms, negated, contrast, hedged}`.
    """
    if not text:
        return {"score": 0.0, "confidence": 0.0, "n_terms": 0,
                "negated": False, "contrast": False, "hedged": False}
    toks = _TOKEN.findall(text.lower())
    if not toks:
        return {"score": 0.0, "confidence": 0.0, "n_terms": 0,
                "negated": False, "contrast": False, "hedged": False}
    s = 0.0
    n_terms = neg_used = 0
    neg_countdown = 0
    contrast = any(w in _CONTRAST for w in toks)
    hedged = any(w in _HEDGES for w in toks)
    for w in toks:
        if w in _NEGATORS:
            neg_countdown = _NEG_WINDOW            # active la négation sur les N mots suivants
            continue
        v = 1 if w in _POS else (-1 if w in _NEG else 0)
        if v:
            n_terms += 1
            if neg_countdown > 0:
                v = -v; neg_used += 1
            s += v
        if neg_countdown > 0:
            neg_countdown -= 1
    if n_terms == 0:
        return {"score": 0.0, "confidence": 0.0, "n_terms": 0,
                "negated": False, "contrast": contrast, "hedged": hedged}
    score = max(-1.0, min(1.0, s / 3.0))
    # confiance : monte avec le nb de termes, chute si contraste/hedging (ambiguïté sémantique)
    conf = min(1.0, n_terms / 3.0)
    if contrast:
        conf *= 0.5
    if hedged:
        conf *= 0.6
    return {"score": round(score, 4), "confidence": round(conf, 3), "n_terms": n_terms,
            "negated": neg_used > 0, "contrast": contrast, "hedged": hedged}


def label_of(score: float) -> str:
    """Étiquette lisible à partir d'un score ∈ [-1, 1]."""
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"
