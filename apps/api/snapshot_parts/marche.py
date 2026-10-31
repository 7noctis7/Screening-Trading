"""Marché : thèmes, section données, VIX, scores de classement.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from apps.api.snapshot_parts.base import ROOT
from apps.api.snapshot_parts.univers import _setup_label, is_real_mode
from packages.common import load_yaml


def _themes_section(data: dict, sector_of: dict, end) -> dict:
    """Thèmes de marché calculés depuis les MÊMES données que le trading → cohérence
    positions ↔ secteurs. YTD = perf CALENDAIRE réelle (depuis le 1ᵉʳ janvier) ; garde-fou
    anti-glitch (saut > 150 %/j écarté). Meilleurs setups par secteur (momentum + tendance vs MM50).
    Seuls les secteurs « investissables »
    (4ᵉ révolution + GICS, hors forex/indices/etf) alimentent la heatmap d'actifs."""
    import numpy as np

    from packages.data.corporate_actions import ajuster as _ca_ajuster
    from packages.data.corporate_actions import exploitable as _ca_exploitable

    skip = {"Forex", "Indices", "ETF", "Commodités"}
    _splits_ajustes: list[str] = []      # publiés : un ajustement silencieux n'est pas auditable
    _splits_ecartes: list[str] = []
    buckets: dict[str, list] = {}
    for s, bars in data.items():
        sec = sector_of.get(s, "Actions diverses")
        if sec in skip:
            continue
        buckets.setdefault(sec, []).append((s, bars))
    out = []
    for sec, items in buckets.items():
        if len(items) < 3:
            continue
        assets = []
        _cur_year = end.year
        for s, bars in items:
            c = np.array([b.close for b in bars], float)
            if c.size < 64:
                continue
            # GARDE-FOU DATA. Le seuil de 150 % attrape les REGROUPEMENTS (1:10 = +900 %) mais
            # laissait passer les SPLITS : un 4:1 fait -75 %, donc sous le seuil. C'était le cas
            # fréquent, et il frappe les valeurs qui ont beaucoup monté — celles que le momentum
            # sélectionne. Détection dédiée (packages/data/corporate_actions) : on ajuste quand
            # prix ET volume concordent, on ÉCARTE quand le doute subsiste. Jamais de rendement
            # inventé au milieu d'un historique.
            rr = c[1:] / c[:-1] - 1.0
            if rr.size and (np.nanmax(np.abs(rr)) > 1.5 or not np.all(np.isfinite(c)) or c.min() <= 0):
                continue
            _vols = [float(getattr(b, "volume", 0.0) or 0.0) for b in bars]
            _ok, _motif = _ca_exploitable([float(x) for x in c], _vols)
            if not _ok:
                _splits_ecartes.append(f"{s} : {_motif}")
                continue
            _c_adj, _cands = _ca_ajuster([float(x) for x in c], _vols)
            if any(x.certain for x in _cands):
                c = np.array(_c_adj, float)
                _splits_ajustes.append(f"{s} : {sum(1 for x in _cands if x.certain)} split(s)")
            # YTD CALENDAIRE RÉEL : base = dernier cours de l'année précédente (sinon 1ʳᵉ barre dispo)
            _bidx = next((i for i, b in enumerate(bars) if b.ts.year == _cur_year), None)
            base = bars[_bidx - 1].close if (_bidx and _bidx > 0) else float(c[0])
            ytd = float(c[-1] / base - 1.0) if base > 0 else 0.0
            mom = float(c[-1] / c[-63] - 1.0)                    # ~3 mois
            sma50 = float(c[-50:].mean())
            trend = float((c[-1] - sma50) / sma50)
            assets.append({"symbol": s, "ytd": round(ytd, 4), "momentum": round(mom, 4),
                           "trend": round(trend, 4), "setup_score": round(0.6 * mom + 0.4 * trend, 4),
                           "setup": _setup_label(mom, trend)})
        if len(assets) < 3:
            continue
        # MÉDIANE (pas moyenne) → robuste : une seule valeur extrême (COIN/MSTR +1000 %
        # ou glitch de base passé sous le garde-fou) ne fait plus exploser le secteur.
        ytd_sec = float(np.median([a["ytd"] for a in assets]))
        mom_sec = float(np.median([a["momentum"] for a in assets]))
        stance = "bullish" if ytd_sec > 0.05 else "bearish" if ytd_sec < -0.05 else "neutral"
        top = sorted(assets, key=lambda a: a["setup_score"], reverse=True)[:4]
        out.append({"sector": sec, "ytd": round(ytd_sec, 4), "momentum": round(mom_sec, 4),
                    "stance": stance, "n": len(assets), "top_assets": top})
    out.sort(key=lambda s: s["ytd"], reverse=True)
    return {
        "as_of": end.isoformat(),
        "splits_ajustes": _splits_ajustes,     # ce qui a été corrigé, et sur quels titres
        "splits_ecartes": _splits_ecartes,     # ce qui n'a pas pu être tranché → titre écarté
        "sectors": out,
        "bullish": [s["sector"] for s in out if s["stance"] == "bullish"],
        "bearish": [s["sector"] for s in out if s["stance"] == "bearish"],
        "stance_by_sector": {s["sector"]: s["stance"] for s in out},
    }


