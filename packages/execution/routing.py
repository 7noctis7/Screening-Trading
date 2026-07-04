"""Routage & mapping des tickers vers les brokers (ère PAPER = mono-broker Alpaca).

La base YAHOO.db contient des actions du MONDE entier (.AS Amsterdam, .PA Paris, .L Londres…)
qu'Alpaca ne peut PAS négocier (US uniquement). Ce module dit, pour chaque symbole : quel broker,
quel symbole côté broker, et s'il est négociable — sinon la production enverrait des ordres
impossibles (ex. AKZA.AS chez Alpaca).

Crypto (cf. ADR-0029) : pendant l'ère paper, TOUTE la crypto passe par **Alpaca paper** (paires
`/USD`, `TimeInForce.GTC`). Les bases non supportées par Alpaca sont **exclues de l'univers papier**
(jamais routées vers Bitmart, qui reste un adaptateur *futur-live gated* — OFF par défaut).
"""

from __future__ import annotations

# Suffixes de places NON-US → non négociables sur Alpaca (actions US only).
_FOREIGN_SUFFIXES = (".AS", ".PA", ".L", ".DE", ".MI", ".MC", ".BR", ".SW", ".ST", ".HE",
                     ".OL", ".CO", ".VI", ".LS", ".F", ".BE", ".HK", ".T", ".TO", ".V",
                     ".AX", ".NZ", ".SI", ".KS", ".KQ", ".TW", ".SS", ".SZ", ".BO", ".NS",
                     ".SA", ".MX", ".JO", ".IS", ".PA", ".MA")

# Bases crypto négociables sur Alpaca (paires /USD). Liste CONSERVATRICE, à réconcilier au besoin
# avec l'API Alpaca `get_all_assets(asset_class=CRYPTO)`. Toute base absente est EXCLUE de l'univers
# papier (jamais routée vers Bitmart). Mieux vaut exclure une base supportée que router l'impossible.
ALPACA_CRYPTO_BASES = frozenset({
    "AAVE", "AVAX", "BAT", "BCH", "BTC", "CRV", "DOGE", "DOT", "ETH", "GRT", "LINK", "LTC",
    "MKR", "PEPE", "SHIB", "SOL", "SUSHI", "UNI", "USDC", "USDT", "XRP", "XTZ", "YFI",
})


def _is_crypto(su: str, ac: str) -> bool:
    return (ac == "crypto" or su.endswith("USDT") or su.endswith("USDC")
            or "/USD" in su or "-USD" in su)


def route(symbol: str, asset_class: str = "") -> dict:
    """Renvoie {broker, broker_symbol, tradeable, reason} pour un symbole de la base."""
    su = (symbol or "").upper()
    ac = (asset_class or "").lower()
    if _is_crypto(su, ac):
        base = symbol.replace("-", "/").split("/")[0].upper()
        if base and base in ALPACA_CRYPTO_BASES:
            # ère paper : crypto → Alpaca paper (paire /USD, TIF GTC côté broker).
            return {"broker": "Alpaca", "broker_symbol": f"{base}/USD", "tradeable": True, "reason": ""}
        # base non supportée par Alpaca → exclue de l'univers papier (JAMAIS vers Bitmart-OFF).
        return {"broker": "Alpaca", "broker_symbol": f"{base}/USD" if base else symbol,
                "tradeable": False,
                "reason": "crypto hors whitelist Alpaca — exclue de l'univers papier"
                          if base else "symbole crypto invalide"}
    if any(su.endswith(s) for s in _FOREIGN_SUFFIXES):
        return {"broker": "Alpaca", "broker_symbol": symbol, "tradeable": False,
                "reason": "action hors-US (non négociable sur Alpaca)"}
    if ac in ("equity", "etf", ""):
        return {"broker": "Alpaca", "broker_symbol": su.replace("/", "."), "tradeable": True, "reason": ""}
    # commodités/indices/forex : pas de broker spot branché → non négociable pour l'instant
    return {"broker": "—", "broker_symbol": symbol, "tradeable": False,
            "reason": f"classe « {ac} » sans broker spot branché"}


def is_tradeable(symbol: str, asset_class: str = "") -> bool:
    return route(symbol, asset_class)["tradeable"]
