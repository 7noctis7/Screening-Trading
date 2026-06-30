"""Text-to-filter DÉTERMINISTE — langage naturel → params → exécution par le code.

Pattern anti-hallucination (façon Fiscal.ai/function-calling) : un parseur traduit la
requête en PARAMÈTRES validés ; c'est ensuite le CODE qui filtre (jamais le LLM). Donc
zéro invention. Un LLM peut REMPLACER le parseur (mêmes params en sortie) sans changer
l'exécution. FR + EN. Aucune dépendance.
"""

from __future__ import annotations

import re

# Unités longues AVANT les courtes (sinon 'm' capture le 'm' de 'milliard').
_UNITS = {"milliard": 1e9, "milliards": 1e9, "million": 1e6, "millions": 1e6,
          "trillion": 1e12, "billion": 1e9, "mds": 1e9, "md": 1e9, "bn": 1e9,
          "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
_AMT = re.compile(
    r"(\d+[.,]?\d*)\s*"
    r"(milliards?|millions?|trillion|billion|mds|md|bn|k|m|b|t)?", re.I)


def _amount(s: str) -> float | None:
    """Extrait un montant ('1,5 milliard', '10md', '500 millions', '2B') → float."""
    m = _AMT.search(s)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    return val * _UNITS.get((m.group(2) or "").lower(), 1.0)


def _num_pct(t: str, trigger: str) -> float | None:
    m = re.search(trigger + r"[^\d]{0,8}(\d+[.,]?\d*)\s*%", t)
    return float(m.group(m.lastindex).replace(",", ".")) if m else None


def parse_query(text: str) -> dict:
    """Requête NL → filtres validés (mcap_min, chg24h_min/max, funding_*, limit)."""
    t = text.lower()
    p: dict = {}
    if re.search(r"funding\s+(n[ée]gatif|negative)", t):
        p["funding_max"] = 0.0
    if re.search(r"funding\s+(positif|positive)", t):
        p["funding_min"] = 0.0
    _cap_re = r"(tvl|cap\w*|capitalisation|market\s*cap)\D{0,12}(\d[\d.,]*\s*\w*)"
    cap = re.search(_cap_re, t)
    if cap:
        amt = _amount(cap.group(2))
        if amt:
            p["mcap_min"] = amt
    up = _num_pct(t, r"(hausse|gagnants?|monte|up|gain)")
    if up is not None:
        p["chg24h_min"] = up
    down = _num_pct(t, r"(baisse|perdants?|perte|chute|down|drop)")
    if down is not None:
        p["chg24h_max"] = -down
    elif re.search(r"\b(baisse|perdants?|perte|chute|down|rouge)\b", t):
        p["chg24h_max"] = 0.0
    if re.search(r"\b(hausse|gagnants?|vert|up)\b", t) and "chg24h_min" not in p:
        p["chg24h_min"] = 0.0
    lim = re.search(r"top\s*(\d+)", t)
    if lim:
        p["limit"] = int(lim.group(1))
    return p


def _g(r: dict, key: str, default: float) -> float:
    v = r.get(key)
    return v if v is not None else default


def apply_filter(rows: list[dict], params: dict) -> list[dict]:
    """Applique les params (déterministe) sur des coins {sym, mcap, chg24h, funding}."""
    def ok(r: dict) -> bool:
        if _g(r, "mcap", 0) < params.get("mcap_min", -1e30):
            return False
        if _g(r, "chg24h", -1e30) < params.get("chg24h_min", -1e30):
            return False
        if _g(r, "chg24h", 1e30) > params.get("chg24h_max", 1e30):
            return False
        if _g(r, "funding", 1e30) > params.get("funding_max", 1e30):
            return False
        if _g(r, "funding", -1e30) < params.get("funding_min", -1e30):
            return False
        return True

    kept = [r for r in rows if ok(r)]
    out = sorted(kept, key=lambda r: _g(r, "mcap", 0), reverse=True)
    return out[: params["limit"]] if params.get("limit") else out
