"""Analyse read-only d'un portefeuille importé, sur historiques réels uniquement."""
from __future__ import annotations

from math import sqrt
import numpy as np
import pandas as pd

from packages.data.price_loader import load_bars
from packages.portfolio.optimize import equal_risk_contribution, hrp_weights, min_variance_weights

MIN_OBSERVATIONS = 60


def _aliases(symbol: str) -> list[str]:
    clean = symbol.upper().replace("/", "-")
    aliases = [clean]
    if clean.endswith("USDT"):
        aliases += [f"{clean[:-4]}-USD", clean[:-4]]
    return list(dict.fromkeys(aliases))


def _load(symbol: str, years: int) -> tuple[str | None, list]:
    for alias in _aliases(symbol):
        bars = load_bars(alias, years=years)
        if len(bars) >= MIN_OBSERVATIONS:
            return alias, bars
    return None, []


def _dated_closes(bars: list) -> dict[str, float]:
    out = {}
    for bar in bars:
        date = bar.get("t") if isinstance(bar, dict) else getattr(bar, "ts", "")
        close = bar.get("c") if isinstance(bar, dict) else getattr(bar, "close", 0)
        if close and float(close) > 0:
            out[str(date)[:10]] = float(close)
    return out


def _align(series: dict[str, dict[str, float]]) -> tuple[list[str], np.ndarray]:
    if not series:
        return [], np.array([])
        
    # Création d'un DataFrame global pour aligner tous les calendriers
    df = pd.DataFrame(series)
    df = df.sort_index()
    
    # 1. Forward Fill : Remplissage des week-ends/jours fériés avec le dernier prix connu
    df = df.ffill()
    
    # 2. Dropna : Suppression des dates anciennes où l'actif le plus jeune n'existait pas encore
    df = df.dropna()
    
    dates = df.index.astype(str).tolist()
    # Transposition pour revenir au format numpy attendu (lignes = symboles, colonnes = dates)
    matrix = df.T.to_numpy(dtype=float)
    
    return dates, matrix


def _metrics(returns: np.ndarray, weights: np.ndarray) -> dict:
    portfolio = weights @ returns
    equity, downside = np.cumprod(1 + portfolio), portfolio[portfolio < 0]
    peaks = np.maximum.accumulate(equity)
    daily_vol = float(portfolio.std(ddof=1))
    sharpe = float(portfolio.mean() / daily_vol * sqrt(252)) if daily_vol else None
    down_vol = float(downside.std(ddof=1)) if downside.size > 1 else 0.0
    var = float(-np.percentile(portfolio, 5))
    tail = portfolio[portfolio <= -var]
    return {"vol_annual": daily_vol * sqrt(252), "max_drawdown": float(np.min(equity / peaks - 1)),
            "sharpe": sharpe, "sortino": float(portfolio.mean() / down_vol * sqrt(252)) if down_vol else None,
            "var_95_1d": var, "expected_shortfall_95_1d": float(-tail.mean()) if tail.size else None}


def _unavailable(reason: str, missing: list[str], loaded: int, total: int, n: int = 0) -> dict:
    return {"available": False, "reason": reason, "missing": missing, "coverage": loaded / total if total else 0,
            "n_observations": n, "min_observations": MIN_OBSERVATIONS}


def _json_matrix(matrix: np.ndarray) -> list[list[float | None]]:
    return [[float(value) if np.isfinite(value) else None for value in row] for row in np.atleast_2d(matrix)]


def analyze(positions: list[dict], years: int = 5, series_by_symbol: dict | None = None) -> dict:
    """Charge, aligne avec ffill, puis mesure et optimise un portefeuille long-only."""
    requested = [(str(row["symbol"]).upper(), float(row["weight"])) for row in positions]
    loaded, aliases, missing, cash = {}, {}, [], []
    
    for symbol, _weight in requested:
        if symbol.startswith("CASH:"):
            cash.append(symbol)
            continue
        supplied = (series_by_symbol or {}).get(symbol) or (series_by_symbol or {}).get(symbol.replace("USDT", "/USDT"))
        if supplied and len(supplied) >= MIN_OBSERVATIONS:
            loaded[symbol], aliases[symbol] = _dated_closes(supplied), symbol
            continue
        alias, bars = _load(symbol, years)
        if alias:
            loaded[symbol], aliases[symbol] = _dated_closes(bars), alias
        else:
            missing.append(symbol)
            
    if missing:
        return _unavailable("historique insuffisant", missing, len(loaded) + len(cash), len(requested))
    if cash and not loaded:
        return _unavailable("aucun actif risqué avec historique", [], len(cash), len(requested))
        
    calendar = sorted(set.union(*(set(values) for values in loaded.values())))
    for symbol in cash:
        loaded[symbol], aliases[symbol] = {date: 1.0 for date in calendar}, symbol
        
    dates, prices = _align(loaded)
    
    if len(dates) < MIN_OBSERVATIONS + 1:
        return _unavailable("calendrier commun insuffisant", [], len(loaded), len(requested), max(0, len(dates) - 1))
        
    returns = prices[:, 1:] / prices[:, :-1] - 1
    weights = np.asarray([weight for _symbol, weight in requested], dtype=float)
    weights /= weights.sum()
    
    try:
        # Base de covariance annualisée (mixte actions/cryptos)
        covariance = np.atleast_2d(np.cov(returns) * 252)
        variance = float(weights @ covariance @ weights)
        contribution = weights * (covariance @ weights) / variance if variance > 0 else np.full(len(weights), np.nan)
        
        with np.errstate(invalid="ignore", divide="ignore"):
            correlation = np.corrcoef(returns)
            
        try:
            scenarios_dict = {
                "prudent": min_variance_weights(covariance),
                "neutre": equal_risk_contribution(covariance),
                "dynamique": hrp_weights(covariance)
            }
        except Exception:
            n_assets = len(requested)
            eq_w = [1.0 / n_assets] * n_assets
            scenarios_dict = {"prudent": eq_w, "neutre": eq_w, "dynamique": eq_w}

        return {
            "available": True, 
            "symbols": [symbol for symbol, _ in requested], 
            "aliases": aliases,
            "as_of": dates[-1], 
            "start": dates[0], 
            "n_observations": returns.shape[1], 
            "frequency": "daily",
            "annualization": 252, 
            "alignment": "forward-fill (week-ends) puis intersection",
            "metrics": _metrics(returns, weights),
            "risk_contribution": [float(value) if np.isfinite(value) else None for value in contribution],
            "correlation": _json_matrix(correlation), 
            "scenarios": scenarios_dict, 
            "coverage": 1.0
        }
    except Exception as e:
        return _unavailable(f"Erreur critique de calcul: {str(e)}", [], len(loaded), len(requested))
