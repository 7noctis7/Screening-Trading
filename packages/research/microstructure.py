"""Microstructure crypto — OFI (Order Flow Imbalance) + vPIN (toxicité du flux).

POC gratuit : se nourrit d'un carnet L2 + trades (WebSocket/REST exchange, sans clé).
Fonctions PURES (testables hors-ligne) ; la capture réseau est dans le CLI dédié.
Comme tout signal ici : à passer au GATE (placebo/DSR/PBO/sabotage) avant tout câblage.

Références : Cont-Kukanov-Stoikov (OFI) ; Easley-López de Prado-O'Hara (vPIN, BVC).
"""

from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def ofi_event(pb: float, qb: float, pa: float, qa: float,
              pb0: float, qb0: float, pa0: float, qa0: float) -> float:
    """Order Flow Imbalance d'UN update L2 (meilleures limites t-1 → t).

    >0 = pression acheteuse nette. (Cont, Kukanov, Stoikov, 2014.)
    """
    if pb > pb0:
        db = qb
    elif pb == pb0:
        db = qb - qb0
    else:
        db = -qb0
    if pa < pa0:
        da = qa
    elif pa == pa0:
        da = qa - qa0
    else:
        da = -qa0
    return db - da


def ofi_series(book: list[tuple[float, float, float, float]]) -> float:
    """OFI cumulé sur une fenêtre. `book` = [(pb, qb, pa, qa), …] chronologique."""
    total = 0.0
    for i in range(1, len(book)):
        pb, qb, pa, qa = book[i]
        pb0, qb0, pa0, qa0 = book[i - 1]
        total += ofi_event(pb, qb, pa, qa, pb0, qb0, pa0, qa0)
    return total


def bulk_buy_fraction(dp: float, sigma: float) -> float:
    """Bulk Volume Classification : part ACHETEUR d'un bucket = Φ(Δprix / σ)."""
    if sigma <= 0:
        return 0.5
    return _norm_cdf(dp / sigma)


def vpin(prices: list[float], volumes: list[float], bucket: float,
         n_buckets: int = 50) -> dict:
    """vPIN = toxicité du flux (probabilité de trading informé synchronisée au volume).

    Trades chronologiques (prix, volume) → buckets de volume `bucket` → par bucket
    V_buy = Σ vᵢ·Φ(Δpᵢ/σ), V_sell = V−V_buy → vPIN = moyenne |V_buy−V_sell|/V sur les
    `n_buckets` derniers. vPIN ↑ = flux toxique (souvent avant un choc de volatilité).
    """
    if len(prices) < 3 or bucket <= 0:
        return {"available": False}
    dps = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    mean = sum(dps) / len(dps)
    var = sum((d - mean) ** 2 for d in dps) / max(1, len(dps) - 1)
    sigma = math.sqrt(var)
    buckets: list[tuple[float, float]] = []          # (V_buy, V_sell)
    cv = bv = sv = 0.0
    for i in range(1, len(prices)):
        frac = bulk_buy_fraction(dps[i - 1], sigma)
        v = volumes[i]
        bv += v * frac
        sv += v * (1 - frac)
        cv += v
        while cv >= bucket:                          # clôt un bucket plein
            buckets.append((bv, sv))
            bv = sv = 0.0
            cv -= bucket
    if not buckets:
        return {"available": False, "reason": "volume insuffisant"}
    last = buckets[-n_buckets:]
    val = sum(abs(b - s) for b, s in last) / (len(last) * bucket)
    return {"available": True, "vpin": round(val, 4), "n_buckets": len(last),
            "sigma_dp": round(sigma, 6)}
