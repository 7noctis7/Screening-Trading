"""Analyse read-only d'un portefeuille importé, sur historiques réels uniquement."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import sqrt
from types import SimpleNamespace

import numpy as np

from packages.data.price_loader import load_bars
from packages.portfolio.optimize import (
    equal_risk_contribution,
    hrp_weights,
    min_variance_weights,
)

MIN_OBSERVATIONS = 60


# Devises de cotation rencontrées dans les paires crypto. Triées par LONGUEUR décroissante :
# tester « USD » avant « USDC » amputerait « TRX-USDC » en « TRX-C ».
DEVISES_DE_COTATION = ("FDUSD", "USDC", "USDT", "BUSD", "USD")


def _base_crypto(clean: str) -> str:
    """Base d'une paire cotée en dollar, ou le symbole inchangé si ce n'en est pas une."""
    for devise in DEVISES_DE_COTATION:
        if clean.endswith("-" + devise):
            return clean[: -(len(devise) + 1)]
        if "-" not in clean and clean.endswith(devise) and len(clean) > len(devise):
            return clean[: -len(devise)]
    return clean


def _aliases(symbol: str) -> list[str]:
    """Variantes à essayer, dans l'ordre. `ETH`, `ETHUSDT` et `ETH/USDC` doivent tous
    mener à `ETH-USD`, le format que `data/crypto.db` stocke (cf. `scripts/ingest_crypto.py`).

    MESURÉ le 06/09 : un ticker crypto NU ne produisait que lui-même, alors que la base
    stocke `{base}-USD` — un portefeuille mixte tombait en « historique insuffisant ».
    MESURÉ le 07/09 : le correctif ne couvrait que le suffixe `USDT`. Le screening publie
    aussi des paires en USDC (`TRX/USDC`, `BTC/USDC`…) : normalisées en `TRX-USDC`, elles
    contenaient un tiret, la variante `-USD` n'était donc jamais tentée, et 7 des 15
    candidats du jour partaient en « sans historique exploitable ». La devise de cotation
    est désormais reconnue quelle qu'elle soit, séparateur ou non.

    Pour une action, l'alias nu répond en premier et `-USD` n'est jamais essayé (`_load`
    sort au premier succès) — le coût est nul là où ça marche déjà.
    """
    clean = symbol.upper().replace("/", "-")
    if clean.startswith("CASH:"):
        return [clean]
    base = _base_crypto(clean)
    if base != clean:
        return list(dict.fromkeys([clean, f"{base}-USD", base]))
    if "-" not in clean:
        return list(dict.fromkeys([clean, f"{clean}-USD"]))
    return [clean]


def _bars_crypto(symbole: str, years: int) -> list:
    """Barres depuis `data/crypto.db`, que `load_bars` ne consulte JAMAIS.

    `_price_db_path()` ne liste que `YAHOO.db`/`market.db` : la base crypto dédiée,
    alimentée par `make ingest-crypto`, est hors de son chemin de recherche. Même
    schéma que `apps/api/main.py::_company_closes`, qui lit déjà market.db PUIS
    crypto.db — on réutilise sa convention plutôt que d'en inventer une seconde."""
    try:
        from packages.data.engine import read_prices_rows
        limite = (datetime.now(UTC) - timedelta(days=365 * years)).date().isoformat()
        rows = read_prices_rows("crypto.db", symbols=[symbole]) or []
        return [SimpleNamespace(ts=str(r.get("ts") or "")[:10], close=float(r["close"]))
                for r in sorted(rows, key=lambda r: r.get("ts") or "")
                if r.get("close") and str(r.get("ts") or "")[:10] >= limite]
    except Exception:  # noqa: BLE001 — base absente ou illisible : on le dit par le vide
        return []


def _load(symbol: str, years: int) -> tuple[str | None, list]:
    """Premier alias qui rend assez de barres, en cherchant AUSSI la base crypto."""
    for alias in _aliases(symbol):
        for bars in (load_bars(alias, years=years), _bars_crypto(alias, years)):
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


ALIGNEMENT = "intersection de dates, aucun remplissage"


def _align(series: dict[str, dict[str, float]]) -> tuple[list[str], np.ndarray]:
    """Dates communes à TOUS les actifs, sans remplissage — et l'étiquette le dit.

    POURQUOI PAS DE FORWARD-FILL, alors qu'une version l'avait introduit (06/09) :
    sur un portefeuille mixte actions + crypto, la crypto cote 7 j/7 et l'action 5.
    Remplir l'action le week-end lui invente deux rendements NULS par semaine — sa
    volatilité mesurée baisse d'environ 15 %, sa corrélation à la crypto se dilue, et
    la covariance qui en sort fait paraître les actions plus sûres qu'elles ne sont.
    Un optimiseur min-variance nourri de cette matrice sur-pondère mécaniquement les
    actions. L'intersection ne coûte que les week-ends (~252 jours/an conservés) et ne
    fabrique aucun prix.

    Cette version ANNONÇAIT « aucun remplissage » tout en faisant un ffill : le champ
    `alignment` publié était faux. La constante partagée interdit désormais que le
    calcul et son étiquette divergent à nouveau.
    """
    if not series:
        return [], np.array([])
    dates = sorted(set.intersection(*(set(values) for values in series.values())))
    matrix = np.asarray([[series[symbol][date] for date in dates] for symbol in series],
                        dtype=float)
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


