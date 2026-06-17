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
_NEGATORS = {"no", "not", "never", "without", "n't"}
_TOKEN = re.compile(r"[a-zA-Z']+")


def score_text(text: str) -> float:
    """Score directionnel d'un texte court ∈ [-1, 1] (0 = neutre).

    Gère une négation simple (« not strong » → négatif). Robuste à l'entrée vide/None.
    """
    if not text:
        return 0.0
    toks = _TOKEN.findall(text.lower())
    if not toks:
        return 0.0
    s = 0
    neg = False
    for w in toks:
        if w in _NEGATORS:
            neg = True
            continue
        v = 1 if w in _POS else (-1 if w in _NEG else 0)
        if v:
            s += -v if neg else v
        neg = False
    if s == 0:
        return 0.0
    # normalisation douce : sature vite (les titres ont peu de mots porteurs)
    return max(-1.0, min(1.0, s / 3.0))


def label_of(score: float) -> str:
    """Étiquette lisible à partir d'un score ∈ [-1, 1]."""
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"
