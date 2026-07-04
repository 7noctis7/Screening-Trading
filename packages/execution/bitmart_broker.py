"""BitmartBroker — exécution CRYPTO SPOT via ccxt (paires /USDT), miroir de SimBroker/Alpaca.

Sécurité d'abord : **dry-run par défaut** (aucun ordre réel), clés via .env
(BITMART_API_KEY / BITMART_API_SECRET / BITMART_API_MEMO). `ccxt` n'est importé que si réellement
utilisé → testable sans dépendance ni réseau. Permissions minimales (jamais de retrait).

Corrige les bugs de QUANTITÉ : arrondi à la précision/lot-size du marché, achat marché par COÛT
($ notional), et lecture des positions/equity en **spot** (solde des coins), pas en futures.
"""

from __future__ import annotations

import os

from packages.core.models import Order, OrderStatus, Position, Side


class BitmartBroker:
    name = "bitmart"
    is_paper: bool = False           # Bitmart n'a pas de vrai paper → dry_run protège (défaut True)

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 memo: str | None = None, dry_run: bool = True, market: str | None = None) -> None:
        self.dry_run = dry_run
        self._key = api_key or os.environ.get("BITMART_API_KEY", "")
        self._secret = api_secret or os.environ.get("BITMART_API_SECRET", "")
        self._memo = memo or os.environ.get("BITMART_API_MEMO", "")
        # marché de TRADING : "spot" (défaut, sans levier) ou "swap" (futures — levier = risque).
        self.market = (market or os.environ.get("BITMART_MARKET", "spot")).lower()
        self._ex = None              # connexion ccxt paresseuse
        self._loaded = False
        # Idempotence : client_id → (statut, filled_qty) RÉELS du 1er submit (rejoués tels quels).
        self._seen: dict[str, tuple[OrderStatus, float | None]] = {}

    def _live(self) -> bool:
        return not self.dry_run and bool(self._key and self._secret)

    def _client(self):
        if self._ex is None:
            import ccxt  # import local
            self._ex = ccxt.bitmart({"apiKey": self._key, "secret": self._secret,
                                     "uid": self._memo, "enableRateLimit": True,
                                     "options": {"defaultType": "swap" if self.market == "swap" else "spot"}})
        if not self._loaded:
            try:
                self._ex.load_markets()
                self._loaded = True
            except Exception:  # noqa: BLE001
                pass
        return self._ex

    def _round_qty(self, symbol: str, qty: float) -> float:
        """Arrondit la quantité à la précision/lot-size du marché (sinon ordre rejeté)."""
        try:
            return float(self._client().amount_to_precision(symbol, qty))
        except Exception:  # noqa: BLE001
            return round(qty, 6)

    def _min_cost(self, symbol: str) -> float:
        try:
            m = self._client().market(symbol)
            return float((m.get("limits", {}).get("cost", {}) or {}).get("min") or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0

    def submit_notional(self, symbol: str, side: Side, cost_usdt: float) -> Order:
        """Ordre marché par MONTANT ($ USDT) — la quantité est dérivée du prix puis arrondie."""
        order = Order(symbol, side, 0.0, None)
        s = "buy" if side is Side.LONG else "sell"
        if not self._live():
            order.status = OrderStatus.SUBMITTED          # simulation : rien n'est envoyé
            return order
        px = self.last_price(symbol)
        if px <= 0 or cost_usdt <= 0:
            order.status = OrderStatus.REJECTED
            return order
        qty = self._round_qty(symbol, cost_usdt / px)
        order.qty = qty
        if qty <= 0 or cost_usdt < self._min_cost(symbol):
            order.status = OrderStatus.REJECTED           # sous le minimum du marché
            return order
        try:
            res = self._client().create_order(symbol, "market", s, qty)
            order.status, order.filled_qty = _map_fill(res, qty)
        except Exception:  # noqa: BLE001
            order.status = OrderStatus.REJECTED
        return order

    def _remember(self, order: Order) -> Order:
        """Mémorise le résultat RÉEL et définitif d'un submit live (rejoué tel quel sur retry)."""
        if order.client_id:
            self._seen[order.client_id] = (order.status, order.filled_qty)
        return order

    def submit(self, order: Order) -> Order:
        # Idempotence : ce client_id a déjà un résultat définitif → le REJOUER tel quel,
        # sans renvoyer d'ordre. Jamais de FILLED fabriqué ; un rejet reste un rejet ;
        # une qté partielle rejouée reste partielle (pas de fill plein supposé).
        if order.client_id and order.client_id in self._seen:
            order.status, order.filled_qty = self._seen[order.client_id]
            return order
        s = "buy" if order.side is Side.LONG else "sell"
        if not self._live():
            order.status = OrderStatus.SUBMITTED          # dry-run : rien envoyé, rien mémorisé
            return order
        qty = self._round_qty(order.instrument, order.qty)    # précision/lot-size
        if qty <= 0:
            order.status = OrderStatus.REJECTED
            return self._remember(order)
        order.qty = qty
        # clientOrderId → dédup côté exchange (ceinture+bretelles si la mémo locale est perdue).
        params = {"clientOrderId": order.client_id} if order.client_id else {}
        try:
            res = self._client().create_order(order.instrument, "market", s, qty, params=params)
            order.status, order.filled_qty = _map_fill(res, qty)
        except Exception:  # noqa: BLE001
            order.status = OrderStatus.REJECTED
        return self._remember(order)

    def last_price(self, symbol: str) -> float:
        """Dernier prix (ccxt) pour dimensionner un ordre ; 0.0 si indisponible/dry-run."""
        if not self._live():
            return 0.0
        try:
            return float(self._client().fetch_ticker(symbol).get("last") or 0.0)
        except Exception:  # noqa: BLE001
            return 0.0

    def positions(self) -> list[Position]:
        """Positions = coins SPOT détenus (solde > 0) + positions FUTURES ouvertes (swap)."""
        if not self._live():
            return []
        out: list[Position] = []
        try:                                          # SPOT : coins en solde
            total = (self._client().fetch_balance({"type": "spot"}).get("total", {}) or {})
            for coin, amt in total.items():
                amt = float(amt or 0.0)
                if coin in ("USDT", "USDC", "USD") or amt <= 0:
                    continue
                sym = f"{coin}/USDT"
                out.append(Position(sym, Side.LONG, amt, self.last_price(sym)))
        except Exception:  # noqa: BLE001
            pass
        try:                                          # FUTURES : positions ouvertes
            for p in (self._client().fetch_positions() or []):
                out.append(position_from_ccxt(p))
        except Exception:  # noqa: BLE001
            pass
        return out

    def equity(self) -> float:
        """Valeur totale en USDT sur les DEUX portefeuilles (spot : cash + coins ; futures : marge)."""
        if not self._live():
            return 0.0
        eq = 0.0
        for typ in ("spot", "swap"):
            try:
                total = (self._client().fetch_balance({"type": typ}).get("total", {}) or {})
                eq += float(total.get("USDT", 0.0) or 0.0) + float(total.get("USDC", 0.0) or 0.0)
                if typ == "spot":
                    for coin, amt in total.items():
                        amt = float(amt or 0.0)
                        if coin in ("USDT", "USDC", "USD") or amt <= 0:
                            continue
                        eq += amt * self.last_price(f"{coin}/USDT")
            except Exception:  # noqa: BLE001
                pass
        return round(eq, 2)

    def positions_detailed(self) -> list[dict]:
        """Positions SPOT réelles enrichies. Le prix d'entrée n'EXISTE PAS dans le solde spot →
        on le reconstitue depuis l'historique d'achats réel ; si inconnu, P&L = None (UI « — »)
        plutôt qu'un faux 0 %."""
        buys: dict[str, list[float]] = {}                # symbole → [coût total, qté totale] (achats)
        for t in self.orders(200):
            if t.get("side") == "buy" and t.get("qty"):
                b = buys.setdefault(t["symbol"], [0.0, 0.0])
                b[0] += float(t.get("notional", 0) or 0); b[1] += float(t["qty"])
        out: list[dict] = []
        for p in self.positions():
            px = self.last_price(p.instrument)
            bb = buys.get(p.instrument)
            avg = (bb[0] / bb[1]) if bb and bb[1] > 0 else 0.0
            mv = p.qty * px
            known = avg > 0
            out.append({"symbol": p.instrument, "broker": "Bitmart", "side": "long",
                        "qty": p.qty, "avg_price": round(avg, 6) if known else None, "price": px,
                        "market_value": round(mv, 2),
                        "pnl": round((px - avg) * p.qty, 2) if known else None,
                        "pnl_pct": round(px / avg - 1, 4) if known else None})
        return out

    def orders(self, limit: int = 100) -> list[dict]:
        """Ordres/transactions RÉELS exécutés (spot) — pour la page Trades. [] si indispo."""
        if not self._live():
            return []
        try:
            trades = self._client().fetch_my_trades(limit=limit) or []
            out = []
            for t in trades:
                out.append({"symbol": t.get("symbol", ""), "broker": "Bitmart",
                            "side": str(t.get("side", "")).lower(),
                            "qty": float(t.get("amount", 0) or 0),
                            "price": float(t.get("price", 0) or 0),
                            "notional": float(t.get("cost", 0) or 0),
                            "date": t.get("datetime", "") or "", "status": "filled"})
            return out
        except Exception:  # noqa: BLE001
            return []

    def open_orders(self, limit: int = 100) -> list[dict]:
        """Ordres SPOT OUVERTS / en attente d'exécution (non remplis) — page Trades. [] si indispo."""
        if not self._live():
            return []
        try:
            oo = self._client().fetch_open_orders(limit=limit) or []
            out = []
            for o in oo:
                rq = float(o.get("amount", 0) or 0)
                px = float(o.get("price", 0) or 0)
                out.append({"symbol": o.get("symbol", ""), "broker": "Bitmart",
                            "side": str(o.get("side", "")).lower(),
                            "qty": rq, "filled_qty": float(o.get("filled", 0) or 0),
                            "price": px, "order_type": str(o.get("type", "")).lower(),
                            "notional": float(o.get("cost", 0) or 0) or rq * px,
                            "date": o.get("datetime", "") or "",
                            "status": str(o.get("status", "open")).lower()})
            return out
        except Exception:  # noqa: BLE001
            return []

    def ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 400) -> list[dict]:
        """Bougies RÉELLES (ccxt) d'une paire spot → [{t,o,h,l,c,v}] pour le graphe. [] si indispo."""
        if not self._live():
            return []
        try:
            rows = self._client().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit) or []
            from datetime import datetime, timezone
            out = []
            for ts, o, h, low, c, v in rows:
                d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
                out.append({"t": d, "o": round(float(o), 6), "h": round(float(h), 6),
                            "l": round(float(low), 6), "c": round(float(c), 6), "v": round(float(v or 0), 2)})
            return out
        except Exception:  # noqa: BLE001
            return []

    def cancel(self, client_id: str) -> bool:
        return True


def _map_fill(res: dict, qty: float) -> tuple[OrderStatus, float | None]:
    """Réponse ccxt → (statut, qté remplie). `filled_qty=None` = inconnu (jamais supposé plein).

    Un ordre `closed/filled` dont `filled < qty` est PARTIELLEMENT rempli ; un ordre encore
    ouvert avec une part déjà remplie l'est aussi ; sinon simplement SUBMITTED.
    """
    raw = res.get("filled")
    filled = float(raw) if raw is not None else None
    if res.get("status") in ("closed", "filled"):
        if filled is not None and filled + 1e-12 < qty:
            return OrderStatus.PARTIALLY_FILLED, filled
        return OrderStatus.FILLED, filled
    if filled and filled > 0:
        return OrderStatus.PARTIALLY_FILLED, filled
    return OrderStatus.SUBMITTED, filled


def position_from_ccxt(p) -> Position:
    """Position ccxt (dict) → Position interne (compat héritée)."""
    qty = abs(float(p.get("contracts") or p.get("amount") or 0.0))
    side = Side.SHORT if str(p.get("side", "long")).lower() == "short" else Side.LONG
    entry = float(p.get("entryPrice") or p.get("average") or 0.0)
    return Position(p.get("symbol", ""), side, qty, entry)