def _collecter(requested: list[tuple[str, float]], years: int,
               series_by_symbol: dict | None) -> tuple[dict, dict, list, list]:
    """(séries chargées, alias retenus, manquants, lignes de cash). Aucune invention :
    un symbole sans historique suffisant part en `missing`, il n'est jamais comblé."""
    loaded, aliases, missing, cash = {}, {}, [], []
    fournies = series_by_symbol or {}
    for symbol, _weight in requested:
        if symbol.startswith("CASH:"):
            cash.append(symbol)
            continue
        supplied = fournies.get(symbol) or fournies.get(symbol.replace("USDT", "/USDT"))
        if supplied and len(supplied) >= MIN_OBSERVATIONS:
            loaded[symbol], aliases[symbol] = _dated_closes(supplied), symbol
            continue
        alias, bars = _load(symbol, years)
        if alias:
            loaded[symbol], aliases[symbol] = _dated_closes(bars), alias
        else:
            missing.append(symbol)
    return loaded, aliases, missing, cash


def scenarios_risque(covariance: np.ndarray) -> dict:
    """Trois allocations calculées sur la MÊME covariance.

    `dynamique` est un HRP (Hierarchical Risk Parity), pas un Black-Litterman : BL
    exige des rendements attendus (μ) que rien ici ne calibre. Le front annonçait
    « Black-Litterman avec vues » pour une clé `hrp` que personne ne lui envoyait —
    d'où un scénario perpétuellement indisponible SOUS UN NOM QU'IL N'AURAIT PAS
    honoré de toute façon. On calcule ce qu'on sait calculer, et on le nomme ainsi.
    """
    return {"prudent": min_variance_weights(covariance),
            "neutre": equal_risk_contribution(covariance),
            "dynamique": hrp_weights(covariance)}


def charger_series(symboles: list[str], years: int = 5) -> tuple[dict, dict, list]:
    """(séries datées par symbole, alias retenus, manquants) — chargement partagé.

    Exposé pour que la recommandation d'univers réutilise EXACTEMENT ce chargement :
    mêmes alias crypto, même lecture de `crypto.db`, même seuil d'observations. Deux
    définitions concurrentes du chargement finiraient par diverger sans que rien ne le
    signale — c'est précisément ce qui avait produit la clé `hrp`/`black_litterman`.
    """
    loaded, aliases, missing, _cash = _collecter([(s, 1.0) for s in symboles], years, None)
    return loaded, aliases, missing


def covariance_annuelle(series: dict[str, dict[str, float]]) -> tuple[list[str], np.ndarray, list[str]]:
    """(symboles, covariance annualisée à 252 j, dates communes) — intersection stricte."""
    dates, prices = _align(series)
    if len(dates) < 2:
        return list(series), np.array([]), dates
    returns = prices[:, 1:] / prices[:, :-1] - 1
    return list(series), np.atleast_2d(np.cov(returns) * 252), dates


def analyze(positions: list[dict], years: int = 5, series_by_symbol: dict | None = None) -> dict:
    """Charge, aligne sans remplissage, puis mesure et optimise un portefeuille long-only."""
    requested = [(str(row["symbol"]).upper(), float(row["weight"])) for row in positions]
    loaded, aliases, missing, cash = _collecter(requested, years, series_by_symbol)
    if missing:
        return _unavailable("historique insuffisant", missing,
                            len(loaded) + len(cash), len(requested))
    if cash and not loaded:
        return _unavailable("aucun actif risqué avec historique", [], len(cash), len(requested))
    calendar = sorted(set.union(*(set(values) for values in loaded.values())))
    for symbol in cash:
        loaded[symbol], aliases[symbol] = {date: 1.0 for date in calendar}, symbol
    dates, prices = _align(loaded)
    if len(dates) < MIN_OBSERVATIONS + 1:
        return _unavailable("calendrier commun insuffisant", [], len(loaded),
                            len(requested), max(0, len(dates) - 1))
    returns = prices[:, 1:] / prices[:, :-1] - 1
    weights = np.asarray([weight for _symbol, weight in requested], dtype=float)
    weights /= weights.sum()
    covariance = np.atleast_2d(np.cov(returns) * 252)
    variance = float(weights @ covariance @ weights)
    contribution = (weights * (covariance @ weights) / variance if variance > 0
                    else np.full(len(weights), np.nan))
    with np.errstate(invalid="ignore", divide="ignore"):
        correlation = np.corrcoef(returns)
    return {"available": True, "symbols": [symbol for symbol, _ in requested],
            "aliases": aliases, "as_of": dates[-1], "start": dates[0],
            "n_observations": returns.shape[1], "frequency": "daily",
            "annualization": 252, "alignment": ALIGNEMENT,
            "metrics": _metrics(returns, weights),
            "risk_contribution": [float(v) if np.isfinite(v) else None for v in contribution],
            "correlation": _json_matrix(correlation),
            "scenarios": scenarios_risque(covariance), "coverage": 1.0}
