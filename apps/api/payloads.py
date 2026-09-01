"""Builders de payloads API — fonctions PURES (JSON-sérialisable), testables offline.

Le front ne contient aucune logique : il consomme ces structures. Toute la dérivation
(totaux, P&L, exposition, contributions de facteurs) est calculée ici puis testée.
"""

from __future__ import annotations

from datetime import datetime

from packages.core.models import Position, RegimeState
from packages.portfolio import integrite as _INT
from packages.portfolio import metrics as M


def regime_payload(regime: RegimeState, exposure_multiplier: float) -> dict:
    return {
        "as_of": regime.ts.isoformat(),
        "cycle": regime.cycle.value,
        "risk_mode": regime.risk_mode.value,
        "vix": regime.vix,
        "exposure_multiplier": round(exposure_multiplier, 3),
        "extras": {k: _round(v) for k, v in (regime.extras or {}).items()},
    }


def equity_series(equity_curve: list[float], timestamps: list[datetime] | None = None) -> list[dict]:
    if timestamps and len(timestamps) == len(equity_curve):
        return [{"t": ts.isoformat(), "v": round(v, 2)}
                for ts, v in zip(timestamps, equity_curve)]
    return [{"t": i, "v": round(v, 2)} for i, v in enumerate(equity_curve)]


def screener_payload(ranked: list, as_of: datetime) -> dict:
    rows = []
    for i, r in enumerate(ranked, 1):
        rows.append({
            "rank": i,
            "symbol": r.symbol,
            "asset_class": getattr(r, "asset_class", None),
            "score": round(r.score, 4),
            "factors": {k: round(v, 4) for k, v in (r.contributions or {}).items()},
            "reason": getattr(r, "reason", None),
        })
    return {"as_of": as_of.isoformat(), "count": len(rows), "rows": rows}


def composition_payload(positions: list[Position], marks: dict[str, float],
                        meta: dict[str, dict] | None = None) -> dict:
    meta = meta or {}
    rows, invested_tot, value_tot, net = [], 0.0, 0.0, 0.0
    for p in positions:
        mark = marks.get(p.instrument, p.avg_price)
        invested = p.avg_price * p.qty
        value = mark * p.qty
        sign = 1 if p.side.value == "long" else -1
        pnl = (value - invested) * sign
        m = meta.get(p.instrument, {})
        rows.append({
            "symbol": p.instrument, "side": p.side.value,
            "entry_date": m.get("entry_date"), "entry_reason": m.get("entry_reason"),
            "asset_class": m.get("asset_class"), "qty": round(p.qty, 6),
            "avg_price": round(p.avg_price, 4), "invested": round(invested, 2),
            "current_value": round(value, 2),
            "pnl_abs": round(pnl, 2),
            "pnl_pct": round(pnl / invested, 4) if invested else 0.0,
        })
        invested_tot += invested
        value_tot += value
        net += value * sign
    return {
        "rows": rows,
        "totals": {
            "invested": round(invested_tot, 2),
            "current_value": round(value_tot, 2),
            "pnl_abs": round(value_tot - invested_tot, 2),
            "pnl_pct": round((value_tot - invested_tot) / invested_tot, 4) if invested_tot else 0.0,
            "gross_exposure": round(value_tot, 2),
            "net_exposure": round(net, 2),
        },
    }


def metrics_payload(equity_curve: list[float], rets: list[float] | None = None) -> dict:
    """KPIs d'une courbe. Un point non fini TRONQUE la courbe au lieu de tout polluer.

    `M.summary` propage un NaN dans chaque ratio. Publier `sharpe: nan` est pire
    qu'une métrique absente : le front l'affiche « — » et personne ne sait qu'une
    donnée manquait. On calcule sur le préfixe valide, et on le DIT (`integrite`).
    """
    propre, diag = _INT.prefixe_fini(equity_curve)
    if diag["tronquee"]:
        _journal_integrite("metrics_payload", diag)
    s = M.summary(propre, rets or [])
    return {**{k: round(v, 4) for k, v in s.items()},
            "integrite": _INT.verdict(diag)}


def benchmark_comparison(portfolio_equity: list[float],
                         benchmarks: dict[str, list[float]]) -> dict:
    """Courbes rebasées à 100 (portefeuille vs benchmarks) pour superposition.

    TOUTES les séries sont tronquées à la MÊME longueur — celle du préfixe valide du
    portefeuille. Tronquer la seule série fautive désalignerait le graphe : les points
    ne correspondraient plus aux mêmes dates, et la comparaison deviendrait fausse tout
    en restant lisible, ce qui est le pire des cas.

    Aucune clé de diagnostic n'est ajoutée ici : le front type ce dictionnaire en
    `Record<string, Point[]>` et itère dessus. Une clé non-série y casserait le graphe.
    L'incident part au journal structuré.
    """
    propre, diag = _INT.prefixe_fini(portfolio_equity)
    if diag["tronquee"]:
        _journal_integrite("benchmark_comparison", diag)
    n = len(propre)
    out = {"portfolio": _rebase(propre)}
    for name, curve in benchmarks.items():
        c, _ = _INT.prefixe_fini(curve)
        out[name] = _rebase(c[:n])
    return out


