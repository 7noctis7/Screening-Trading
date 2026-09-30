"""Sleeve swing paper — producteur d'ordres géométriques (Arch A1).

Paper-only. Convertit les propositions `MarketStructureEngine.detecter` (SFP/OTE)
en dicts compatibles contrat QT §C.1 (`strategy="swing"`). Ne lit PAS le flag
lui-même côté `build_swing_orders` : le caller gate via `swing_paper_enabled()`.

Arch A2 : `attach_swing_orders` câble `live.swing_orders` depuis le snapshot.
`QUANT_SWING_PAPER` défaut OFF — bit-identique preset sans flag. Capital via
`QUANT_SWING_NAV_PCT` (fraction NAV, défaut 0) et `QUANT_SWING_MAX_NAMES` (défaut 5).

Arch A3 : `load_swing_orders` + union `run_live` (preset `proteger` sleeve, second
pass `liquider_hors_cible=False`). `weight_pct` = fraction 0–1 (`notionnel/denom`).
Protection multi-jour via journal = PR4 (pas ici).

Capital A : sizing sur `equity_sleeve` (poche isolée) ; le consommateur (run_live)
unionne sans muter les poids preset.

IPA (institutional_price_action) : hors A1 — mapping ultérieur ; v1 = SFP/OTE
depuis `moteur_swing` uniquement. Pas d'`evaluate_setup`, pas de `p_calibrated` /
`expectancy_R` / `gain_attendu` inventés.
"""

from __future__ import annotations

import math
import os
from typing import Any

from packages.execution.routing import route
from packages.strategies.moteur_swing import MarketStructureEngine, RiskManager

_SETUPS_V1 = frozenset({"SFP", "OTE"})
_FLAG_ON = frozenset({"1", "true", "yes"})


def swing_paper_enabled() -> bool:
    """True uniquement si ``QUANT_SWING_PAPER`` ∈ {1, true, yes} (case-insensitive).

    Défaut OFF : variable absente / 0 / false / autre → False.
    """
    raw = os.environ.get("QUANT_SWING_PAPER", "")
    return str(raw).strip().lower() in _FLAG_ON



def swing_nav_pct() -> float:
    """``QUANT_SWING_NAV_PCT`` : fraction de NAV pour la poche sleeve (défaut 0).

    Même convention que ``QUANT_CRYPTO_PCT`` : 0.05 = 5 %. Illisible / absent → 0.
    Borné à [0, 1].
    """
    raw = os.environ.get("QUANT_SWING_NAV_PCT", "0")
    try:
        v = float(str(raw).strip() or "0")
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return max(0.0, min(1.0, v))


def swing_max_names() -> int:
    """``QUANT_SWING_MAX_NAMES`` : cap lignes sleeve / snap (défaut 5). Illisible → 5."""
    raw = os.environ.get("QUANT_SWING_MAX_NAMES", "5")
    try:
        n = int(str(raw).strip() or "5")
    except (TypeError, ValueError):
        return 5
    return n if n > 0 else 5


def _fini(x: Any) -> bool:
    try:
        return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _geometrie_ok(sens: str, entry: float, stop: float, target: float | None) -> bool:
    """Long ⇒ S < E (< T si cible) ; short ⇒ (T <) E < S ; distance > 0."""
    if entry <= 0 or abs(entry - stop) <= 0:
        return False
    if sens == "long":
        if not (stop < entry):
            return False
        if target is not None and not (entry < target):
            return False
    elif sens == "short":
        if not (stop > entry):
            return False
        if target is not None and not (target < entry):
            return False
    else:
        return False
    return True


def build_swing_orders(
    bars_by_sym: dict[str, list] | None,
    *,
    equity_sleeve: float,
    ts_decision: str,
    max_names: int = 5,
    long_only: bool = True,
    equity_nav: float | None = None,
    engine: MarketStructureEngine | None = None,
    risk: RiskManager | None = None,
    asset_class_by_sym: dict[str, str] | None = None,
) -> list[dict]:
    """Produit des ordres sleeve swing (pure ; ne lit pas ``QUANT_SWING_PAPER``).

    Pour chaque symbole (ordre trié) avec barres : ``detecter`` → skip si
    ``contradiction`` ; pour chaque prop SFP/OTE (long-only v1) → ``RiskManager.taille``
    → dict contrat §C.1. Cap ``max_names``. Skip silencieux si géométrie / sizing invalides.
    """
    if not ts_decision or not str(ts_decision).strip():
        return []
    if not bars_by_sym:
        return []
    try:
        max_n = int(max_names)
    except (TypeError, ValueError):
        max_n = 5
    if max_n <= 0:
        return []

    eng = engine if engine is not None else MarketStructureEngine()
    rm = risk if risk is not None else RiskManager()
    acmap = asset_class_by_sym or {}
    ts = str(ts_decision).strip()
    orders: list[dict] = []

    for sym in sorted(bars_by_sym.keys()):
        if len(orders) >= max_n:
            break
        bars = bars_by_sym.get(sym)
        if not bars:
            continue
        det = eng.detecter(sym, bars)
        if det.get("contradiction"):
            continue
        for prop in det.get("propositions") or []:
            if len(orders) >= max_n:
                break
            order = _prop_to_order(
                sym, prop, equity_sleeve=equity_sleeve, equity_nav=equity_nav,
                ts_decision=ts, long_only=long_only, rm=rm, acmap=acmap,
            )
            if order is not None:
                orders.append(order)
    return orders


