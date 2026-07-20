"""Delta de biais du survivant (audit 07/17, XL-1) — chiffre l'optimisme du backtest.

`preset_backtest` ne voit que les titres ENCORE cotés (`data.items()`) → Sharpe/DD
optimistes (les délistés/faillis ont disparu). Ici on relance le MÊME preset sur deux
univers — survivants seuls vs survivants + délistés — et on publie l'écart. C'est la
mesure honnête que l'audit exige AVANT de croire un backtest long.

Dépendance dure : les délistés doivent avoir leur OHLCV en base (`make ingest-delisted`).
Sans leurs prix, `delisted_data` est vide → delta indisponible (jamais inventé). numpy pur.
"""

from __future__ import annotations

from packages.backtest.preset_backtest import preset_backtest


def survivorship_delta(survivor_data: dict, delisted_data: dict | None = None,
                       **preset_kw) -> dict:
    """Compare le preset SANS vs AVEC les délistés. Renvoie l'écart de Sharpe/CAGR/maxDD.

    Args:
        survivor_data: {symbol: [Bar,…]} des titres encore cotés (univers courant).
        delisted_data: {symbol: [Bar,…]} des titres délistés AVEC prix (sinon None/{}).
        preset_kw: mêmes paramètres passés aux deux backtests (comparaison apples-to-apples).

    Returns:
        {available, corrected, n_survivors, n_delisted, with_survivors_only,
         with_delisted, delta:{sharpe, cagr, max_drawdown}} — ou available=False si
         les données délistées manquent (leurs prix ne sont pas en base).
    """
    base = preset_backtest(survivor_data, **preset_kw)
    if not base.get("available"):
        return {"available": False, "reason": "backtest survivants indisponible"}
    if not delisted_data:
        return {
            "available": False,
            "reason": "aucun prix de délisté en base — lancer `make ingest-delisted` "
                      "puis relancer (delisted.csv ne contient que noms+dates, pas l'OHLCV)",
            "n_survivors": len(survivor_data),
            "with_survivors_only": base.get("preset"),
        }
    merged = {**survivor_data, **delisted_data}
    full = preset_backtest(merged, **preset_kw)
    if not full.get("available"):
        return {"available": False, "reason": "backtest avec délistés indisponible"}

    def _d(key: str, sub: str = "preset") -> float:
        a = (full.get(sub) or {}).get(key, 0.0)
        b = (base.get(sub) or {}).get(key, 0.0)
        return round(float(a) - float(b), 4)

    return {
        "available": True,
        "corrected": True,
        "n_survivors": len(survivor_data),
        "n_delisted": len(delisted_data),
        "with_survivors_only": base.get("preset"),
        "with_delisted": full.get("preset"),
        "delta": {"sharpe": _d("sharpe"), "annualized": _d("annualized"),
                  "max_drawdown": _d("max_drawdown"), "total_return": _d("total_return")},
        "note": ("Écart survivants-seuls → +délistés. Un Sharpe qui CHUTE avec les "
                 "délistés = le backtest survivant était optimiste (attendu). À publier "
                 "sur /echecs comme mesure d'honnêteté du backtest long."),
    }
