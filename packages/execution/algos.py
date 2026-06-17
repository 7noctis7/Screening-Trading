"""Algorithmes d'exécution — TWAP / VWAP (réduction de l'impact marché, best practice sell-side).

Découper un ordre parent en ordres enfants : **TWAP** répartit uniformément dans le temps,
**VWAP** pondère par le volume attendu (on trade plus quand le marché est liquide). Pur, testable.
"""

from __future__ import annotations


def twap_schedule(total_qty: float, slices: int = 5) -> list[float]:
    """Découpe TWAP : `slices` tranches égales (la dernière absorbe l'arrondi)."""
    if slices <= 0 or total_qty == 0:
        return []
    base = total_qty / slices
    out = [round(base, 8) for _ in range(slices - 1)]
    out.append(round(total_qty - sum(out), 8))
    return out


def vwap_schedule(total_qty: float, volume_curve: list[float]) -> list[float]:
    """Découpe VWAP : tranches proportionnelles à la courbe de volume attendue."""
    vc = [max(0.0, v) for v in (volume_curve or [])]
    tot = sum(vc)
    if total_qty == 0 or tot <= 0:
        return twap_schedule(total_qty, max(1, len(vc)))
    out = [round(total_qty * v / tot, 8) for v in vc[:-1]]
    out.append(round(total_qty - sum(out), 8))
    return out


def participation_cap(total_qty: float, adv: float, max_participation: float = 0.10) -> dict:
    """Vérifie qu'un ordre ne dépasse pas un % du volume quotidien moyen (anti-impact)."""
    cap = max(0.0, adv) * max_participation
    return {"within_cap": total_qty <= cap or adv <= 0, "cap_qty": round(cap, 4),
            "participation": round(total_qty / adv, 4) if adv > 0 else None}