def _data_section(data: dict, acmap: dict[str, str], universe_total: int = 0,
                  mode: str = "synthetic") -> dict:
    """Vue DONNÉES : collecte (providers, barres, qualité) + couches de base de données."""
    import pandas as pd

    from packages.storage.quality import validate_ohlcv

    symbols = list(data)
    collection = []
    for s in symbols:
        bars = data[s]
        collection.append({
            "symbol": s, "asset_class": acmap.get(s, ""), "bars": len(bars),
            "start": bars[0].ts.isoformat(), "end": bars[-1].ts.isoformat(),
            "last_close": round(bars[-1].close, 2),
        })
    first = symbols[0]
    bars = data[first]
    df = pd.DataFrame(
        [{"open": b.open, "high": b.high, "low": b.low,
          "close": b.close, "volume": b.volume} for b in bars],
        index=pd.DatetimeIndex([b.ts for b in bars]))
    rep = validate_ohlcv(df, first, "1d", max_gap_ratio=0.5)
    from packages.storage.data_health import health_report
    health = health_report(data, acmap)
    # AUDIT PwC complet (complétude / exactitude / point-in-time) — toujours calculé sur données
    # réelles pour affichage (la gate bloquante reste séparée, pilotée par QUANT_AUDIT). Best-effort.
    audit_summary: dict | None = None
    if is_real_mode(mode):
        try:
            from packages.data.audit import audit_and_report
            _ar = audit_and_report(data, universe=symbols)
            audit_summary = _ar.to_dict()
        except Exception:  # noqa: BLE001 — affichage non critique
            audit_summary = None
    # SPC / Six Sigma : taux de défaut OHLCV sur TOUT le panel → DPMO + niveau sigma.
    # Défaut = barre non conforme (high<low, prix≤0, volume<0, ou NaN). Best-effort.
    spc_block: dict = {"available": False}
    try:
        from packages.data.spc import dpmo, p_chart, sigma_level
        total, bad = 0, 0
        for _bars in data.values():
            for b in _bars:
                total += 1
                ok = (b.high >= b.low and b.open > 0 and b.low > 0 and b.close > 0
                      and b.volume >= 0 and b.close == b.close and b.high == b.high)
                if not ok:
                    bad += 1
        _d = dpmo(bad, total)
        spc_block = {"available": True, "p_chart": p_chart(bad, total),
                     "dpmo": round(_d, 2), "sigma_level": sigma_level(_d),
                     "checks": "high>=low, prix>0, volume>=0, non-NaN",
                     "target_dpmo": 3.4}
    except Exception:  # noqa: BLE001 — affichage non critique
        spc_block = {"available": False}
    src_cfg = load_yaml(ROOT / "config" / "data_sources.yaml")
    return {
        "as_of": data[first][-1].ts.isoformat(),
        "health": health,
        "spc": spc_block,                                   # SPC / Six Sigma (qualité pipeline)
        "symbols_total": len(symbols),
        "universe_total": universe_total or len(symbols),   # total disponible (29k si YAHOO.db)
        "provider": mode,                                   # vrai mode des données (réel / mixte / synthétique)
        "fallback_order": src_cfg.get("ohlcv", {}).get("fallback_order", []),
        "fundamentals_provider": src_cfg.get("fundamentals", {}).get("provider"),
        "cache": src_cfg.get("ohlcv", {}).get("cache"),
        "collection": collection,
        "total_bars": sum(c["bars"] for c in collection),
        "quality": {"symbol": rep.symbol, "n_rows": rep.n_rows, "ok": rep.ok,
                    "errors": rep.errors, "warnings": rep.warnings},
        "audit": audit_summary,                             # rapport PwC : ok, compteurs, anomalies
        "layers": [
            {"name": "Bronze — barres brutes", "store": "bars_repo · duckdb_bars_repo",
             "desc": "OHLCV ingéré par symbole/timeframe, validé par contrats qualité"},
            {"name": "Silver — features", "store": "feature_store",
             "desc": "indicateurs & facteurs calculés, versionnés (anti-fuite)"},
            {"name": "Gold — journal & univers", "store": "journal · universe_repo · macro_store",
             "desc": "trades clôturés, snapshots d'univers datés, macro point-in-time"},
            {"name": "Sauvegardes", "store": "backup",
             "desc": "sauvegarde / restauration des stores"},
        ],
    }


