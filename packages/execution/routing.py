"""Routage & mapping des tickers vers les brokers (Alpaca actions US, Bitmart crypto).

La base YAHOO.db contient des actions du MONDE entier (.AS Amsterdam, .PA Paris, .L Londres…)
qu'Alpaca ne peut PAS négocier (US uniquement), et des cryptos à router vers Bitmart au bon format.
Ce module dit, pour chaque symbole : quel broker, quel symbole côté broker, et s'il est négociable.
Sans ça, la production enverrait des ordres impossibles (ex. AKZA.AS chez Alpaca).
"""

from __future__ import annotations

# Suffixes de places NON-US → non négociables sur Alpaca (actions US only).
_FOREIGN_SUFFIXES = (".AS", ".PA", ".L", ".DE", ".MI", ".MC", ".BR", ".SW", ".ST", ".HE",
                     ".OL", ".CO", ".VI", ".LS", ".F", ".BE", ".HK", ".T", ".TO", ".V",
                     ".AX", ".NZ", ".SI", ".KS", ".KQ", ".TW", ".SS", ".SZ", ".BO", ".NS",
                     ".SA", ".MX", ".JO", ".IS", ".PA", ".MA")


def _is_crypto(su: str, ac: str) -> bool:
    return (ac == "crypto" or su.endswith("USDT") or su.endswith("USDC")
            or "/USD" in su or "-USD" in su)


def route(symbol: str, asset_class: str = "") -> dict:
    """Renvoie {broker, broker_symbol, tradeable, reason} pour un symbole de la base."""
    su = (symbol or "").upper()
    ac = (asset_class or "").lower()
    if _is_crypto(su, ac):
        base = symbol.replace("-", "/").split("/")[0].upper()
        return {"broker": "Bitmart", "broker_symbol": f"{base}/USDT", "tradeable": bool(base),
                "reason": "" if base else "symbole crypto invalide"}
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
