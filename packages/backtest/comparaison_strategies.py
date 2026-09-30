"""SMCLXTP-A face aux stratégies du bot, sous les MÊMES règles — et face au buy & hold.

Mêmes barres, même moteur (`signal_long_tp` : signal au close → ouverture suivante), mêmes
frais par classe, mêmes KPI. Chaque stratégie garde SES sorties : son signal de sortie
(FLAT / TP) et, pour celles du registre, le stop et la cible qu'elles fixent au close du
signal LONG.

Stratégies : `smclxtp` (réglages du Pine, 50/50, sans stop) ; `ma_crossover` (config
20/50) ; `rsi_reversion` et `swing` (réglages par défaut du dépôt). Une stratégie du
registre sans AUCUN réglage connu (ni défaut, ni config) — aujourd'hui
`institutional_price_action` — est écartée et dite UNCALIBRATED : on ne la lance jamais
avec des valeurs inventées.
"""

from __future__ import annotations

import math
from statistics import median

import numpy as np

STRATEGIES = ("smclxtp", "ma_crossover", "rsi_reversion", "swing")
FENETRE = 300                                        # barres passées vues à chaque décision
PARAMS = {"ma_crossover": {"fast": 20, "slow": 50}}  # config/strategies/ma_crossover.yaml


def non_calibrees() -> list[str]:
    """Stratégies du registre qui ne s'instancient pas sans réglages : écartées."""
    from packages.strategies import strategies
    out = []
    for nom in strategies.names():
        if nom in STRATEGIES:
            continue
        try:
            strategies.create(nom)
        except TypeError:
            out.append(nom)
    return out


def _vide(n: int) -> dict[str, np.ndarray]:
    return {"long": np.zeros(n, bool), "flat": np.zeros(n, bool),
            "stops": np.full(n, np.nan), "cibles": np.full(n, np.nan)}


def signaux(nom: str, bars: list) -> dict[str, np.ndarray]:
    """Signaux barre par barre ; à t, la stratégie ne voit que bars[t-FENETRE+1 : t+1]."""
    from packages.core.models import SignalDirection
    out = _vide(len(bars))
    if nom == "smclxtp":
        from packages.indicators.smc_lux_tp import calculer
        r = calculer([b.high for b in bars], [b.low for b in bars], [b.close for b in bars])
        out["long"], out["flat"] = r["long_signal"], r["take_profit_signal"]
        return out
    from packages.strategies import strategies
    strat = strategies.create(nom, **PARAMS.get(nom, {}))
    for t in range(len(bars)):
        for s in strat.generate_signals(bars[max(0, t - FENETRE + 1):t + 1]):
            if s.direction is SignalDirection.LONG:
                out["long"][t] = True
                out["stops"][t] = s.stop if s.stop is not None else np.nan
                out["cibles"][t] = s.target if s.target is not None else np.nan
            elif s.direction is SignalDirection.FLAT:
                out["flat"][t] = True
    return out


def _actif(bars: list, classe: str, debut: str, par_an: float) -> dict:
    from packages.backtest.signal_long_tp import kpis, simuler
    from packages.execution.costs import CostModel
    jours = [b.ts.date().isoformat() if b.timeframe == "1d" else b.ts.isoformat()
             for b in bars]
    o, h, lo, c = (np.array([getattr(b, k) for b in bars], float)
                   for k in ("open", "high", "low", "close"))
    cout = CostModel.for_asset_class(classe).round_trip_bps / 2e4
    res, bh = {}, None
    for nom in STRATEGIES:
        s = signaux(nom, bars)
        r = simuler(jours, o, c, s["long"], s["flat"], debut=debut, cout=cout, haut=h, bas=lo,
                    stops=s["stops"], cibles=s["cibles"])
        k = kpis(r, par_an)
        bh = k.pop("buy_and_hold")
        res[nom] = {**k, "motifs": _motifs(r["trades"])}
    return {**res, "buy_and_hold": bh}


def _motifs(trades: list) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in trades:
        out[t.motif_sortie] = out.get(t.motif_sortie, 0) + 1
    return out


def comparer(univers: dict, *, debut: str, classes: dict,
             par_an: float | None = None) -> dict:
    """{symbole: {stratégie: KPI, "buy_and_hold": KPI}}."""
    out = {}
    for sym, bars in univers.items():
        classe = classes.get(sym, "equity")
        ppy = par_an or (365.0 if classe == "crypto" else 252.0)
        out[sym] = _actif(bars, classe, debut, ppy)
    return out


def _med(xs: list) -> float:
    xs = [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]
    return float(median(xs)) if xs else math.nan


def synthese(res: dict) -> dict:
    """Par stratégie : médianes entre actifs (robustes à un actif hors norme), trades et
    taux de gain agrégés, et le nombre d'actifs où elle bat le buy & hold en Sharpe."""
    out = {}
    for nom in (*STRATEGIES, "buy_and_hold"):
        ks = [r[nom] for r in res.values()]
        bh = [r["buy_and_hold"] for r in res.values()]
        n = sum(k.get("trades", 0) or 0 for k in ks)
        gains = sum((k.get("win_rate") or 0) * (k.get("trades") or 0) for k in ks
                    if isinstance(k.get("win_rate"), float) and math.isfinite(k["win_rate"]))
        out[nom] = {"sharpe_median": _med([k["sharpe"] for k in ks]),
                    "sortino_median": _med([k["sortino"] for k in ks]),
                    "cagr_median": _med([k["cagr"] for k in ks]),
                    "maxdd_median": _med([k["max_drawdown"] for k in ks]),
                    "trades_total": n, "win_rate_global": gains / n if n else math.nan,
                    "bat_bh_sharpe": sum(1 for k, b in zip(ks, bh, strict=True)
                                         if k["sharpe"] > b["sharpe"])}
    return out


def tirage(candidats: list[str], k: int, graine: int) -> list[str]:
    """Tirage sans remise, reproductible, indépendant de l'ordre des candidats."""
    pool = sorted(set(candidats))
    rng = np.random.default_rng(graine)
    idx = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
    return [pool[i] for i in idx]
