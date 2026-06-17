"""Note technique 0-100 — synthèse tendance / momentum / RSI / distance aux moyennes.

Combine des signaux techniques classiques en une note unique (haut = configuration haussière),
pour la croiser avec la note fondamentale. stdlib pur, robuste aux séries courtes.
"""

from __future__ import annotations


def _sma(c: list[float], p: int) -> float | None:
    return sum(c[-p:]) / p if len(c) >= p else None


def _rsi(c: list[float], p: int = 14) -> float:
    if len(c) <= p:
        return 50.0
    gains = losses = 0.0
    for i in range(1, p + 1):
        d = c[-i] - c[-i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / p) / (losses / p)
    return 100.0 - 100.0 / (1.0 + rs)


def technical_rating(closes: list[float]) -> dict:
    """Note technique ∈ [0, 100] + libellé. 4 composantes égales (25 pts chacune)."""
    c = [float(x) for x in closes if x == x]
    if len(c) < 30:
        return {"score": 50, "label": "neutre", "available": False}
    px = c[-1]
    sma50, sma200 = _sma(c, 50), _sma(c, 200)
    rsi = _rsi(c)
    mom = c[-1] / c[-63] - 1 if len(c) > 63 else 0.0
    pts = 0.0
    pts += 25 if (sma50 and px > sma50) else 0          # au-dessus de la MM50
    pts += 25 if (sma200 and px > sma200) else 0        # au-dessus de la MM200 (tendance LT)
    pts += 25 * max(0.0, min(1.0, (mom + 0.2) / 0.4))   # momentum 63 j borné [-20%,+20%]
    pts += 25 * max(0.0, min(1.0, (rsi - 30) / 40))     # RSI 30→70 mappé 0→25
    score = round(pts)
    label = "haussier" if score >= 66 else ("baissier" if score <= 33 else "neutre")
    return {"score": score, "label": label, "rsi": round(rsi, 1),
            "above_sma200": bool(sma200 and px > sma200), "available": True}
