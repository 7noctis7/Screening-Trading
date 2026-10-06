"""Cotations bid / ask / mid d'un passage — pour MESURER le coût, jamais décider.

POURQUOI (audit E[Gain], 06/10, constat F6). Le « slippage » journalisé comparait le
prix de fill au DERNIER CLOSE connu : il mêlait le gap de nuit, la dérive intraday et le
vrai coût d'exécution, et le spread n'était jamais capté. Les colonnes du journal
existaient (mid à l'arrivée, bid au fill…) ; rien ne les remplissait.

Ce module lit la dernière cotation (Alpaca, actions et crypto) et la rend sous une forme
validée. Il ne lève JAMAIS : une cotation illisible vaut « absente » (None), et un
passage d'ordres ne doit pas dépendre d'une mesure. Aucune donnée n'est inventée : un
bid ≤ 0, un ask < bid ou un symbole muet sont écartés, pas corrigés.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from datetime import UTC, datetime

# lecteur(symboles) → {symbole: (bid, ask, horodatage ISO ou "")}
Lecteur = Callable[[list[str]], dict[str, tuple[float, float, str]]]


def valider(bid, ask, ts: str = "") -> dict | None:
    """{bid, ask, mid, spread_bps, ts} si la cotation est cohérente, sinon None."""
    try:
        b, a = float(bid), float(ask)
    except (TypeError, ValueError):
        return None
    if not (b > 0 and a > 0 and a >= b):
        return None
    mid = (a + b) / 2.0
    return {"bid": b, "ask": a, "mid": mid, "spread_bps": (a - b) / mid * 1e4,
            "ts": ts or datetime.now(UTC).isoformat()}


def _paire_crypto(sym: str) -> str | None:
    """« BTC/USD » (cibles) ou « BTCUSD » (positions Alpaca) → « BTC/USD », ou None."""
    from packages.execution.routing import ALPACA_CRYPTO_BASES
    if "/" in sym:
        return sym
    if sym.endswith("USD") and sym[:-3] in ALPACA_CRYPTO_BASES:
        return f"{sym[:-3]}/USD"
    return None


def _lire_lot(appel, demandes: dict[str, list[str]]) -> dict:
    """Un lot de cotations, rendu sous les symboles DEMANDÉS. Panne → {}."""
    out = {}
    with contextlib.suppress(Exception):          # mesure seulement
        for s, q in (appel(list(demandes)) or {}).items():
            ts = getattr(q, "timestamp", None)
            for orig in demandes.get(s, [s]):
                out[orig] = (q.bid_price, q.ask_price, ts.isoformat() if ts else "")
    return out


def _lecteur_alpaca(symboles: list[str]) -> dict[str, tuple[float, float, str]]:
    """Dernière cotation Alpaca (données de marché, lecture seule). Actions et crypto
    sont lues séparément : un lot en panne ne prive pas l'autre."""
    from alpaca.data.historical import (
        CryptoHistoricalDataClient,
        StockHistoricalDataClient,
    )
    from alpaca.data.requests import CryptoLatestQuoteRequest, StockLatestQuoteRequest
    cle = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_API_SECRET", "")
    actions: dict[str, list[str]] = {}
    paires: dict[str, list[str]] = {}
    for s in symboles:
        p = _paire_crypto(s)
        (paires.setdefault(p, []) if p else actions.setdefault(s, [])).append(s)
    out: dict[str, tuple[float, float, str]] = {}
    if actions:
        cli = StockHistoricalDataClient(cle, secret)
        out |= _lire_lot(lambda x: cli.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=x)), actions)
    if paires:
        cli_c = CryptoHistoricalDataClient(cle, secret)
        out |= _lire_lot(lambda x: cli_c.get_crypto_latest_quote(
            CryptoLatestQuoteRequest(symbol_or_symbols=x)), paires)
    return out


def cotations(symboles, lecteur: Lecteur | None = None) -> dict[str, dict]:
    """{symbole: cotation validée} pour les symboles qui en ont une. Ne lève jamais."""
    syms = sorted({str(s) for s in symboles if s})
    if not syms:
        return {}
    try:
        brut = (lecteur or _lecteur_alpaca)(syms)
    except Exception:  # noqa: BLE001 — une mesure ne bloque jamais un passage
        return {}
    out = {}
    for s, triplet in (brut or {}).items():
        try:
            q = valider(*triplet)
        except TypeError:
            q = None
        if q is not None:
            out[s] = q
    return out
