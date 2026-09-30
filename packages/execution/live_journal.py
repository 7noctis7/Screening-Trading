"""Journalisation des OUVERTURES de réconciliation paper — `legacy=0` + features de DÉCISION.

Phase 1 (P0-4 / BLOC 4). Câble le chemin de PROD (`run_live.py`) sur `data/journal.db` pour que
chaque run accumule des trades RÉELS exploitables par la calibration ML (aujourd'hui : 0 `legacy=0`).

Séparation stricte des sources (anti look-ahead, cf. garde-fou CLAUDE.md) :
  - **FEATURES** = figées à la DÉCISION dans `build_snapshot()` (screener + poids cibles + régime) et
    transportées jusqu'ici. JAMAIS recalculées après le submit.
  - **FAITS d'exécution** (prix/qté d'entrée) = positions RÉELLES du broker APRÈS fill (vérité terrain).

Le round-trip (exit/pnl/MFE/MAE) = Phase 2 (appariement des ventes). Ici on n'écrit que des ENTRÉES.
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.core.models import AssetClass, Side, TradeRecord
from packages.execution.costs import broker_charge


def _asset_class(sym: str, hint: str | None) -> AssetClass:
    """Classe d'actif : indice explicite du snapshot, sinon paires crypto = présence d'un '/'."""
    if hint:
        try:
            return AssetClass(hint)
        except ValueError:
            pass
    return AssetClass.CRYPTO if "/" in (sym or "") else AssetClass.EQUITY


def _finite_float(v) -> float | None:
    """Float fini utilisable en features_snapshot ; None si absent / non numérique / NaN."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if f == f else None  # NaN → None


def feature_map(snap: dict) -> dict[str, dict]:
    """Extrait, du snapshot de DÉCISION, les features PAR SYMBOLE (score + contributions).

    Union des sources (anti look-ahead : tout est déjà figé dans le snap) :
      1. `screener.rows` — ranking pur (score + factors)
      2. `screen.rows` — screener à filtres (score comble les trous)
      3. `live.target_orders[].rank_score` — score attaché decision-time sur l'ordre cible
         (souvent le seul hit : les ouvertures paper viennent du preset, pas du screener)

    `rank_score` n'est écrit QUE si la valeur est un float fini (jamais de clé None qui
    disparaîtrait ensuite silencieusement dans `build_open`)."""
    out: dict[str, dict] = {}

    def _ensure(sym: str) -> dict:
        return out.setdefault(sym, {})

    for row in (snap.get("screener") or {}).get("rows", []) or []:
        sym = row.get("symbol")
        if not sym:
            continue
        bucket = _ensure(sym)
        sc = _finite_float(row.get("score"))
        if sc is not None and "rank_score" not in bucket:
            bucket["rank_score"] = sc
        for k, v in (row.get("factors") or {}).items():
            fv = _finite_float(v)
            if fv is not None and k not in bucket:
                bucket[k] = fv

    for row in (snap.get("screen") or {}).get("rows", []) or []:
        sym = row.get("symbol")
        if not sym:
            continue
        bucket = _ensure(sym)
        sc = _finite_float(row.get("score"))
        if sc is not None and "rank_score" not in bucket:
            bucket["rank_score"] = sc

    for o in ((snap.get("live") or {}).get("target_orders") or []):
        sym = o.get("symbol")
        if not sym:
            continue
        sc = _finite_float(o.get("rank_score"))
        if sc is None:
            continue
        bucket = _ensure(sym)
        # gap-fill : preset symbols absents du screener
        if "rank_score" not in bucket:
            bucket["rank_score"] = sc
    return out


def regime_context(snap: dict) -> tuple[str | None, dict]:
    """(label régime, features numériques de régime) depuis `snap["dashboard"]["regime"]`.

    Best-effort : le label = `cycle/risk_mode` (ex. « expansion/risk_on ») ; l'exposition cible est
    une feature numérique commune à toutes les entrées du run."""
    r = (snap.get("dashboard") or {}).get("regime") or {}
    cycle, mode = r.get("cycle"), r.get("risk_mode")
    label = "/".join(x for x in (cycle, mode) if x) or None
    ctx: dict = {}
    expo = r.get("exposure_multiplier")
    if isinstance(expo, (int, float)):
        ctx["regime_expo"] = float(expo)
    return label, ctx


