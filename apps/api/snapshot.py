"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.api import payloads as PL
from packages.backtest.fast_swing import fast_swing_backtest
from packages.common import load_yaml
from packages.data import data_providers
from packages.execution import CostModel
from packages.portfolio import (attribution, correlation_matrix, cluster, expert_review,
                                mc_projection, monte_carlo, relative_metrics, risk_metrics_fn)
from packages.portfolio.metrics import returns_from_equity
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.storage import MacroStore

ROOT = Path(__file__).resolve().parents[2]
_NETWORK_KINDS = {"wikipedia", "ishares_holdings", "nasdaq_trader", "coingecko"}
_HISTORY_DAYS = 1700        # ~4,6 ans d'historique jusqu'à aujourd'hui


def _seed_universe() -> list[dict]:
    """Univers COMPLET dédupliqué (par symbole) à partir des seeds — source unique."""
    seen: dict[str, dict] = {}
    for path in sorted((ROOT / "data" / "seed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sym = (r.get("symbol") or "").strip()
                if sym and sym not in seen:
                    seen[sym] = {
                        "symbol": sym, "name": r.get("name") or "",
                        "asset_class": (r.get("asset_class") or "equity").strip() or "equity",
                        "venue": r.get("venue") or "", "currency": r.get("currency") or "",
                        "sector": r.get("sector") or "", "source": path.stem,
                    }
    return list(seen.values())


def _universe_section(instruments: list[dict]) -> dict:
    """Vue UNIVERS : sources déclarées (offline/réseau), seeds, répartition par classe."""
    cfg = load_yaml(ROOT / "config" / "universe.yaml")
    src_rows = []
    for s in cfg.get("sources", []):
        kind = s.get("kind")
        src_rows.append({
            "id": s.get("id"), "kind": kind,
            "enabled": bool(s.get("enabled", True)),
            "network": kind in _NETWORK_KINDS,
            "detail": s.get("file") or s.get("url") or "",
        })
    by_class, by_venue = {}, {}
    for r in instruments:
        ac = (r.get("asset_class") or "?").strip() or "?"
        by_class[ac] = by_class.get(ac, 0) + 1
        ven = (r.get("venue") or "?").strip() or "?"
        by_venue[ven] = by_venue.get(ven, 0) + 1
    seeds = []
    for path in sorted((ROOT / "data" / "seed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            cnt = sum(1 for _ in csv.DictReader(f))
        seeds.append({"file": path.name, "count": cnt,
                      "as_of": datetime.fromtimestamp(path.stat().st_mtime,
                                                      timezone.utc).isoformat()})
    rows = sorted(instruments, key=lambda r: (r["asset_class"], r["symbol"]))
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "rebuild_cadence_days": cfg.get("rebuild_cadence_days"),
        "sources": src_rows,
        "sources_enabled": sum(1 for s in src_rows if s["enabled"]),
        "sources_total": len(src_rows),
        "seeds": seeds,
        "seed_total": len(instruments),
        "by_asset_class": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "by_venue": dict(sorted(by_venue.items(), key=lambda kv: -kv[1])[:12]),
        "instruments": rows,                  # UNIVERS COMPLET (pas un échantillon)
        "instruments_total": len(rows),
    }


# Thèmes structurels (4ᵉ révolution industrielle, K. Schwab) + secteurs classiques.
# Chaque thème : panier de proxies + biais de drift/vol thématique (synthétique, reproductible).
_SECTORS = {
    # --- 4ᵉ révolution industrielle --- (drifts ANNUELS modérés → réalistes sur ~4,6 ans)
    "Intelligence artificielle":     {"tickers": ["NVDA", "MSFT", "GOOGL", "PLTR", "SNOW"], "drift": 0.16, "vol": 0.24},
    "Semi-conducteurs":              {"tickers": ["NVDA", "TSM", "AVGO", "AMD", "ASML"],    "drift": 0.15, "vol": 0.26},
    "Crypto & Blockchain":           {"tickers": ["COIN", "MSTR", "MARA", "RIOT", "HUT"],   "drift": 0.14, "vol": 0.45},
    "Cloud & Datacenters":           {"tickers": ["MSFT", "AMZN", "GOOGL", "EQIX", "DLR"],  "drift": 0.12, "vol": 0.18},
    "Cybersécurité":                 {"tickers": ["CRWD", "PANW", "ZS", "FTNT", "S"],       "drift": 0.11, "vol": 0.22},
    "Espace & Défense":              {"tickers": ["LMT", "RTX", "BA", "NOC", "RKLB"],       "drift": 0.08, "vol": 0.20},
    "Robotique & Automatisation":    {"tickers": ["ABB", "ISRG", "ROK", "TER", "FANUY"],    "drift": 0.07, "vol": 0.18},
    "Véhicules électriques":         {"tickers": ["TSLA", "RIVN", "LCID", "BYDDY", "NIO"],  "drift": 0.02, "vol": 0.40},
    "Fintech & Paiements":           {"tickers": ["V", "MA", "PYPL", "SQ", "ADYEY"],        "drift": 0.05, "vol": 0.20},
    "Biotech & Génomique":           {"tickers": ["LLY", "VRTX", "REGN", "CRSP", "MRNA"],   "drift": 0.02, "vol": 0.24},
    "Énergie propre & Transition":   {"tickers": ["ENPH", "FSLR", "NEE", "PLUG", "BE"],     "drift": -0.04, "vol": 0.30},
    # --- secteurs GICS classiques ---
    "Énergie (fossile)":             {"tickers": ["XOM", "CVX", "COP", "SLB", "EOG"],       "drift": 0.06, "vol": 0.18},
    "Industrie":                     {"tickers": ["CAT", "GE", "HON", "UPS", "DE"],         "drift": 0.05, "vol": 0.16},
    "Conso. de base":                {"tickers": ["PG", "KO", "PEP", "COST", "WMT"],        "drift": 0.04, "vol": 0.12},
    "Finance":                       {"tickers": ["JPM", "BAC", "GS", "MS", "BLK"],         "drift": 0.03, "vol": 0.18},
    "Services publics":              {"tickers": ["DUK", "SO", "AEP", "D", "EXC"],          "drift": 0.01, "vol": 0.12},
}


# drift/vol par secteur (sert à générer les trajectoires synthétiques cohérentes)
_SECTOR_DV = {name: (cfg["drift"], cfg.get("vol", 0.18)) for name, cfg in _SECTORS.items()}
_SECTOR_DV.update({
    "Santé": (0.08, 0.16), "Conso. discrétionnaire": (0.10, 0.20),
    "Communication": (0.09, 0.18), "Matériaux": (0.05, 0.20), "Immobilier": (0.02, 0.18),
    "Actions diverses": (0.06, 0.20), "ETF": (0.07, 0.13), "Indices": (0.07, 0.12),
    "Forex": (0.00, 0.07), "Commodités": (0.05, 0.20),
})
# ticker → thème (4ᵉ révolution) pour étiqueter les actions des seeds européens/US
_THEME_TICKERS = {t: name for name, cfg in _SECTORS.items() for t in cfg["tickers"]}
# GICS (anglais, seeds CAC40/AEX) → bucket interne
_GICS_MAP = {
    "Information Technology": "Cloud & Datacenters", "Health Care": "Santé",
    "Financials": "Finance", "Consumer Discretionary": "Conso. discrétionnaire",
    "Consumer Staples": "Conso. de base", "Industrials": "Industrie",
    "Energy": "Énergie (fossile)", "Utilities": "Services publics",
    "Materials": "Matériaux", "Communication Services": "Communication",
    "Real Estate": "Immobilier",
}


def _sector_of(m: dict) -> str:
    """Secteur/thème d'un instrument (cohérent entre génération de données et heatmap)."""
    ac = m.get("asset_class")
    if ac == "crypto":
        return "Crypto & Blockchain"
    if ac == "forex":
        return "Forex"
    if ac == "commodity":
        return "Commodités"
    if ac == "index":
        return "Indices"
    if ac == "etf":
        return "ETF"
    if m["symbol"] in _THEME_TICKERS:
        return _THEME_TICKERS[m["symbol"]]
    sec = (m.get("sector") or "").strip()
    if sec in _SECTOR_DV:
        return sec
    return _GICS_MAP.get(sec, "Actions diverses")


def _setup_label(mom: float, trend: float) -> str:
    if mom > 0.05 and trend > 0.02:
        return "tendance haussière confirmée"
    if mom > 0.05 and trend <= 0.02:
        return "momentum naissant"
    if mom < -0.05 and trend < -0.02:
        return "tendance baissière"
    if trend > 0.02 and mom <= 0.05:
        return "rebond au-dessus de la MM50"
    return "neutre / range"


def _themes_section(data: dict, sector_of: dict, end) -> dict:
    """Thèmes de marché calculés depuis les MÊMES données que le trading → cohérence
    positions ↔ secteurs. YTD = performance sur les 365 derniers jours ; meilleurs
    setups par secteur (momentum + tendance vs MM50). Seuls les secteurs « investissables »
    (4ᵉ révolution + GICS, hors forex/indices/etf) alimentent la heatmap d'actifs."""
    import numpy as np

    skip = {"Forex", "Indices", "ETF", "Commodités"}
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
        for s, bars in items:
            c = np.array([b.close for b in bars], float)
            if c.size < 380:
                continue
            ytd = float(c[-1] / c[-252] - 1.0)                   # 12 derniers mois
            mom = float(c[-1] / c[-63] - 1.0)                    # ~3 mois
            sma50 = float(c[-50:].mean())
            trend = float((c[-1] - sma50) / sma50)
            assets.append({"symbol": s, "ytd": round(ytd, 4), "momentum": round(mom, 4),
                           "trend": round(trend, 4), "setup_score": round(0.6 * mom + 0.4 * trend, 4),
                           "setup": _setup_label(mom, trend)})
        if len(assets) < 3:
            continue
        ytd_sec = sum(a["ytd"] for a in assets) / len(assets)
        mom_sec = sum(a["momentum"] for a in assets) / len(assets)
        stance = "bullish" if ytd_sec > 0.05 else "bearish" if ytd_sec < -0.05 else "neutral"
        top = sorted(assets, key=lambda a: a["setup_score"], reverse=True)[:4]
        out.append({"sector": sec, "ytd": round(ytd_sec, 4), "momentum": round(mom_sec, 4),
                    "stance": stance, "n": len(assets), "top_assets": top})
    out.sort(key=lambda s: s["ytd"], reverse=True)
    return {
        "as_of": end.isoformat(),
        "sectors": out,
        "bullish": [s["sector"] for s in out if s["stance"] == "bullish"],
        "bearish": [s["sector"] for s in out if s["stance"] == "bearish"],
        "stance_by_sector": {s["sector"]: s["stance"] for s in out},
    }


def _data_section(data: dict, acmap: dict[str, str]) -> dict:
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
    src_cfg = load_yaml(ROOT / "config" / "data_sources.yaml")
    return {
        "as_of": data[first][-1].ts.isoformat(),
        "symbols_total": len(symbols),
        "provider": "synthetic",
        "fallback_order": src_cfg.get("ohlcv", {}).get("fallback_order", []),
        "fundamentals_provider": src_cfg.get("fundamentals", {}).get("provider"),
        "cache": src_cfg.get("ohlcv", {}).get("cache"),
        "collection": collection,
        "total_bars": sum(c["bars"] for c in collection),
        "quality": {"symbol": rep.symbol, "n_rows": rep.n_rows, "ok": rep.ok,
                    "errors": rep.errors, "warnings": rep.warnings},
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


def _live_section(positions: list, acmap: dict, kpis: dict | None = None) -> dict:
    """Portefeuille RÉEL : statut de connexion aux brokers (Alpaca actions, Bitmart crypto).
    Non connecté tant que les clés API ne sont pas fournies → ordres « cibles » à répliquer."""
    import os
    alp = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_API_SECRET"))
    bit = bool(os.environ.get("BITMART_API_KEY") and os.environ.get("BITMART_API_SECRET"))
    tot = sum(p["current_value"] for p in positions) or 1.0
    targets = []
    for p in positions:
        is_crypto = acmap.get(p["symbol"]) == "crypto"
        targets.append({"symbol": p["symbol"], "broker": "Bitmart" if is_crypto else "Alpaca",
                        "asset_class": acmap.get(p["symbol"], ""),
                        "weight_pct": round(p["current_value"] / tot, 4),  # allocation cible (%)
                        "side": p["side"]})
    return {
        "connected": alp or bit,
        # KPI réels seulement si un compte est connecté (sinon le portefeuille réel est vide)
        "portfolio": (kpis or {}) if (alp or bit) else {},
        "model_weights_only": not (alp or bit),
        "mode": "paper",                          # paper par défaut, JAMAIS d'ordre réel non confirmé
        "brokers": [
            {"name": "Alpaca", "scope": "Actions & ETF US", "connected": alp, "paper": True,
             "env": ["ALPACA_API_KEY", "ALPACA_API_SECRET"]},
            {"name": "Bitmart", "scope": "Crypto (paires /USDC)", "connected": bit, "paper": False,
             "env": ["BITMART_API_KEY", "BITMART_API_SECRET"]},
        ],
        "target_orders": targets,
        "note": "Brancher les clés API (variables d'environnement) puis valider en mode paper "
                "avant tout ordre réel. Les ordres cibles répliquent le portefeuille modèle.",
    }


def _auc(scores, y) -> float | None:
    import numpy as np
    y = np.asarray(y, float)[np.argsort(scores)]
    n_pos, n = y.sum(), len(y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = np.arange(1, n + 1)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _ml_section(data: dict, sector_of: dict, names: dict) -> dict:
    """Score ML d'edge (proba de hausse à ~1 mois) entraîné en CROSS-SECTION sur TOUT
    l'univers (régression logistique numpy pure, sans dépendance). Holdout temporel + AUC."""
    import numpy as np

    from packages.indicators.momentum import RSI
    from packages.indicators.trend import SMA
    from packages.indicators.volatility import ATR
    from packages.ml.model import LogitModel

    H = 21  # horizon ~1 mois (profil moyen-long terme)

    def feats(c, sma, rsi, atr, t):
        if t < 60 or t >= len(c) or sma[t] != sma[t] or rsi[t] != rsi[t] or atr[t] != atr[t]:
            return None
        return [c[t] / c[t - 20] - 1, c[t] / c[t - 60] - 1,
                (c[t] - sma[t]) / sma[t], rsi[t] / 100.0, atr[t] / c[t]]

    X, y, Xh, yh, last = [], [], [], [], {}
    for s, bars in data.items():
        c = np.array([b.close for b in bars], float)
        ncl = len(c)
        if ncl < 90 + H:
            continue
        sma, rsi, atr = SMA(50).compute(bars), RSI(14).compute(bars), ATR(14).compute(bars)
        split = ncl - 252                       # 1 an de holdout out-of-time
        for t in range(60, ncl - H, 5):
            f = feats(c, sma, rsi, atr, t)
            if f is None:
                continue
            lab = 1.0 if c[t + H] > c[t] else 0.0
            (X if t < split else Xh).append(f)
            (y if t < split else yh).append(lab)
        fl = feats(c, sma, rsi, atr, ncl - 1)
        if fl is not None:
            last[s] = fl
    if len(X) < 200:
        return {"available": False}
    model = LogitModel(epochs=400).fit(np.array(X), np.array(y))
    auc = _auc(model.predict_proba(np.array(Xh)), yh) if len(yh) > 50 else None
    probs = {s: float(model.predict_proba([f])[0]) for s, f in last.items()}
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:15]
    fn = ["momentum 1 mois", "momentum 3 mois", "tendance vs MM50", "RSI", "volatilité (ATR)"]
    imp = sorted(zip(fn, [abs(float(w)) for w in model.w]), key=lambda kv: -kv[1])
    return {
        "available": True, "model": "régression logistique (numpy)", "horizon_days": H,
        "n_train": len(X), "n_holdout": len(yh), "auc": round(auc, 3) if auc else None,
        "feature_importance": [{"feature": f, "weight": round(w, 3)} for f, w in imp],
        "top_conviction": [{"symbol": s, "name": names.get(s, ""),
                            "sector": sector_of.get(s, ""), "ml_score": round(p, 3)}
                           for s, p in top],
        "scores": {s: round(p, 3) for s, p in probs.items()},
    }


def _price_db_path() -> "Path | None":
    """Chemin d'une base de prix réelle. Priorité : env QUANT_PRICE_DB, puis emplacements
    usuels (data/, Bureau/Desktop) → branche automatiquement votre ~/Desktop/YAHOO.db."""
    import os
    env = os.environ.get("QUANT_PRICE_DB")
    if env and Path(env).exists():
        return Path(env)
    home = Path.home()
    for p in (ROOT / "data" / "YAHOO.db", ROOT / "data" / "market.db",
              home / "Desktop" / "YAHOO.db", home / "Bureau" / "YAHOO.db",
              home / "Desktop" / "market.db"):
        if p.exists():
            return p
    return None


def _load_prices(instruments, sector_of, start, end, seed):
    """Charge l'OHLCV : base RÉELLE (YAHOO.db…) en priorité, sinon synthétique sectorisé
    (et synthétique en complément pour les symboles absents de la base). Renvoie (data, mode)."""
    data, n_real = {}, 0
    db = _price_db_path()
    prov_db = None
    if db is not None:
        try:
            from packages.data.providers.db_provider import DBPriceProvider
            prov_db = DBPriceProvider(db)
        except Exception:  # noqa: BLE001 — base illisible → tout en synthétique
            prov_db = None
    for m in instruments:
        s = m["symbol"]
        bars = prov_db.fetch_ohlcv(s, "1d", start, end) if prov_db else []
        if len(bars) >= 250:
            data[s] = bars
            n_real += 1
        else:
            drift, vol = _SECTOR_DV.get(sector_of[s], (0.07, 0.18))
            data[s] = data_providers.create(
                "synthetic", seed=seed, drift=drift, annual_vol=vol).fetch_ohlcv(s, "1d", start, end)
    if n_real == 0:
        mode = "synthetic"
    elif n_real == len(instruments):
        mode = f"réel ({db.name})"
    else:
        mode = f"mixte ({n_real} réels / {len(instruments)} via {db.name})"
    return data, mode


def build_snapshot(seed: int = 7) -> dict:
    # --- univers COMPLET + fenêtre jusqu'à AUJOURD'HUI ---
    instruments = _seed_universe()
    symbols = [m["symbol"] for m in instruments]
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    names = {m["symbol"]: m["name"] for m in instruments}
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_HISTORY_DAYS)
    # prix RÉELS (base locale) si disponibles, sinon synthétique sectorisé (cohérence secteurs)
    data, data_mode = _load_prices(instruments, sector_of, start, end, seed)
    n = max(len(b) for b in data.values())
    vix = _vix_series(n, seed)                    # VIX (playbook volatilité + modulation)

    # --- backtest swing VECTORISÉ sur TOUT l'univers, capital fictif 10 000 $.
    # Profil offensif moyen-long terme : on alloue le cash aux MEILLEURS setups (tri par
    # conviction), exposition modulée par le VIX, positions laissées ouvertes. ---
    broker, journal, equity, ts_list = fast_swing_backtest(
        data, cash=10_000, costs=CostModel(), asset_classes=acmap,
        target_annual_vol=0.30, max_capital_frac=0.15, max_positions=20, max_pct=0.20,
        atr_stop=4.0, rr=6.0, vix=vix, close_at_end=False,
        daily_max_loss=0.06,        # kill-switch : stop des entrées si perte du jour > 6%
        trail_atr=5.0,              # trailing stop ATR : protège les gains, laisse courir
        next_open_fills=True)       # exécution à l'ouverture suivante (anti look-ahead)

    # régime macro point-in-time (couvre toute la fenêtre)
    months = int(_HISTORY_DAYS / 30) + 4
    ms = MacroStore(":memory:"); ms.upsert(synthetic_macro(start, months=months))
    regime = MacroRegimeClassifier(ms).classify(end - timedelta(days=2))
    impact = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))
    expo = impact.exposure_multiplier(regime)

    # ranking / screener sur TOUT l'univers
    ranker = RankingEngine(load_yaml(ROOT / "config" / "factors.yaml"), acmap)
    ranked = ranker.rank(data, t=n - 1, regime=regime, top_n=12)

    # benchmark JUSTE = univers équipondéré (buy & hold) → mesure l'alpha actif du swing.
    # + S&P 500 synthétique en référence marché. Tous rebasés 100 pour superposition.
    norm = [[b.close / d0[0].close for b in d0] for d0 in (data[s] for s in symbols)]
    eqw = [sum(col) / len(col) * 100 for col in zip(*norm)]
    sp = [b.close for b in data_providers.create(
        "synthetic", seed=101, drift=0.09, annual_vol=0.16).fetch_ohlcv("S&P 500", "1d", start, end)]
    bench_px = eqw
    benches = {"Univers (équipondéré)": eqw, "S&P 500": sp}

    # --- analyse de portefeuille (mesures relatives, risque, thèmes, ML) ---
    rel = relative_metrics(equity, bench_px)
    rets = returns_from_equity(equity)
    rm = risk_metrics_fn(rets)
    mc = monte_carlo(rets, seed=1)
    all_trades = journal.all()
    attr = attribution.attribute(all_trades, "strategy")
    agg = {**PL.metrics_payload(equity), **rel, **rm, **mc}
    themes = _themes_section(data, sector_of, end)         # mêmes données (cohérence)
    stance_by = themes.get("stance_by_sector", {})
    ml = _ml_section(data, sector_of, names)
    ml_scores = ml.get("scores", {}) if ml.get("available") else {}

    # SINGLE SOURCE OF TRUTH : les positions ouvertes pilotent positions/trades/corrélation/graphes
    marks = {s: data[s][-1].close for s in symbols}
    meta_pos = {s: {"asset_class": acmap.get(s), "name": names.get(s)} for s in symbols}
    comp = PL.composition_payload(broker.positions(), marks, meta_pos)
    for r in comp["rows"]:                       # liaison position ↔ secteur/thème + ML
        sec = sector_of.get(r["symbol"], "")
        r["sector"] = sec
        r["stance"] = stance_by.get(sec, "neutral")
        r["ml_score"] = ml_scores.get(r["symbol"])
    held = [r["symbol"] for r in comp["rows"]]
    # corrélation sur LES MÊMES actifs que les positions (cohérence inter-fenêtres)
    corr_syms = held[:12] if len(held) >= 2 else [s for s, _ in _top_traded(journal, 8)] or symbols[:8]
    rets_by = {s: returns_from_equity([b.close for b in data[s]]) for s in corr_syms}
    syms, corr = correlation_matrix({k: list(v) for k, v in rets_by.items()})
    clusters = cluster(syms, corr, 0.7)
    # séries OHLCV (historique LONG : daily/weekly/monthly agrégés côté front) + marqueurs trades
    open_info = getattr(broker, "open_positions_info", {})
    by_sym_trades = {}
    for t in all_trades:
        by_sym_trades.setdefault(t.instrument, []).append(t)
    position_series, position_markers = {}, {}
    for r in comp["rows"]:
        s = r["symbol"]
        bars = data[s][-1000:]                         # ~4 ans de daily → agrégeable W/M
        start_t = bars[0].ts
        position_series[s] = [
            {"t": b.ts.isoformat()[:10], "o": round(b.open, 4), "h": round(b.high, 4),
             "l": round(b.low, 4), "c": round(b.close, 4), "v": round(b.volume, 0)} for b in bars]
        marks = []
        oi = open_info.get(s)
        if oi and oi["entry_ts"] >= start_t:
            marks.append({"t": oi["entry_ts"].isoformat()[:10], "side": "buy",
                          "price": round(oi["entry_price"], 4)})
        for tr in by_sym_trades.get(s, []):            # achats/ventes clôturés visibles
            if tr.entry_ts >= start_t:
                marks.append({"t": tr.entry_ts.isoformat()[:10], "side": "buy", "price": round(tr.entry_price, 4)})
            if tr.exit_ts and tr.exit_ts >= start_t:
                marks.append({"t": tr.exit_ts.isoformat()[:10], "side": "sell", "price": round(tr.exit_price, 4)})
        position_markers[s] = marks
    trade_stats = PL.trade_stats_payload(all_trades)
    # 300 trades les plus récents (couvre la récence + de nombreux actifs)
    recent = sorted(all_trades, key=lambda t: t.entry_ts, reverse=True)[:300]
    dates = [t.isoformat() for t in ts_list]
    screener = PL.screener_payload(ranked, regime.ts)
    for r in screener["rows"]:                    # enrichit le screener du score ML + secteur
        r["ml_score"] = ml_scores.get(r["symbol"])
        r["sector"] = sector_of.get(r["symbol"], "")
    now = datetime.now(timezone.utc)
    last_bar = ts_list[-1]
    vix_now = vix[-1]
    init_cap = 10_000
    pf_value = round(equity[-1], 2)
    pf_pnl = round(pf_value - init_cap, 2)
    invested = comp["totals"]["current_value"]
    cash = round(max(0.0, pf_value - invested), 2)         # jamais négatif (pas de levier)
    portfolio_kpis = {
        "value": pf_value, "initial": init_cap, "pnl_abs": pf_pnl,
        "pnl_pct": round(pf_pnl / init_cap, 4), "cash": cash,
        "invested": round(invested, 2),
        "exposure_pct": round(min(1.0, invested / pf_value), 4) if pf_value else 0.0,
        "n_positions": len(comp["rows"]),
    }
    return {
        "meta": {
            "generated_at": now.isoformat(),
            "last_bar": last_bar.isoformat(),
            "period_start": start.isoformat(),
            "delay_minutes": 15,                 # flux différé 15 min (EOD/synthétique)
            "mode": data_mode,
            "strategy": "swing",
            "initial_capital": init_cap,
            "universe_size": len(symbols),
            "traded_assets": len({t.instrument for t in all_trades}),
            "n_trades": len(all_trades),
            "profile": "offensif · moyen-long terme",
        },
        "dashboard": {
            "as_of": last_bar.isoformat(),
            "regime": PL.regime_payload(regime, expo),
            "metrics": PL.metrics_payload(equity),
            "equity": PL.equity_series(equity, ts_list),
            "dates": dates,
            "positions": comp["rows"], "totals": comp["totals"],
            "portfolio": portfolio_kpis,
            "position_series": position_series,
            "position_markers": position_markers,
            "trade_stats": trade_stats,
            "vix": vix_now, "vix_playbook": _vix_playbook(vix_now),
            "vix_series": vix[::max(1, n // 240)],   # sous-échantillonné pour le graphe
        },
        "screener": screener,
        "portfolio": {
            **comp,
            "metrics": PL.metrics_payload(equity),
            "benchmarks": PL.benchmark_comparison(equity, benches),
            "analysis": {
                "relative": rel, "risk": rm, "monte_carlo": mc,
                "mc_projection": mc_projection(rets, horizon=252, start_value=100.0, seed=1),
                "attribution": attr,
                "correlation": PL.correlation_payload(syms, corr, clusters),
                "review": PL.review_payload(expert_review({**agg, **comp["totals"]})),
            },
        },
        "trades": [PL.trade_payload(t) for t in recent],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "universe": _universe_section(instruments),
        "data": _data_section(data, acmap),
        "themes": themes,
        "ml": ml,
        "live": _live_section(comp["rows"], acmap, portfolio_kpis),
    }


def _top_traded(journal, k: int) -> list[tuple[str, int]]:
    """k symboles les plus tradés (pour une matrice de corrélation lisible)."""
    counts: dict[str, int] = {}
    for t in journal.all():
        counts[t.instrument] = counts.get(t.instrument, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
