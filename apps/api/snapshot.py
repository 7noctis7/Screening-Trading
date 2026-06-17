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


def _db_full_universe() -> list[dict] | None:
    """Univers EXHAUSTIF depuis YAHOO.db (tous les tickers), si la base est branchée."""
    db = _price_db_path()
    if db is None:
        return None
    try:
        from packages.data.providers.db_provider import DBPriceProvider
        rows = DBPriceProvider(db).universe()
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    out = []
    for r in rows:
        s = r["symbol"]
        su = s.upper()
        ac = ("crypto" if (su.endswith("USDC") or su.endswith("USDT") or "/USD" in su or "-USD" in su)
              else "forex" if ("/" in s and len(s) <= 7 and "USD" in su)
              else "commodity" if "=F" in su
              else "index" if su.startswith("^")
              else "etf" if (r.get("sector") or "").lower() in ("etf", "fund")
              else "equity")
        out.append({"symbol": s, "name": r.get("name", ""), "asset_class": ac,
                    "venue": r.get("venue", ""), "currency": r.get("currency", ""),
                    "sector": r.get("sector", ""), "source": "YAHOO.db"})
    return out


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
        ac = (str(r.get("asset_class") or "?")).strip() or "?"
        by_class[ac] = by_class.get(ac, 0) + 1
        ven = (str(r.get("venue") or "?")).strip() or "?"
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


