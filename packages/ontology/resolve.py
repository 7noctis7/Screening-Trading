"""Résolveurs d'objets métiers — projections PURES du snapshot (aucun recalcul, aucun réseau).

Chaque résolveur : (snap, id) -> dict {type, id, ...champs, relations{...}} ou None si inconnu.
Registre extensible : ajouter un objet = ajouter une fonction + une entrée OBJECT_TYPES.
"""

from __future__ import annotations


def _rows(snap: dict, section: str) -> list[dict]:
    sec = snap.get(section) or {}
    return sec.get("rows") or []


def _find(rows: list[dict], key: str, value: str) -> dict | None:
    for r in rows:
        if (r.get(key) or "").upper() == value.upper():
            return r
    return None


def _norm(s: str) -> str:
    """BTC/USD ↔ BTCUSD ↔ BTC-USD : même instrument, formats de venue différents."""
    return (s or "").upper().replace("/", "").replace("-", "").removesuffix("USDT") \
        .removesuffix("USDC").removesuffix("USD")


def resolve_instrument(snap: dict, sym: str) -> dict | None:
    """Instrument 360 : identité + ses relations (score, fondamental, sentiment, position, note)."""
    dash = snap.get("dashboard") or {}
    scr = _find(_rows(snap, "screen"), "symbol", sym) or {}
    rank = _find(_rows(snap, "screener"), "symbol", sym) or {}
    fund = _find(_rows(snap, "fundamentals"), "symbol", sym) or {}
    sent = _find(_rows(snap, "sentiment"), "symbol", sym) or {}
    pos = next((p for p in dash.get("real_positions") or []
                if _norm(p.get("symbol", "")) == _norm(sym)), None)
    tgt = next((o for o in (snap.get("live") or {}).get("target_orders") or []
                if _norm(o.get("symbol", "")) == _norm(sym)), None)
    known = any([scr, rank, fund, sent, pos, tgt])
    if not known:
        return None
    return {
        "type": "instrument", "id": sym.upper(),
        "name": scr.get("name") or fund.get("name") or sym.upper(),
        "sector": scr.get("sector") or fund.get("sector"),
        "asset_class": scr.get("asset_class") or (tgt or {}).get("asset_class"),
        "relations": {
            "screen": scr or {"available": False},          # filtres + score composite
            "ranking": rank or {"available": False},         # z-scores factoriels (explicabilité)
            "fundamentals": fund or {"available": False},    # DCF/Piotroski/Altman
            "sentiment": sent or {"available": False},       # news/FinBERT
            "position": pos or {"available": False},         # détenu RÉEL (broker)
            "target": tgt or {"available": False},           # poids cible du preset
        },
    }


def resolve_portfolio(snap: dict, _id: str = "main") -> dict | None:
    """Portefeuille 360 : cible vs réel + risque + régime — l'objet central de la page unique."""
    dash = snap.get("dashboard") or {}
    if not dash:
        return None
    port = snap.get("portfolio") or {}
    return {
        "type": "portfolio", "id": "main",
        "regime": dash.get("regime") or {"available": False},
        "metrics": dash.get("metrics") or {"available": False},
        "relations": {
            "targets": (snap.get("live") or {}).get("target_orders") or [],
            "positions": dash.get("real_positions") or [],
            "risk": (port.get("analysis") or {}).get("limits") or {"available": False},
            "honesty": dash.get("honesty") or {"available": False},
        },
    }


OBJECT_TYPES = {
    "instrument": resolve_instrument,
    "portfolio": resolve_portfolio,
}


def resolve(snap: dict, obj_type: str, obj_id: str) -> dict | None:
    """Point d'entrée unique : (type, id) → objet + relations, ou None (type/id inconnu)."""
    fn = OBJECT_TYPES.get(obj_type)
    return fn(snap, obj_id) if fn else None
