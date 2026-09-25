"""AlpacaBroker — implémente l'interface Broker (PAPER par défaut). Requiert alpaca-py.

Même interface que SimBroker → parité backtest↔paper↔live (on échange juste le broker).
Le réseau est isolé ; les mappers (`position_from_alpaca`, `is_filled`) sont purs/testés.
Permissions minimales, jamais retrait. Clés via .env (ALPACA_API_KEY / ALPACA_API_SECRET).
"""

from __future__ import annotations

import os

from packages.core.models import Order, OrderStatus, Position, Side

_STATUS = {
    "new": OrderStatus.SUBMITTED, "accepted": OrderStatus.SUBMITTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED, "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED, "rejected": OrderStatus.REJECTED,
}


def paginer(page, limit: int, page_max: int = 500) -> list:
    """Remonte l'historique page par page. `page(n, borne)` rend les n ordres les plus
    récents ANTÉRIEURS à `borne`.

    Extrait de `AlpacaBroker.orders` pour être testable SANS le SDK : la boucle de
    pagination est exactement le genre de code où une condition d'arrêt mal posée
    tourne à l'infini ou tronque en silence, et c'est précisément ce qu'on répare ici.

    Deux garde-fous, et ils servent des cas différents : le nombre de pages est borné
    (une API qui renvoie toujours du neuf ne peut pas nous retenir), et l'horodatage le
    plus ancien doit STRICTEMENT reculer (une API qui renvoie toujours la même page ne
    peut pas nous faire boucler). L'un couvre le cas où elle répond trop, l'autre le cas
    où elle répond pareil.
    """
    res, vus, borne = [], set(), None
    for _ in range(2 + max(0, limit - 1) // max(1, page_max)):
        lot = page(min(limit, page_max), borne)
        nouveaux = [o for o in lot if getattr(o, "id", None) not in vus]
        if not nouveaux:
            break
        vus.update(getattr(o, "id", None) for o in nouveaux)
        res.extend(nouveaux)
        horo = [getattr(o, "submitted_at", None) for o in nouveaux]
        plus_ancien = min((t for t in horo if t), default=None)
        if plus_ancien is None or (borne is not None and plus_ancien >= borne):
            break
        borne = plus_ancien
        if len(res) >= limit or len(lot) < min(limit, page_max):
            break
    return res[:limit]


def _is_crypto_symbol(symbol: str) -> bool:
    """Alpaca : paires crypto avec '/' (BTC/USD) MAIS les POSITIONS reviennent SANS slash
    (BTCUSD) — fix 07/07 : les ventes de positions héritées partaient en TIF=DAY →
    « invalid crypto time_in_force » (42210000). Une action ne se termine jamais par
    USD/USDT/USDC avec ≥2 lettres devant → heuristique sûre sur ce périmètre."""
    s = (symbol or "").upper()
    if "/" in s:
        return True
    return any(s.endswith(q) and len(s) >= len(q) + 2 for q in ("USDT", "USDC", "USD"))


def position_from_alpaca(p) -> Position:
    """Objet position Alpaca (duck-typed) → Position interne."""
    qty = abs(float(p.qty))
    side = Side.LONG if str(getattr(p, "side", "long")).lower().endswith("long") else Side.SHORT
    return Position(p.symbol, side, qty, float(p.avg_entry_price))


def order_status_from_alpaca(o) -> OrderStatus:
    return _STATUS.get(str(getattr(o, "status", "")).lower(), OrderStatus.PENDING)


class AlpacaBroker:
    name = "alpaca"
    is_paper = True

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 paper: bool = True) -> None:
        self.is_paper = paper
        from packages.common.env import load_env
        load_env()                          # .env (tous points d'entrée)
        from alpaca.trading.client import TradingClient  # import local
        self._client = TradingClient(
            api_key or os.environ.get("ALPACA_API_KEY", ""),
            api_secret or os.environ.get("ALPACA_API_SECRET", ""),
            paper=paper)

    def submit(self, order: Order) -> Order:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        # TIF asset-class-aware : crypto (24/7) exige GTC ; actions gardent DAY.
        tif = TimeInForce.GTC if _is_crypto_symbol(order.instrument) else TimeInForce.DAY
        req = MarketOrderRequest(
            symbol=order.instrument, qty=order.qty,
            side=OrderSide.BUY if order.side is Side.LONG else OrderSide.SELL,
            time_in_force=tif,
            client_order_id=order.client_id)  # idempotence native Alpaca
        res = self._client.submit_order(req)
        order.status = order_status_from_alpaca(res)
        return order

    def submit_notional(self, symbol: str, side: Side, notional: float,
                        client_id: str | None = None):
        """Ordre marché par MONTANT $ (Alpaca gère le fractionnement) — pratique pour répliquer
        une allocation cible en %. Reste en paper si paper=True.

        IDEMPOTENT PAR `client_id` (QML-006). `run_live` appelle cette méthode sous `retry` :
        sans identifiant, un envoi accepté puis perdu en route (timeout) repartait une seconde
        fois — un ordre doublé. Avec lui, Alpaca refuse le doublon, et une exception n'est
        rendue qu'après avoir demandé au courtier s'il détient déjà l'ordre : s'il l'a, c'est
        CET ordre qu'on rend, pas une erreur."""
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        tif = TimeInForce.GTC if _is_crypto_symbol(symbol) else TimeInForce.DAY
        req = MarketOrderRequest(
            symbol=symbol, notional=round(notional, 2),
            side=OrderSide.BUY if side is Side.LONG else OrderSide.SELL,
            time_in_force=tif, client_order_id=client_id)
        try:
            return self._client.submit_order(req)
        except Exception:
            if not client_id:
                raise
            try:
                return self._client.get_order_by_client_id(client_id)
            except Exception:  # noqa: BLE001 — l'ordre n'existe pas : l'erreur d'origine vaut
                pass
            raise

    def positions(self) -> list[Position]:
        return [position_from_alpaca(p) for p in self._client.get_all_positions()]

    def positions_detailed(self) -> list[dict]:
        """Positions RÉELLES enrichies (prix courant, valeur de marché, P&L latent) pour l'UI."""
        out = []
        for p in self._client.get_all_positions():
            out.append({
                "symbol": p.symbol, "broker": "Alpaca",
                "side": "long" if str(getattr(p, "side", "long")).lower().endswith("long") else "short",
                "qty": abs(float(p.qty)), "avg_price": float(p.avg_entry_price),
                "price": float(getattr(p, "current_price", 0) or 0),
                "market_value": float(getattr(p, "market_value", 0) or 0),
                "pnl": float(getattr(p, "unrealized_pl", 0) or 0),
                "pnl_pct": float(getattr(p, "unrealized_plpc", 0) or 0)})
        return out

    def close_position(self, symbol: str) -> bool:
        """Solde INTÉGRALEMENT une position (ordre en quantité, côté courtier).

        Indispensable pour ne pas laisser de résidu : `submit_notional` demande « vends pour
        812 $ » et le cours bouge entre la cotation et l'exécution, il reste toujours une miette.
        Cette miette tombe alors sous la bande d'inaction et n'est plus jamais vendue.
        """
        try:
            self._client.close_position(symbol)
            return True
        except Exception:  # noqa: BLE001 — position déjà fermée / inconnue : rien à solder
            return False

    PAGE_MAX = 500                      # plafond imposé par l'API Alpaca pour `limit`

    def orders(self, limit: int = 100) -> list[dict]:
        """Ordres RÉELS exécutés (fills) du compte — pour la page Trades. [] si indispo.

        PAGINÉ (03/09). `get_orders` plafonne à 500 par appel et rend les plus RÉCENTS
        d'abord : un seul appel ne peut donc pas rendre un historique plus long, et il
        le tronque SANS RIEN DIRE. Mesuré ce jour-là : `limit=500` a rendu 202 ordres,
        et la réconciliation du journal n'a pu solder que la MOITIÉ de chaque position —
        les ventes plus anciennes n'étaient jamais arrivées.

        On remonte donc page par page avec `until` = le plus ancien horodatage déjà vu.
        Deux garde-fous contre la boucle infinie : le nombre de pages est borné, et
        l'horodatage le plus ancien doit STRICTEMENT reculer à chaque tour — sinon
        l'API rend la même page et on s'arrête.
        """
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest
            def _page(n, borne):
                return list(self._client.get_orders(GetOrdersRequest(
                    status=QueryOrderStatus.CLOSED, limit=n, until=borne)))
            res = paginer(_page, limit, self.PAGE_MAX)
            out = []
            for o in res:
                fq = float(getattr(o, "filled_qty", 0) or 0)
                if fq <= 0:                       # on ne garde que les ordres réellement remplis
                    continue
                ts = getattr(o, "filled_at", None) or getattr(o, "submitted_at", None)
                out.append({
                    "id": str(getattr(o, "id", "")),   # identité du fill → idempotence
                    "symbol": o.symbol, "broker": "Alpaca",
                    "side": str(getattr(o, "side", "")).lower().split(".")[-1],
                    "qty": fq, "price": float(getattr(o, "filled_avg_price", 0) or 0),
                    "notional": fq * float(getattr(o, "filled_avg_price", 0) or 0),
                    "date": ts.isoformat() if ts else "",
                    "status": str(getattr(o, "status", "")).lower().split(".")[-1]})
            return out
        except Exception:  # noqa: BLE001
            return []

    def open_orders(self, limit: int = 100) -> list[dict]:
        """Ordres OUVERTS / en attente d'exécution (non encore remplis) — page Trades.
        Inclut new/accepted/pending_new/held/partially_filled (ex. marché fermé le week-end). [] si indispo."""
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            res = self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=limit))
            out = []
            for o in res:
                rq = float(getattr(o, "qty", 0) or 0)            # ordre en parts (qty)…
                nv = float(getattr(o, "notional", 0) or 0)       # …ou ordre en MONTANT $ (notional, qty=None)
                fq = float(getattr(o, "filled_qty", 0) or 0)
                lp = getattr(o, "limit_price", None)
                px = float(lp) if lp else float(getattr(o, "filled_avg_price", 0) or 0)
                ts = getattr(o, "submitted_at", None) or getattr(o, "created_at", None)
                # montant : notional explicite si présent, sinon parts × prix (si prix connu)
                amount = nv if nv > 0 else (rq * px if px else 0.0)
                out.append({
                    "id": str(getattr(o, "id", "")),   # identité du fill → idempotence
                    "symbol": o.symbol, "broker": "Alpaca",
                    "side": str(getattr(o, "side", "")).lower().split(".")[-1],
                    "qty": rq, "filled_qty": fq, "notional_order": nv > 0,
                    "price": px, "order_type": str(getattr(o, "order_type", "")).lower().split(".")[-1],
                    "notional": round(amount, 2),
                    "date": ts.isoformat() if ts else "",
                    "status": str(getattr(o, "status", "")).lower().split(".")[-1]})
            return out
        except Exception:  # noqa: BLE001
            return []

    def equity(self) -> float:
        return float(self._client.get_account().equity)

    def portfolio_history(self, period: str = "1A", timeframe: str = "1D") -> list[dict]:
        """Historique RÉEL d'equity du compte (Alpaca le stocke). Renvoie [{t, v}] (vide si indispo)."""
        from datetime import datetime, timezone
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            ph = self._client.get_portfolio_history(
                GetPortfolioHistoryRequest(period=period, timeframe=timeframe))
            ts, eq = list(ph.timestamp or []), list(ph.equity or [])
            return [{"t": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
                     "v": round(float(v), 2)} for t, v in zip(ts, eq) if v]
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _champ(a, nom: str):
        """Un enregistrement d'activité, qu'il arrive en dict OU en objet.

        La route REST rend du JSON brut aujourd'hui ; une version du SDK qui le
        parserait en modèles ferait échouer un `.get()` — et l'échec serait SILENCIEUX,
        puisque `frais` rendrait alors zéro dollar au lieu de lever. Un zéro de frais
        se lit « aucun frais prélevé », ce qui est faux de 810,30 $ sur ce compte.
        """
        return a.get(nom) if isinstance(a, dict) else getattr(a, nom, None)

    def _activites(self, page_token: str | None) -> list[dict]:
        """Une page d'activités, PAR LA ROUTE REST et non par une classe du SDK.

        POURQUOI (18/09). `GetAccountActivitiesRequest` n'existe pas dans
        `alpaca.trading.requests` de la version installée — l'import échouait, et les
        frais restaient introuvables. Le nom des classes du SDK bouge d'une version à
        l'autre ; l'URL `/account/activities`, elle, est le contrat public d'Alpaca.
        On s'appuie donc sur ce qui ne bouge pas, et le client REST du SDK ne sert plus
        qu'à porter l'authentification.
        """
        params = {"activity_types": "FEE,CFEE", "page_size": 100}
        if page_token:
            params["page_token"] = page_token
        rep = self._client.get("/account/activities", params)
        return list(rep) if isinstance(rep, list) else list(rep.get("activities", []))

    def frais(self, pages_max: int = 60) -> dict:
        """Frais RÉELLEMENT prélevés, lus dans les ACTIVITÉS du compte.

        POURQUOI ILS NE SONT PAS DANS `orders` (18/09). Un fill porte une quantité et un
        prix, pas son coût de transaction : chez Alpaca les frais sont des ACTIVITÉS
        séparées — `FEE` (TAF/REG/CAT, en dollars) et `CFEE` (crypto). Un registre
        reconstruit depuis les seuls ordres est donc BRUT de frais, et l'identité
        `capital = mise + réalisé + latent` y perd exactement leur montant : 810,30 $
        mesurés ce jour-là sur un compte à 100 973,45 $.

        LES FRAIS CRYPTO SE PRÉLÈVENT EN NATURE, et c'est le piège de lecture. Une
        `CFEE` retire des JETONS : elle réduit la quantité détenue, donc la valeur du
        portefeuille, sans passer par le cash. On somme les montants en DOLLARS et on
        compte à part ce qui n'en porte pas, plutôt que de convertir des jetons à un
        prix qu'on choisirait nous-mêmes.

        LA PAGINATION EST BORNÉE ET SON ARRÊT EST VÉRIFIÉ : une page vide, un jeton qui
        ne change pas, ou le plafond. Une boucle qui redemande la même page est le
        défaut que `paginer` a déjà coûté à ce dépôt.
        """
        actes: list[dict] = []
        jeton, vus = None, set()
        try:
            for _ in range(max(1, pages_max)):
                page = self._activites(jeton)
                if not page:
                    break
                actes.extend(page)
                suivant = str(self._champ(page[-1], "id") or "")
                if not suivant or suivant in vus:
                    break
                vus.add(suivant)
                jeton = suivant
        except Exception as e:  # noqa: BLE001
            if not actes:
                return {"disponible": False, "motif": f"{type(e).__name__}: {e}"[:200]}
        par_type: dict[str, float] = {}
        en_nature: list[dict] = []
        for a in actes:
            typ = str(self._champ(a, "activity_type") or "").upper()
            montant = self._champ(a, "net_amount")
            try:
                val = float(montant) if montant not in (None, "") else None
            except (TypeError, ValueError):
                val = None
            if val is not None:
                par_type[typ] = round(par_type.get(typ, 0.0) + val, 4)
            else:
                # Prélèvement EN JETONS : on le NOMME sans lui donner un prix qu'on
                # aurait choisi. Sa trace en dollars est dans la valeur du portefeuille.
                # ON GARDE L'ENREGISTREMENT BRUT (18/09). Les prélèvements en jetons
                # pèsent ~456 $ sur ce compte, et les valoriser demande de savoir si
                # Alpaca joint un prix. Deviner les champs disponibles serait un aller-
                # retour de plus ; on les publie, et la mesure tranche du premier coup.
                en_nature.append(
                    {"type": typ, "symbole": str(self._champ(a, "symbol") or ""),
                     "qty": float(self._champ(a, "qty") or 0),
                     "date": str(self._champ(a, "date")
                                 or self._champ(a, "transaction_time") or ""),
                     "brut": dict(a) if isinstance(a, dict) else vars(a)})
        champs = sorted({k for e in en_nature for k in (e.get("brut") or {})})
        return {"disponible": True, "n": len(actes), "par_type": par_type,
                "total_usd": round(sum(par_type.values()), 2),
                "en_nature": en_nature[:50], "n_en_nature": len(en_nature),
                "champs_en_nature": champs,
                "qty_par_symbole": {
                    s: round(sum(e["qty"] for e in en_nature if e["symbole"] == s), 10)
                    for s in sorted({e["symbole"] for e in en_nature})}}

    def cancel(self, client_id: str) -> bool:
        try:
            o = self._client.get_order_by_client_id(client_id)
            self._client.cancel_order_by_id(o.id)
            return True
        except Exception:  # noqa: BLE001
            return False