def _journal_integrite(ou: str, diag: dict) -> None:
    """Trace structurée d'une série trouée. Best-effort : ne casse aucun snapshot."""
    try:
        import logging
        logging.getLogger("data.integrite").warning(
            "série tronquée sur point non fini",
            extra={"fonction": ou, "n": diag.get("n"),
                   "n_non_finis": diag.get("n_non_finis"),
                   "premier": diag.get("premier_non_fini"),
                   "conserves": diag.get("n_conserves")})
    except Exception:  # noqa: BLE001
        pass


def _rebase(curve: list[float]) -> list[float]:
    if not curve or curve[0] == 0:
        return [round(v, 2) for v in curve]
    base = curve[0]
    return [round(v / base * 100, 2) for v in curve]


def trade_payload(tr) -> dict:
    """TradeRecord → dict JSON-safe (dates isoformat, enums .value)."""
    def conv(v):
        if isinstance(v, datetime):
            return v.isoformat()
        if hasattr(v, "value"):          # Enum
            return v.value
        if isinstance(v, float):
            return round(v, 4)
        return v
    from dataclasses import fields
    return {f.name: conv(getattr(tr, f.name)) for f in fields(tr)}


def trade_stats_payload(trades) -> dict:
    """Statistiques agrégées sur les trades CLÔTURÉS (win rate, P&L, profit factor…)."""
    closed = [t for t in trades if getattr(t, "pnl_net", None) is not None]
    if not closed:
        return {"count": 0}
    pnls = [t.pnl_net for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    return {
        "count": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed), 4),
        "pnl_total": round(sum(pnls), 2),
        "avg_win": round(gross_win / len(wins), 2) if wins else 0.0,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "avg_pnl_pct": round(sum(t.pnl_pct or 0 for t in closed) / len(closed), 4),
        **_fragilite(wins, gross_win, gross_loss, len(closed)),
    }


def _fragilite(wins: list, gross_win: float, gross_loss: float, n: int) -> dict:
    """DEUX chiffres qui manquaient — le « pourquoi » derrière une espérance faible.

    Un profit factor de 1,01 se lit « léger avantage ». Les deux mesures ci-dessous
    disent s'il s'agit d'un avantage ou d'un hasard :

    `marge_payoff_pct` — de combien le payoff dépasse le SEUIL DE RENTABILITÉ imposé
    par le taux de réussite, soit (1 − p) / p. À 28,5 % de réussite, il faut 2,51 pour
    ne rien gagner ; réaliser 2,53 laisse 0,8 % de marge. Un payoff seul ne dit rien —
    il ne se lit que contre ce seuil.

    `n_gagnants_couvrant_les_pertes` — combien des MEILLEURS trades suffisent à couvrir
    la totalité des pertes. Si dix trades sur cinq cents y suffisent, la stratégie n'a
    pas un avantage : elle a une poignée de coups de chance, et son espérance dépend de
    leur reproduction. Choisi plutôt qu'une « part du gain NET » : avec un profit factor
    proche de 1, le net tend vers zéro et tout ratio qui le prend au dénominateur
    explose.
    """
    if not wins or gross_loss <= 0 or n <= 0:
        return {}
    p = len(wins) / n
    seuil = (1.0 - p) / p if p > 0 else float("inf")
    paye = (gross_win / len(wins)) / (gross_loss / max(1, n - len(wins)))
    tries = sorted(wins, reverse=True)
    cumul, k = 0.0, 0
    while k < len(tries) and cumul < gross_loss:
        cumul += tries[k]
        k += 1
    return {
        "payoff": round(paye, 2),
        "payoff_seuil": round(seuil, 2),
        "marge_payoff_pct": round((paye / seuil - 1.0) * 100.0, 1) if seuil else None,
        "n_gagnants_couvrant_les_pertes": k if cumul >= gross_loss else None,
        "part_top5_du_gain_brut_pct": round(sum(tries[:5]) / gross_win * 100.0, 1)
        if gross_win > 0 else None,
    }


def _round(v):
    return round(v, 4) if isinstance(v, (int, float)) else v


def correlation_payload(symbols: list[str], matrix, clusters: list[list[str]]) -> dict:
    return {"symbols": symbols,
            "matrix": [[round(float(v), 3) for v in row] for row in matrix],
            "clusters": clusters}


def review_payload(review) -> dict:
    return {"health_score": review.health_score, "strengths": review.strengths,
            "weaknesses": review.weaknesses, "risks": review.risks,
            "recommendations": review.recommendations, "disclaimer": review.disclaimer}
