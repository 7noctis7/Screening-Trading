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


def _asset_class(sym: str, hint: str | None) -> AssetClass:
    """Classe d'actif : indice explicite du snapshot, sinon paires crypto = présence d'un '/'."""
    if hint:
        try:
            return AssetClass(hint)
        except ValueError:
            pass
    return AssetClass.CRYPTO if "/" in (sym or "") else AssetClass.EQUITY


def feature_map(snap: dict) -> dict[str, dict]:
    """Extrait, du snapshot de DÉCISION, les features PAR SYMBOLE (score + contributions factorielles).

    Source unique = `snap["screener"]["rows"]` (déjà calculé à la décision). Le poids cible et le
    contexte de régime sont ajoutés côté appelant (propres à l'ordre / au run)."""
    out: dict[str, dict] = {}
    for row in (snap.get("screener") or {}).get("rows", []):
        sym = row.get("symbol")
        if not sym:
            continue
        feats = {"rank_score": row.get("score")}
        feats.update(row.get("factors") or {})
        out[sym] = feats
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


def build_open(symbol: str, *, venue: str, asset_class: str | None, fill: dict | None,
               features: dict | None, regime: str | None = None,
               strategy: str = "preset", ts: datetime | None = None) -> TradeRecord | None:
    """TradeRecord d'ouverture (`legacy=0`), ou None si le fill est inexploitable (prix/qté ≤ 0).

    `id` DÉTERMINISTE par (jour, broker, symbole) → l'UPSERT du journal rend le re-run du même jour
    idempotent (jamais de doublon). `features_snapshot` = uniquement des floats finis (JSON/ML-safe)."""
    ts = ts or datetime.now(timezone.utc)
    price = float((fill or {}).get("avg_price") or 0.0)
    qty = float((fill or {}).get("qty") or 0.0)
    if price <= 0 or qty <= 0:
        return None
    feats = {k: round(float(v), 6) for k, v in (features or {}).items()
             if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v}
    return TradeRecord(
        id=f"P-{ts.strftime('%Y%m%d')}-{venue}-{symbol}",
        instrument=symbol, asset_class=_asset_class(symbol, asset_class),
        venue=venue, side=Side.LONG, qty=qty, entry_ts=ts, entry_price=price, avg_price=price,
        entry_reason="reconciliation paper (open/add)", regime=regime, strategy=strategy,
        features_snapshot=feats)


def journal_opens(journal, opens: list[dict], *, ts: datetime | None = None) -> int:
    """Écrit les ouvertures exploitables. `opens` : dicts {symbol, venue, asset_class, fill, features,
    regime}. Retourne le nombre de trades RÉELLEMENT journalisés (fills valides)."""
    n = 0
    for o in opens:
        tr = build_open(o["symbol"], venue=o["venue"], asset_class=o.get("asset_class"),
                        fill=o.get("fill"), features=o.get("features"),
                        regime=o.get("regime"), ts=ts)
        if tr is not None:
            journal.append(tr, legacy=False)
            n += 1
    return n
