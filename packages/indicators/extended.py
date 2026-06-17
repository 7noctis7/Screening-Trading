"""Pont **pandas-ta** optionnel (~150 indicateurs) avec repli sur nos indicateurs maison.

Philosophie « ajouter un fichier, jamais toucher au cœur » : si `pandas-ta` est installé on en
profite, sinon on retombe sur `packages.indicators` (numpy pur, déjà testé). Aucun import lourd
tant que ce n'est pas appelé → testable sans pandas/pandas-ta.
"""

from __future__ import annotations

from collections.abc import Sequence


def pandas_ta_available() -> bool:
    try:
        import pandas_ta  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def rsi(closes: Sequence[float], period: int = 14) -> float:
    """RSI du dernier point. pandas-ta si dispo, sinon implémentation maison (Wilder)."""
    closes = list(closes)
    if pandas_ta_available() and len(closes) > period:
        try:
            import pandas as pd
            import pandas_ta as ta
            s = ta.rsi(pd.Series(closes), length=period)
            if s is not None and len(s.dropna()):
                return float(s.dropna().iloc[-1])
        except Exception:  # noqa: BLE001
            pass
    # repli maison (Wilder)
    if len(closes) <= period:
        return 50.0
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[-i] - closes[-i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


def list_indicators() -> list[str]:
    """Noms d'indicateurs disponibles via pandas-ta (vide si non installé)."""
    if not pandas_ta_available():
        return []
    try:
        import pandas_ta as ta
        return sorted(getattr(ta, "Category", {}).get("momentum", []))  # un échantillon utile
    except Exception:  # noqa: BLE001
        return []