def normaliser(sym: str) -> str:
    """« AVAX/USDC », « AVAX-USD » et « AVAXUSD » désignent le même instrument.

    DÉLÈGUE à `symbole_canonique`, qui retire aussi la DEVISE DE COTATION. Un simple
    retrait des séparateurs ne suffit pas : « AVAX/USDC » deviendrait « AVAXUSDC » et
    « AVAXUSD » resterait « AVAXUSD » — deux clés distinctes pour le même actif, et
    l'agrégation des achats se scinderait en deux. Une seule définition du symbole
    canonique dans tout le dépôt, sinon elles divergent.
    """
    from packages.research.biais_fermeture import symbole_canonique
    return symbole_canonique(sym)


def agreger_achats(ordres: list[dict], jour: str) -> dict[str, dict]:
    """Achats RÉELLEMENT exécutés un jour donné, agrégés par symbole : quantité et VWAP.

    POURQUOI CETTE FONCTION EXISTE (03/09). `_journal_opens` prenait le fill dans la
    POSITION du courtier lue juste après l'envoi de l'ordre. Deux conséquences, toutes
    deux mesurées sur le compte réel :

      · si la position n'était pas encore à jour (ordre non rempli à l'instant du run,
        marché fermé, latence), le fill était introuvable et l'achat n'était JAMAIS
        journalisé. Le message disait « capturé au prochain run » — mais rien ne le
        capture, sauf à racheter le même titre. L'achat était perdu ;
      · la position porte la quantité TOTALE et le prix de revient MOYEN, pas l'achat
        du jour. Le lot ne décrivait donc pas l'opération qu'il prétendait décrire.

    Mesuré le 03/09 : sur 87 symboles achetés, 30 n'étaient couverts qu'à moitié ou
    moins (AVAX 626 au journal contre 1 239 achetés, PATH 9 contre 139).

    Les fills, eux, sont la vérité terrain : ils existent après coup, ils portent la
    quantité RÉELLEMENT achetée et son prix. Un run tardif les retrouve ; une position
    non rafraîchie, non.
    """
    par_sym: dict[str, dict] = {}
    for o in ordres or []:
        if o.get("side") != "buy" or (o.get("date") or "")[:10] != jour:
            continue
        q, px = float(o.get("qty") or 0.0), float(o.get("price") or 0.0)
        if q <= 0 or px <= 0:
            continue
        cle = normaliser(o.get("symbol", ""))
        acc = par_sym.setdefault(cle, {"qty": 0.0, "notional": 0.0, "ids": []})
        acc["qty"] += q
        acc["notional"] += q * px
        acc["ids"].append(str(o.get("id") or ""))        # "" = ordre sans identité
    return {k: {"qty": round(v["qty"], 10),
                "avg_price": v["notional"] / v["qty"],      # VWAP du jour, pas le PRU
                "origine": "ordre",                         # un FILL du jour (cf. ecart)
                "ids": v["ids"]}                            # les ordres que ce VWAP mêle
            for k, v in par_sym.items() if v["qty"] > 0}


def ecart_decision(fill: dict | None, features: dict, prix: float, qty: float,
                   order_id: str | None = None) -> float | None:
    """Écart décision → fill de l'ACHAT, en devise : (fill − décision) × quantité.

    Convention unique via `fills` + `Fill.shortfall_amount` : positif = défavorable.
    Descriptif : déjà dans le prix de fill, jamais retranché du P&L. `None` (jamais 0) :
      · sans prix de décision ;
      · si le « fill » est une POSITION de repli (prix moyen d'autres jours) ;
      · si le VWAP du jour n'est pas EXACTEMENT l'ordre envoyé (`order_id`) : un achat
        manuel ou un autre passage du même jour sur le même titre y serait mêlé, et
        l'écart serait attribué à une décision qui n'en est pas la cause."""
    from packages.core.models import Fill, Side
    from packages.execution.fills import shortfall_bps
    f = fill or {}
    if f.get("origine") != "ordre" or not order_id or f.get("ids") != [str(order_id)]:
        return None
    ref = features.get("decision_price")
    if not isinstance(ref, (int, float)):
        return None
    bps = shortfall_bps(ref, prix, Side.LONG)
    if bps is None:
        return None
    # Devise via Fill.shortfall_amount (formule unique dans models/fills — pas ici).
    amt = Fill(instrument="_", side=Side.LONG, qty=qty, fill_price=prix,
               reference_price=float(ref), shortfall_bps=bps).shortfall_amount
    return None if amt is None else round(amt, 6)


