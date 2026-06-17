"""Adaptateur **vectorbt** optionnel — backtest ultra-rapide depuis des signaux, repli intégré.

`vectorbt` (gratuit, MIT) vectorise des milliers de combinaisons en quelques secondes. S'il
n'est pas installé, `quick_backtest` calcule la même chose en numpy pur (long-only, plein
investissement) — donc utilisable et testable partout. On garde `fast_swing` comme moteur de
référence ; cet adaptateur sert au prototypage rapide de règles entrée/sortie.
"""

from __future__ import annotations

from collections.abc import Sequence


def vectorbt_available() -> bool:
    try:
        import vectorbt  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def quick_backtest(closes: Sequence[float], entries: Sequence[bool],
                   exits: Sequence[bool], fees: float = 0.0005) -> dict:
    """Backtest long-only depuis des signaux booléens → `{total_return, n_trades, engine}`.

    Utilise vectorbt si présent (métriques riches), sinon un moteur numpy équivalent.
    """
    closes = [float(c) for c in closes]
    entries = list(entries)
    exits = list(exits)
    if len(closes) < 2:
        return {"total_return": 0.0, "n_trades": 0, "engine": "none"}

    if vectorbt_available():
        try:
            import numpy as np
            import vectorbt as vbt
            pf = vbt.Portfolio.from_signals(
                np.asarray(closes), np.asarray(entries), np.asarray(exits), fees=fees)
            return {"total_return": float(pf.total_return()),
                    "n_trades": int(pf.trades.count()), "engine": "vectorbt"}
        except Exception:  # noqa: BLE001
            pass

    # repli numpy : position 0/1, frais à chaque bascule
    pos = 0
    equity = 1.0
    n_trades = 0
    if entries[0] and not exits[0]:        # signal d'entrée dès la 1re barre
        pos = 1
        n_trades += 1
        equity *= (1 - fees)
    for i in range(1, len(closes)):
        if pos:
            equity *= closes[i] / closes[i - 1]
        if pos and exits[i]:
            pos = 0
            equity *= (1 - fees)
        elif not pos and entries[i]:
            pos = 1
            n_trades += 1
            equity *= (1 - fees)
    return {"total_return": round(equity - 1.0, 6), "n_trades": n_trades, "engine": "numpy (repli)"}
