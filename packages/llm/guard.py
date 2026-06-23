"""Garde anti-hallucination chiffrée pour sorties LLM (alignement, 0 dépendance).

Principe : un LLM *narre*, il ne *calcule jamais*. Tout nombre « significatif » du texte
généré mais ABSENT du contexte fourni est une hallucination → neutralisé (redact) ou
rejet total (reject). On ignore les petits entiers d'énumération (« 3 phrases ») pour
limiter les faux positifs : seuls %, décimaux et valeurs ≥ 10 sont contrôlés.
"""

from __future__ import annotations

import re

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?%?")


def _to_float(token: str) -> float:
    return float(token.rstrip("%").replace(",", "."))


def _significant(token: str, value: float) -> bool:
    """Contrôlé si % OU décimal OU |valeur| >= 10 (petits entiers ignorés)."""
    return token.endswith("%") or ("." in token or "," in token) or abs(value) >= 10.0


def allowed_values(context: str) -> set[float]:
    """Valeurs numériques autorisées (arrondies) extraites du contexte fourni au LLM."""
    out: set[float] = set()
    for tok in _NUM.findall(context):
        try:
            out.add(round(_to_float(tok), 4))
        except ValueError:
            continue
    return out


def _matches_allowed(value: float, allowed: set[float], tol: float) -> bool:
    """Tolère le reformatage (12.34 → 12.3) : match si écart absolu OU relatif ≤ tol."""
    for a in allowed:
        if abs(value - a) <= tol or abs(value - a) <= tol * max(abs(a), 1.0):
            return True
    return False


def guard_numbers(
    text: str, context: str, tol: float = 0.05, policy: str = "redact",
) -> tuple[str, list[str]]:
    """Contrôle les nombres de `text` contre ceux de `context`.

    Retourne `(texte_nettoyé, violations)`. `redact` remplace chaque nombre fabriqué
    par `[n.d.]` ; `reject` renvoie `("", violations)` dès la 1re violation (le caller
    bascule alors sur son repli déterministe).
    """
    allowed = allowed_values(context)
    violations: list[str] = []

    def _repl(m: re.Match) -> str:
        tok = m.group(0)
        try:
            val = _to_float(tok)
        except ValueError:
            return tok
        if not _significant(tok, val):
            return tok
        if _matches_allowed(val, allowed, tol):
            return tok
        violations.append(tok)
        return "[n.d.]"

    cleaned = _NUM.sub(_repl, text)
    if policy == "reject" and violations:
        return "", violations
    return cleaned, violations