def _classe_de_frais(symbole: str, hint: str | None) -> str:
    """Classe d'actif au sens des BARÈMES (le courtier, pas la taxonomie interne)."""
    return _asset_class(symbole, hint).value


def build_open(symbol: str, *, venue: str, asset_class: str | None, fill: dict | None,
               features: dict | None, regime: str | None = None,
               strategy: str = "preset", ts: datetime | None = None,
               order_id: str | None = None,
               ts_arrival: datetime | None = None,
               P_arrival: float | None = None,
               fill_id: str | None = None,
               impact_horizon: str | None = "1bar") -> TradeRecord | None:
    """TradeRecord d'ouverture (`legacy=0`), ou None si le fill est inexploitable (prix/qté ≤ 0).

    `id` DÉTERMINISTE par (jour, broker, symbole) → l'UPSERT du journal rend le re-run du même jour
    idempotent (jamais de doublon). `features_snapshot` = uniquement des floats finis (JSON/ML-safe)."""
    ts = ts or datetime.now(timezone.utc)
    price = float((fill or {}).get("avg_price") or 0.0)
    qty = float((fill or {}).get("qty") or 0.0)
    if price <= 0 or qty <= 0:
        return None
    # features_snapshot = floats finis (JSON/ML-safe), SAUF exceptions str documentées :
    # `ts_decision` (ISO TCA) et `setup_id` (sleeve swing) — même famille ; le reste float-only.
    feats: dict = {}
    for k, v in (features or {}).items():
        if k in ("ts_decision", "setup_id") and isinstance(v, str) and v.strip():
            feats[k] = v.strip()
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
            feats[k] = round(float(v), 6)
    fee = broker_charge(_classe_de_frais(symbol, asset_class), price * qty, side="BUY")
    # P_arrival : kwargs dédiés, sinon decision_price figé dans features (chemin run_live).
    p_arr = P_arrival
    if p_arr is None:
        dp = feats.get("decision_price")
        p_arr = float(dp) if isinstance(dp, (int, float)) else None
    # Sans mid/bid/ask paper : bench_quality=missing ; NULL ≠ 0 inventé.
    return TradeRecord(
        id=f"P-{ts.strftime('%Y%m%d')}-{venue}-{symbol}",
        instrument=symbol, asset_class=_asset_class(symbol, asset_class),
        venue=venue, side=Side.LONG, qty=qty, entry_ts=ts, entry_price=price, avg_price=price,
        entry_reason="reconciliation paper (open/add)", regime=regime, strategy=strategy,
        fees=fee, fees_source="estimated",
        slippage=ecart_decision(fill, feats, price, qty, order_id),
        features_snapshot=feats,
        order_id=order_id, fill_id=fill_id, qty_filled=qty,
        ts_arrival=ts_arrival, ts_send=None, ts_fill=ts,
        P_arrival=p_arr, P_fill=price,
        P_mid_arrival=None, P_mid_fill=None, P_mid_fill_h=None,
        P_bid_fill=None, P_ask_fill=None,
        fee_comm=fee, fee_funding=None,
        impact_horizon=impact_horizon,
        bench_quality="missing",
        tca_variant="arrival_plus_fees")


def journal_opens(journal, opens: list[dict], *, ts: datetime | None = None) -> int:
    """Écrit les ouvertures exploitables. `opens` : dicts {symbol, venue, asset_class, fill, features,
    regime}. Retourne le nombre de trades RÉELLEMENT journalisés (fills valides)."""
    n = 0
    for o in opens:
        tr = build_open(o["symbol"], venue=o["venue"], asset_class=o.get("asset_class"),
                        fill=o.get("fill"), features=o.get("features"),
                        regime=o.get("regime"),
                        strategy=o.get("strategy") or "preset",
                        ts=ts, order_id=o.get("order_id"),
                        ts_arrival=o.get("ts_arrival"), P_arrival=o.get("P_arrival"),
                        fill_id=o.get("fill_id"),
                        impact_horizon=o.get("impact_horizon", "1bar"))
        if tr is not None:
            journal.append(tr, legacy=False)
            n += 1
    return n