def _vix_series(n: int, seed: int = 0) -> list:
    """Indice de volatilité (VIX) synthétique : retour à la moyenne ~16 + pics occasionnels.
    Sert au playbook volatilité et à la modulation d'exposition du backtest."""
    import numpy as np
    rng = np.random.default_rng(seed + 99)
    v = [16.0]
    for _ in range(1, n):
        x = v[-1] + 0.05 * (15.0 - v[-1]) + rng.normal(0, 1.1)
        if rng.random() < 0.004:                 # pic de stress
            x += rng.uniform(8, 22)
        v.append(min(75.0, max(9.0, x)))
    return [round(float(x), 2) for x in v]


# Playbook rendu quand aucune série VIX RÉELLE n'est disponible. `exposure` vaut 1.0 :
# une valeur neutre, jamais un multiplicateur inventé qui modulerait le risque.
_VIX_NON_CALIBRE = {
    "regime": "UNCALIBRATED", "color": "#6b7280", "exposure": 1.0,
    "action": ("Aucune série VIX réelle disponible (ni `^VIX` ni `VIX`, "
               "fraîcheur ≤ 7 j). Pas de lecture de volatilité : on n'en "
               "invente pas. Vérifier la base de prix ou le réseau."),
}


def _vix_playbook(v: float) -> dict:
    if v < 13:
        return {"regime": "calme", "color": "#22c55e", "exposure": 1.2,
                "action": "Marché haussier calme : on pousse l'exposition, prises de profits partielles, protections (puts) peu chères à accumuler."}
    if v < 20:
        return {"regime": "normal", "color": "#3b82f6", "exposure": 1.0,
                "action": "Volatilité normale : exposition cible, on suit les setups et la discipline de risque."}
    if v < 30:
        return {"regime": "tendu", "color": "#f59e0b", "exposure": 0.6,
                "action": "Stress qui monte : on réduit le levier, on resserre les stops, on garde de la poudre sèche."}
    return {"regime": "panique", "color": "#f43f5e", "exposure": 0.3,
            "action": "Pic de peur : on coupe le levier (défensif). On prépare des achats sur les actions solides quand le VIX montre des signes de fatigue ; toute spéculation directe sur le VIX se solde vite."}


def _rank_score_map(screener: dict | None, screen: dict | None,
                    ml_scores: dict | None = None) -> dict[str, float]:
    """Scores decision-time par symbole — jamais inventés.

    Priorité (dernier gagne) : ml → screen.rows → screener.rows. Seuls les floats
    finis sont retenus ; absence = pas de clé (pas de None silencieux)."""
    out: dict[str, float] = {}
    for sym, sc in (ml_scores or {}).items():
        if isinstance(sc, bool) or not isinstance(sc, (int, float)) or sc != sc:
            continue
        if sym:
            out[sym] = float(sc)
    for row in (screen or {}).get("rows", []) or []:
        sym, sc = row.get("symbol"), row.get("score")
        if not sym or isinstance(sc, bool) or not isinstance(sc, (int, float)) or sc != sc:
            continue
        out[sym] = float(sc)
    for row in (screener or {}).get("rows", []) or []:
        sym, sc = row.get("symbol"), row.get("score")
        if not sym or isinstance(sc, bool) or not isinstance(sc, (int, float)) or sc != sc:
            continue
        out[sym] = float(sc)
    return out


def _attach_rank_scores(orders: list | None, scores: dict[str, float]) -> None:
    """Attache `rank_score` float sur chaque ordre quand dispo ; omet la clé sinon."""
    for o in orders or []:
        sym = o.get("symbol")
        sc = scores.get(sym) if sym else None
        if isinstance(sc, (int, float)) and not isinstance(sc, bool) and sc == sc:
            o["rank_score"] = round(float(sc), 6)
        else:
            o.pop("rank_score", None)  # jamais None écrit