def _prop_to_order(
    sym: str,
    prop: dict,
    *,
    equity_sleeve: float,
    equity_nav: float | None,
    ts_decision: str,
    long_only: bool,
    rm: RiskManager,
    acmap: dict[str, str],
) -> dict | None:
    scenario = str(prop.get("scenario") or "").strip().upper()
    if scenario not in _SETUPS_V1:
        return None
    sens = str(prop.get("sens") or "").strip().lower()
    if long_only and sens != "long":
        return None
    if sens not in ("long", "short"):
        return None

    if not _fini(prop.get("entree")) or not _fini(prop.get("stop")):
        return None
    entry = float(prop["entree"])
    stop = float(prop["stop"])

    target: float | None = None
    if _fini(prop.get("cible")):
        target = float(prop["cible"])
    rr_val: float | None = None
    if _fini(prop.get("rr")):
        rr_val = float(prop["rr"])
    if target is None and rr_val is None:
        return None
    if not _geometrie_ok(sens, entry, stop, target):
        return None

    sized = rm.taille(float(equity_sleeve), prop)
    qty = float(sized.get("quantite") or 0.0)
    risque = sized.get("risque_devise")
    notionnel = sized.get("notionnel")
    if qty <= 0 or not _fini(risque) or float(risque) <= 0:
        return None
    if not _fini(notionnel) or float(notionnel) <= 0:
        return None
    notionnel_f = float(notionnel)
    risk_dollar = float(risque)

    ac = acmap.get(sym, "")
    r = route(sym, ac)
    out: dict[str, Any] = {
        "symbol": sym,
        "strategy": "swing",
        "setup_id": scenario,
        "side": sens,
        "entry": entry,
        "stop": stop,
        "ts_decision": ts_decision,
        "qty": qty,
        "notionnel": notionnel_f,
        "risk_$": risk_dollar,
        "broker": r["broker"],
        "broker_symbol": r["broker_symbol"],
        "tradeable": r["tradeable"],
    }
    if target is not None:
        out["target"] = target
    if rr_val is not None:
        out["rr"] = rr_val
    denom = float(equity_nav) if (equity_nav is not None and _fini(equity_nav) and float(equity_nav) > 0) \
        else float(equity_sleeve)
    if _fini(denom) and denom > 0:
        out["weight_pct"] = notionnel_f / denom  # fraction 0–1 (run_live._broker_targets)
    if ac:
        out["asset_class"] = ac
    return out


def swing_bars_by_sym(symbols, data_or_series) -> dict[str, list]:
    """Extrait les listes de barres OHLC pour ``symbols`` depuis le cache snapshot.

    ``data`` snapshot = ``dict[str, list[Bar]]`` (attributs ``.open/.high/.low/.close/.volume``)
    — passé tel quel au moteur. Dict-bars chart (clés o/h/l/c) non convertis ici :
    préférer le cache ``data`` Bar-objets. Symbole absent / liste vide → omis.
    """
    out: dict[str, list] = {}
    src = data_or_series or {}
    for s in symbols or []:
        if not s:
            continue
        bars = src.get(s) if hasattr(src, "get") else None
        if bars:
            out[str(s)] = bars
    return out



def load_swing_orders(snap: dict) -> list[dict]:
    """Charge `live.swing_orders` si flag ON ; sinon ``[]`` (chemin preset inchangé).

    Assure ``strategy="swing"`` sur chaque ligne. Normalisation ``weight_pct``
    fraction (notionnel/cap) est faite côté ``run_live.main`` après ``alp_cap``.
    """
    if not swing_paper_enabled():
        return []
    live = (snap or {}).get("live") or {}
    raw = live.get("swing_orders") or []
    out: list[dict] = []
    for o in raw:
        if not isinstance(o, dict):
            continue
        row = dict(o)
        row.setdefault("strategy", "swing")
        if not row.get("strategy"):
            row["strategy"] = "swing"
        out.append(row)
    return out


def attach_swing_orders(
    live: dict,
    *,
    bars_by_sym: dict[str, list] | None,
    equity_nav: float,
    ts_decision: str,
    rank_scores: dict[str, float] | None = None,
    asset_class_by_sym: dict[str, str] | None = None,
) -> None:
    """Pose ``live["swing_orders"]`` selon flags env (Arch A2). Mutates ``live``.

    - Flag OFF → ``[]`` (clé toujours présente ; preset ``target_orders`` intouché).
    - Flag ON + ``QUANT_SWING_NAV_PCT`` ≤ 0 → ``[]`` (pas de capital inventé).
    - Flag ON + pct > 0 → ``build_swing_orders`` sur ``bars_by_sym`` (best-effort :
      ``{}`` → ``[]``). Rank optionnel (≠ p). N'invente jamais expectancy / p.
    """
    if not isinstance(live, dict):
        return
    if not swing_paper_enabled():
        live["swing_orders"] = []
        return
    pct = swing_nav_pct()
    try:
        nav = float(equity_nav)
    except (TypeError, ValueError):
        nav = 0.0
    if pct <= 0.0 or not math.isfinite(nav) or nav <= 0.0:
        live["swing_orders"] = []
        return
    equity_sleeve = nav * pct
    orders = build_swing_orders(
        bars_by_sym,
        equity_sleeve=equity_sleeve,
        equity_nav=nav,
        ts_decision=ts_decision,
        max_names=swing_max_names(),
        asset_class_by_sym=asset_class_by_sym,
    )
    if rank_scores:
        for o in orders:
            sym = o.get("symbol")
            sc = rank_scores.get(sym) if sym else None
            if isinstance(sc, (int, float)) and not isinstance(sc, bool) and sc == sc:
                o["rank_score"] = round(float(sc), 6)
    live["swing_orders"] = orders
