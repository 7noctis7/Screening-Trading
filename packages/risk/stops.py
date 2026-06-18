"""Sorties CONVEXES (Taleb : des barrières statiques sont fragiles et manipulables).

Les stops/targets ne sont pas des prix fixes mais des fonctions de la **volatilité** (ATR) ET de
la **volatilité textuelle implicite** (intensité/incertitude des news) : on élargit le stop quand
l'incertitude monte (pour ne pas se faire sortir par le bruit), on réduit la taille en parallèle.
Asymétrie : take-profit plus lointain que le stop (convexité : petites pertes, gros gains).
"""

from __future__ import annotations


def convex_stops(price: float, atr: float, k_stop: float = 2.0, rr: float = 3.0,
                 text_vol: float = 0.0, side: str = "long") -> dict:
    """Stop/target adaptatifs à la vol prix (ATR) et à la vol textuelle.

    Args:
        price: prix d'entrée.
        atr: Average True Range (vol prix absolue).
        k_stop: multiple d'ATR pour le stop (élargi par la vol textuelle).
        rr: ratio rendement/risque (target = rr × distance de stop) → convexité.
        text_vol: volatilité textuelle implicite ∈ [0,1] (intensité/incertitude des news).
        side: "long" ou "short".
    Renvoie `{stop, target, stop_dist, widen_factor}`.
    """
    widen = 1.0 + max(0.0, min(1.0, text_vol))        # +100 % de marge au pic d'incertitude news
    stop_dist = k_stop * max(0.0, atr) * widen
    tgt_dist = rr * stop_dist
    if side == "short":
        return {"stop": price + stop_dist, "target": price - tgt_dist,
                "stop_dist": stop_dist, "widen_factor": round(widen, 3)}
    return {"stop": price - stop_dist, "target": price + tgt_dist,
            "stop_dist": stop_dist, "widen_factor": round(widen, 3)}


def vol_scaled_size(base_weight: float, atr_pct: float, target_vol: float = 0.02,
                    text_vol: float = 0.0, max_weight: float = 0.20) -> float:
    """Taille de position ∝ vol-cible / vol réalisée, RÉDUITE quand la vol textuelle monte.

    Convexité défensive : plus le stop s'élargit (incertitude), plus la taille diminue → la perte
    maximale par trade (taille × distance de stop) reste bornée. size = w·(tgt/atr)/(1+text_vol).
    """
    if atr_pct <= 0:
        return 0.0
    raw = base_weight * (target_vol / atr_pct) / (1.0 + max(0.0, text_vol))
    return max(0.0, min(max_weight, raw))