def _data_section(data: dict, acmap: dict[str, str], universe_total: int = 0) -> dict:
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
    src_cfg = load_yaml(ROOT / "config" / "data_sources.yaml")
    return {
        "as_of": data[first][-1].ts.isoformat(),
        "health": health,
        "symbols_total": len(symbols),
        "universe_total": universe_total or len(symbols),   # total disponible (29k si YAHOO.db)
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


def _live_with_rebalance(positions: list, acmap: dict, kpis: dict | None,
                         current_weights: dict[str, float]) -> dict:
    """_live_section + aperçu de la BANDE DE NON-TRADING (réduit le churn)."""
    from packages.execution.algos import twap_schedule
    from packages.portfolio.rebalance import apply_no_trade_band
    live = _live_section(positions, acmap, kpis)
    targets = {o["symbol"]: o["weight_pct"] for o in live["target_orders"]}
    live["rebalance"] = apply_no_trade_band(targets, current_weights, band=0.02)
    # plan d'exécution TWAP (exemple) sur le plus gros ordre cible → anti-impact marché
    top = max(live["target_orders"], key=lambda o: o["weight_pct"], default=None)
    if top:
        live["execution"] = {"algo": "TWAP", "slices": 5, "symbol": top["symbol"],
                             "weight_pct": top["weight_pct"],
                             "schedule_pct": twap_schedule(top["weight_pct"], 5)}
    return live


def _auc(scores, y) -> float | None:
    import numpy as np
    y = np.asarray(y, float)[np.argsort(scores)]
    n_pos, n = y.sum(), len(y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = np.arange(1, n + 1)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _ml_model():
    """Modèle d'edge : Gradient Boosting (sklearn) si disponible, sinon régression
    logistique numpy pure (toujours fonctionnel, sans dépendance)."""
    try:
        from packages.ml.model import SklearnModel
        return SklearnModel(), "Gradient Boosting (sklearn)"
    except Exception:  # noqa: BLE001
        from packages.ml.model import LogitModel
        return LogitModel(epochs=400), "régression logistique (numpy)"


def _feat_importance(model, names, X, y):
    """Importance des variables : native (arbres) sinon |poids| (logit) sinon permutation."""
    import numpy as np
    clf = getattr(getattr(model, "pipe", None), "named_steps", {}).get("clf") if hasattr(model, "pipe") else None
    if clf is not None and hasattr(clf, "feature_importances_"):
        vals = [float(v) for v in clf.feature_importances_]
    elif hasattr(model, "w") and model.w is not None:
        vals = [abs(float(v)) for v in model.w]
    else:
        vals = [1.0] * len(names)
    return sorted(zip(names, vals), key=lambda kv: -kv[1])


def _ml_section(data: dict, sector_of: dict, names: dict) -> dict:
    """Score ML d'edge (proba de hausse à ~1 mois) entraîné en CROSS-SECTION sur TOUT
    l'univers. Validation par CV PURGÉE + EMBARGO (López de Prado) ; GBM si dispo, sinon logit.
    Suivi mlflow optionnel. Anti look-ahead : features point-in-time, labels purgés."""
    import numpy as np

    from packages.indicators.momentum import RSI
    from packages.indicators.trend import SMA
    from packages.indicators.volatility import ATR
    from packages.ml.cv import PurgedKFold

    H = 21  # horizon ~1 mois (profil moyen-long terme)

    def feats(c, sma, rsi, atr, t):
        if t < 60 or t >= len(c) or sma[t] != sma[t] or rsi[t] != rsi[t] or atr[t] != atr[t]:
            return None
        return [c[t] / c[t - 20] - 1, c[t] / c[t - 60] - 1,
                (c[t] - sma[t]) / sma[t], rsi[t] / 100.0, atr[t] / c[t]]

    X, y, T0, T1, last = [], [], [], [], {}    # T0/T1 = fenêtre du label (pour la purge)
    for s, bars in data.items():
        c = np.array([b.close for b in bars], float)
        ncl = len(c)
        if ncl < 90 + H:
            continue
        sma, rsi, atr = SMA(50).compute(bars), RSI(14).compute(bars), ATR(14).compute(bars)
        for t in range(60, ncl - H, 5):
            f = feats(c, sma, rsi, atr, t)
            if f is None:
                continue
            X.append(f); y.append(1.0 if c[t + H] > c[t] else 0.0)
            T0.append(t); T1.append(t + H)     # le label couvre [t, t+H] → purge des chevauchements
        fl = feats(c, sma, rsi, atr, ncl - 1)
        if fl is not None:
            last[s] = fl
    if len(X) < 500:
        return {"available": False}
    X, y, T0, T1 = np.array(X), np.array(y), np.array(T0), np.array(T1)
    if len(X) > 60000:                          # borne le coût (sous-échantillon reproductible)
        idx = np.random.default_rng(0).choice(len(X), 60000, replace=False)
        X, y, T0, T1 = X[idx], y[idx], T0[idx], T1[idx]
    order = np.argsort(T0, kind="stable")       # TRI temporel requis par la CV purgée
    X, y, T0, T1 = X[order], y[order], T0[order], T1[order]
    model, model_name = _ml_model()

    # CV PURGÉE + EMBARGO : AUC out-of-sample honnête (labels chevauchants neutralisés)
    aucs, n_splits = [], 5
    try:
        for tr, te in PurgedKFold(n_splits=n_splits, embargo_pct=0.01).split(T0, T1):
            if len(tr) < 100 or len(te) < 30 or len(set(y[te])) < 2:
                continue
            m, _ = _ml_model()
            m.fit(X[tr], y[tr])
            a = _auc(m.predict_proba(X[te]), y[te])
            if a is not None:
                aucs.append(a)
    except Exception:  # noqa: BLE001 — CV indisponible → on continue sans
        pass
    cv_auc = round(float(np.mean(aucs)), 3) if aucs else None

    model.fit(X, y)                              # modèle final sur tout l'échantillon
    fn = ["momentum 1 mois", "momentum 3 mois", "tendance vs MM50", "RSI", "volatilité (ATR)"]
    imp = _feat_importance(model, fn, X, y)
    mx = max((v for _, v in imp), default=1.0) or 1.0
    probs = {s: float(model.predict_proba([f])[0]) for s, f in last.items()}
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:15]

    # CALIBRATION (Platt) + Brier : un score 0.8 doit se réaliser ~80 % du temps.
    # Validation temporelle : 80 % entraînement / 20 % test (X déjà trié par T0).
    calibration = {"available": False}
    try:
        from packages.ml.calibration import PlattCalibrator, brier_score, reliability_curve
        cut = int(len(X) * 0.8)
        if cut > 100 and len(X) - cut > 50:
            mcal, _ = _ml_model()
            mcal.fit(X[:cut], y[:cut])
            p_te = np.asarray(mcal.predict_proba(X[cut:]), float)
            cal = PlattCalibrator().fit(p_te, y[cut:])
            p_cal = cal.transform(p_te)
            calibration = {
                "available": True,
                "brier_raw": brier_score(y[cut:], p_te),
                "brier_calibrated": brier_score(y[cut:], p_cal),
                "reliability": reliability_curve(y[cut:], p_cal, bins=8),
            }
    except Exception:  # noqa: BLE001
        pass

    # CONFORMAL PREDICTION (LAC) : couverture garantie 1−α (split calib/test).
    conformal = {"available": False}
    try:
        from packages.ml.conformal import evaluate as conformal_eval
        cut = int(len(X) * 0.8)
        mid = int(len(X) * 0.6)
        if mid > 100 and len(X) - cut > 50:
            mcf, _ = _ml_model()
            mcf.fit(X[:mid], y[:mid])
            p_cal = np.asarray(mcf.predict_proba(X[mid:cut]), float)
            p_te = np.asarray(mcf.predict_proba(X[cut:]), float)
            conformal = {"available": True,
                         **conformal_eval(p_cal, y[mid:cut], p_te, y[cut:], alpha=0.1)}
    except Exception:  # noqa: BLE001
        pass

    # WALK-FORWARD (ancré) : robustesse temporelle de l'edge (AUC moyenne ± écart-type).
    walk_forward = {"available": False}
    try:
        from packages.backtest.walk_forward import walk_forward_splits
        wf_aucs = []
        for tr, te in walk_forward_splits(len(X), n_splits=5, train_frac=0.5, anchored=True):
            if len(set(y[list(te)])) < 2:
                continue
            mw, _ = _ml_model()
            mw.fit(X[list(tr)], y[list(tr)])
            a = _auc(mw.predict_proba(X[list(te)]), y[list(te)])
            if a is not None:
                wf_aucs.append(a)
        if wf_aucs:
            walk_forward = {"available": True, "folds": len(wf_aucs),
                            "auc_mean": round(float(np.mean(wf_aucs)), 3),
                            "auc_std": round(float(np.std(wf_aucs)), 3),
                            "aucs": [round(a, 3) for a in wf_aucs]}
    except Exception:  # noqa: BLE001
        pass

    # DRIFT des features (PSI) : 1re moitié (référence) vs 2nde moitié (actuel).
    drift = {"available": False}
    try:
        from packages.ml.drift import feature_drift
        half = len(X) // 2
        if half > 50:
            d = feature_drift(X[:half], X[half:], fn)
            drift = {"available": True, **d}
    except Exception:  # noqa: BLE001
        pass

    try:                                        # suivi d'expérience mlflow (optionnel)
        import mlflow
        mlflow.set_experiment("quant-terminal-ml")
        with mlflow.start_run(run_name="edge_cross_section"):
            mlflow.log_params({"model": model_name, "horizon": H, "n_splits": n_splits,
                               "n_samples": len(X)})
            if cv_auc is not None:
                mlflow.log_metric("cv_auc_purged", cv_auc)
    except Exception:  # noqa: BLE001
        pass

    return {
        "available": True, "model": model_name, "horizon_days": H,
        "validation": f"CV purgée + embargo (k={n_splits})",
        "n_train": int(len(X)), "n_splits": len(aucs), "auc": cv_auc,
        "feature_importance": [{"feature": f, "weight": round(v / mx, 3)} for f, v in imp],
        "top_conviction": [{"symbol": s, "name": names.get(s, ""),
                            "sector": sector_of.get(s, ""), "ml_score": round(p, 3)}
                           for s, p in top],
        "scores": {s: round(p, 3) for s, p in probs.items()},
        "calibration": calibration,
        "conformal": conformal,
        "walk_forward": walk_forward,
        "drift": drift,
    }


def _sentiment_section(held: list, names: dict, sector_of: dict, data: dict) -> dict:
    """Sentiment / news par position. News RSS réelles si `QUANT_NEWS=1` (FinBERT si dispo),
    sinon **repli hors-ligne** déterministe dérivé du momentum 63 jours (cohérent, jamais vide)."""
    import os

    from packages import sentiment as S

    use_news = os.environ.get("QUANT_NEWS") == "1"
    rows: list[dict] = []
    for s in (held or [])[:30]:
        score, n, heads = 0.0, 0, []
        if use_news:
            r = S.news_sentiment(s)
            score, n, heads = r["score"], r["n"], r["headlines"]
        if n == 0:                                  # repli momentum (hors-ligne)
            bars = data.get(s)
            if bars and len(bars) > 64:
                score = round(max(-1.0, min(1.0, (bars[-1].close / bars[-64].close - 1) * 3.0)), 4)
        rows.append({"symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
                     "score": score, "label": S.label_of(score), "n_news": n,
                     "headlines": heads[:5]})
    mood = round(sum(r["score"] for r in rows) / len(rows), 4) if rows else 0.0
    has_news = any(r["n_news"] for r in rows)
    return {
        "available": bool(rows),
        "engine": S.engine_name() if has_news else "momentum 63 j (repli hors-ligne)",
        "source": "news RSS" if has_news else "dérivé du momentum (activez QUANT_NEWS=1 pour les news)",
        "market_mood": mood, "market_label": S.label_of(mood), "rows": rows,
    }


def _fund_provider():
    """Provider fondamentaux : FMP si clé présente (free tier), sinon synthétique déterministe."""
    import os
    if os.environ.get("FMP_API_KEY"):
        try:
            from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
            return FMPFundamentalsProvider(), "FMP (free tier)"
        except Exception:  # noqa: BLE001
            pass
    from packages.fundamentals.provider import SyntheticFundamentalsProvider
    return SyntheticFundamentalsProvider(), "synthétique"


def _fundamentals_section(symbols: list, acmap: dict, names: dict, sector_of: dict) -> dict:
    """Analyse FONDAMENTALE : ratios (PER, EV/EBITDA, P/B, ROE/ROIC, marges), valorisation DCF
    (marge de sécurité) et score composite value+quality. Equities/ETF uniquement.
    FMP si `FMP_API_KEY`, sinon fondamentaux synthétiques déterministes (offline-safe)."""
    from packages.fundamentals import ratios, valuation
    from packages.fundamentals.provider import degrade_prior
    from packages.fundamentals.scoring import f_score, f_score_label, piotroski_full

    eq = [s for s in symbols if acmap.get(s) in ("equity", "etf")][:40]
    if not eq:
        return {"available": False}
    prov, src = _fund_provider()
    rows = []
    for s in eq:
        try:
            f = prov.get(s)
        except Exception:  # noqa: BLE001
            f = None
        if f is None:
            continue
        mos = valuation.margin_of_safety(f)
        try:                                          # Piotroski complet (YoY) si historique dispo
            prev = getattr(prov, "get_prior", None)
            prev = prev(s) if callable(prev) else degrade_prior(f)
            fs = piotroski_full(f, prev)
        except Exception:  # noqa: BLE001
            fs = f_score(f)
        rows.append({
            "symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
            "per": round(valuation.per(f), 1), "ev_ebitda": round(valuation.ev_ebitda(f), 1),
            "pb": round(valuation.price_to_book(f), 2), "roe": round(ratios.roe(f), 3),
            "roic": round(ratios.roic(f), 3), "gross_margin": round(ratios.gross_margin(f), 3),
            "fcf_yield": round(valuation.fcf_yield(f), 3),
            "margin_of_safety": None if mos != mos else round(mos, 3),
            "f_score": fs, "f_score_label": f_score_label(fs),
            "_val": (valuation.earnings_yield(f) + valuation.fcf_yield(f)),
            "_qual": (ratios.roic(f) + ratios.gross_margin(f) + ratios.fcf_conversion(f)),
        })
    if not rows:
        return {"available": False}

    # score composite 0-100 = rang percentile (value 50 % + quality 50 %)
    def _pctl(key):
        order = sorted(rows, key=lambda r: r[key])
        n = len(order)
        return {r["symbol"]: (i + 1) / n for i, r in enumerate(order)}
    pv, pq = _pctl("_val"), _pctl("_qual")
    for r in rows:
        score = round((pv[r["symbol"]] * 0.5 + pq[r["symbol"]] * 0.5) * 100, 1)
        r["score"] = score
        mos = r["margin_of_safety"]
        r["rating"] = ("BUY" if (mos is not None and mos > 0.20 and score >= 50)
                       else "SELL" if (score < 35 or (mos is not None and mos < -0.20))
                       else "HOLD")
        del r["_val"], r["_qual"]
    # rang sectoriel relatif (1 = meilleur de son secteur) — valorisation sector-neutral
    from collections import defaultdict
    by_sec: dict = defaultdict(list)
    for r in rows:
        by_sec[r["sector"]].append(r)
    for sec_rows in by_sec.values():
        for rank, r in enumerate(sorted(sec_rows, key=lambda x: x["score"], reverse=True), 1):
            r["sector_rank"] = f"{rank}/{len(sec_rows)}"
    rows.sort(key=lambda r: r["score"], reverse=True)
    buys = sum(1 for r in rows if r["rating"] == "BUY")
    return {"available": True, "source": src, "n": len(rows), "buys": buys, "rows": rows,
            "method": "Score = rang percentile value (earnings+FCF yield) 50 % + quality "
                      "(ROIC+marge+conversion FCF) 50 % · DCF FCFF pour la marge de sécurité."}


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


def _yahoo_aliases(sym: str, ac: str) -> list[str]:
    """Variantes de symbole au format Yahoo (pour retrouver crypto/forex/indices/commodités
    dans YAHOO.db). Objectif : maximiser la part de données RÉELLES.
    BTC/USDC → BTC-USD · EUR/USD → EURUSD=X · S&P 500 → ^GSPC · Gold → GC=F · BRK.B ↔ BRK-B."""
    _IDX = {"S&P 500": "^GSPC", "SP500": "^GSPC", "Nasdaq": "^IXIC", "Nasdaq 100": "^NDX",
            "Dow Jones": "^DJI", "Dow": "^DJI", "Russell 2000": "^RUT", "VIX": "^VIX",
            "FTSE 100": "^FTSE", "DAX": "^GDAXI", "CAC 40": "^FCHI", "Nikkei 225": "^N225"}
    _COMM = {"Gold": "GC=F", "Silver": "SI=F", "Crude Oil": "CL=F", "WTI": "CL=F",
             "Brent": "BZ=F", "Natural Gas": "NG=F", "Copper": "HG=F", "Corn": "ZC=F",
             "Wheat": "ZW=F"}
    out = [sym]
    if ac == "crypto":
        base = sym.split("/")[0] if "/" in sym else sym.replace("-USD", "").replace("USD", "")
        out += [f"{base}-USD", f"{base}USD", f"{base}-USDC", f"{base}-USDT", f"{base}USDT", base]
    elif ac == "forex" and "/" in sym:
        a, b = sym.split("/")[:2]
        out += [f"{a}{b}=X", f"{b}=X" if a == "USD" else f"{a}=X", f"{a}{b}"]
    elif ac == "commodity":
        out += [_COMM.get(sym, ""), f"{sym}=F"]
    elif ac == "index":
        out += [_IDX.get(sym, ""), f"^{sym}", sym.replace(" ", "")]
    elif ac in ("equity", "etf"):
        # convention Yahoo : classes d'actions notées avec '-' (BRK.B → BRK-B) et inversement
        if "." in sym:
            out.append(sym.replace(".", "-"))
        if "-" in sym:
            out.append(sym.replace("-", "."))
        out.append(sym.upper())
    return [s for s in dict.fromkeys(out) if s]   # dédupliqué, ordre préservé, sans vide


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
        bars = []
        if prov_db:                                  # essaie le symbole + ses alias Yahoo
            for alias in _yahoo_aliases(s, m.get("asset_class", "equity")):
                bars = prov_db.fetch_ohlcv(alias, "1d", start, end)
                if len(bars) >= 250:
                    break
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
    full_universe = _db_full_universe() or instruments   # univers EXHAUSTIF (29k tickers si DB)

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

    # --- BUDGET DE RISQUE + LIMITES DE CONCENTRATION (best practice buy-side) ---
    from packages.portfolio.risk_budget import covariance, risk_contributions
    from packages.risk.limits import concentration_report
    invested_now = comp["totals"]["current_value"] or 1.0
    w_by_name = {r["symbol"]: r["current_value"] / invested_now for r in comp["rows"]}
    w_by_sector: dict[str, float] = {}
    for r in comp["rows"]:
        w_by_sector[r["sector"]] = w_by_sector.get(r["sector"], 0.0) + r["current_value"] / invested_now
    cb_syms, cov = covariance({s: list(rets_by[s]) for s in syms})  # mêmes actifs que corr
    rb = risk_contributions([w_by_name.get(s, 0.0) for s in cb_syms], cov)
    risk_budget = {"symbols": cb_syms, "contrib_pct": rb["contrib_pct"],
                   "portfolio_vol": rb["portfolio_vol"],
                   "diversification_ratio": rb["diversification_ratio"]}
    limits = concentration_report(w_by_name, w_by_sector, max_name=0.20, max_sector=0.40)

    # --- STRESS-TESTS MACRO + COUVERTURE (axe 11) ---
    from packages.portfolio.scenarios import hedge_suggestion, scenario_analysis
    w_by_class: dict[str, float] = {}
    for r in comp["rows"]:
        ac = acmap.get(r["symbol"], "equity")
        w_by_class[ac] = w_by_class.get(ac, 0.0) + r["current_value"] / invested_now
    stress = {"scenarios": scenario_analysis(w_by_class),
              "hedge": hedge_suggestion(w_by_class, target_max_loss=-0.15)}

    # --- RISQUE AVANCÉ (VaR Cornish-Fisher, EWMA) + ALLOCATION OPTIMALE (HRP/min-var) ---
    from packages.portfolio.optimize import hrp_weights, min_variance_weights
    from packages.portfolio.risk_advanced import cornish_fisher_var, ewma_vol
    rm["var_cornish_fisher_95"] = cornish_fisher_var(rets, 0.95)
    rm["vol_ewma"] = ewma_vol(rets)
    # GARCH(1,1) vol forecast + backtest de VaR (Kupiec) + risque factoriel (ACP)
    from packages.portfolio.factor_risk import pca_risk
    from packages.portfolio.garch import fit_garch
    from packages.portfolio.var_backtest import backtest_var
    rm["garch"] = fit_garch(rets)
    rm["var_backtest"] = backtest_var(rets, rm.get("var_95", 0.0), alpha=0.95)
    rm["factor_risk"] = pca_risk({s: list(rets_by[s]) for s in syms})
    cur_w = [w_by_name.get(s, 0.0) for s in cb_syms]
    optimal = {"symbols": cb_syms, "current": [round(x, 4) for x in cur_w],
               "hrp": [round(x, 4) for x in hrp_weights(cov)],
               "min_variance": [round(x, 4) for x in min_variance_weights(cov)]}
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
    # turnover annualisé + capacité (best practice : friction & soutenabilité)
    from packages.portfolio.capacity import turnover
    avg_eq = sum(equity) / len(equity) if equity else 0.0
    trade_stats["turnover"] = turnover(all_trades, avg_eq, len(ts_list))
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
                "risk_budget": risk_budget,
                "limits": limits,
                "stress": stress,
                "optimal_allocation": optimal,
                "review": PL.review_payload(expert_review({**agg, **comp["totals"]})),
            },
        },
        "trades": [PL.trade_payload(t) for t in recent],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "universe": _universe_section(full_universe),
        "data": _data_section(data, acmap, len(full_universe)),
        "themes": themes,
        "ml": ml,
        "sentiment": _sentiment_section(held, names, sector_of, data),
        "fundamentals": _fundamentals_section(
            list(dict.fromkeys(held + [r["symbol"] for r in screener["rows"]] + symbols)),
            acmap, names, sector_of),
        "live": _live_with_rebalance(comp["rows"], acmap, portfolio_kpis, w_by_name),
    }


def _top_traded(journal, k: int) -> list[tuple[str, int]]:
    """k symboles les plus tradés (pour une matrice de corrélation lisible)."""
    counts: dict[str, int] = {}
    for t in journal.all():
        counts[t.instrument] = counts.get(t.instrument, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
