"""Assemble un snapshot complet de l'app depuis un run OFFLINE (synthétique).

Sert de source de données à l'API (et au front en mode démo) sans réseau. En prod, les
routes liront l'état live (broker, DB, régime du jour) au lieu de ce snapshot.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packages.common.env import load_env as _load_env

_load_env()   # charge .env (clés brokers, FMP, QUANT_PRICE_DB, QUANT_NEWS, LLM_*) au plus tôt

from apps.api import payloads as PL
from packages.backtest.fast_swing import fast_swing_backtest
from packages.common import load_yaml
from packages.data import data_providers
from packages.execution import CostModel
from packages.portfolio import (attribution, correlation_matrix, cluster, expert_review,
                                mc_projection, monte_carlo, relative_metrics, risk_metrics_fn)
from packages.common.safe_section import safe_section
from packages.portfolio.metrics import returns_from_equity
from packages.ranking import RankingEngine
from packages.regime import MacroImpactMap, MacroRegimeClassifier, synthetic_macro
from packages.storage import MacroStore

ROOT = Path(__file__).resolve().parents[2]
_NETWORK_KINDS = {"wikipedia", "ishares_holdings", "nasdaq_trader", "coingecko"}
import os as _os_hist
# Profondeur d'historique (jours calendaires). Défaut ≈ depuis 2015 (~11 ans) si ta base le permet ;
# sinon la fenêtre est tronquée à l'historique réel disponible. Surchargeable : QUANT_HISTORY_DAYS.
_HISTORY_DAYS = int(_os_hist.environ.get("QUANT_HISTORY_DAYS", "4015"))


def _seed_universe() -> list[dict]:
    """Univers COMPLET dédupliqué (par symbole) à partir des seeds — source unique.

    Ticket #4 (Thiel, micro-marché) : `QUANT_UNIVERSE=/chemin/niche.csv` restreint l'univers à un
    micro-marché choisi (mêmes colonnes que les seeds) → on domine une niche avant de scaler.
    """
    import os
    seen: dict[str, dict] = {}
    custom = os.environ.get("QUANT_UNIVERSE")
    paths = [Path(custom)] if custom and Path(custom).exists() else \
        sorted((ROOT / "data" / "seed").glob("*.csv"))
    for path in paths:
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
    positions ↔ secteurs. YTD = perf CALENDAIRE réelle (depuis le 1ᵉʳ janvier) ; garde-fou
    anti-glitch (saut > 150 %/j écarté). Meilleurs setups par secteur (momentum + tendance vs MM50).
    Seuls les secteurs « investissables »
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
        _cur_year = end.year
        for s, bars in items:
            c = np.array([b.close for b in bars], float)
            if c.size < 64:
                continue
            # GARDE-FOU DATA : saut quotidien aberrant (>150 % en 1 jour = split non ajusté /
            # glitch / discontinuité de fusion) → on écarte le titre (évite les SPCX +627 % faux).
            rr = c[1:] / c[:-1] - 1.0
            if rr.size and (np.nanmax(np.abs(rr)) > 1.5 or not np.all(np.isfinite(c)) or c.min() <= 0):
                continue
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
    if mode == "real":
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


def _live_section(positions: list, acmap: dict, kpis: dict | None = None,
                  target_weights: dict | None = None, crypto_weights: dict | None = None) -> dict:
    """Portefeuille RÉEL : statut de connexion aux brokers (Alpaca actions, Bitmart crypto).
    Non connecté tant que les clés API ne sont pas fournies → ordres « cibles » à répliquer.
    Si `target_weights` est fourni (allocation PRESET de production), les ordres cibles en découlent ;
    sinon on réplique les poids du portefeuille modèle (swing)."""
    import os
    alp = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_API_SECRET"))
    bit = bool(os.environ.get("BITMART_API_KEY") and os.environ.get("BITMART_API_SECRET"))
    # --- DONNÉES RÉELLES PAR BROKER (séparées, avec diagnostic d'erreur) ---
    def _alpaca():
        d = {"name": "Alpaca", "configured": alp, "ok": False, "equity": 0.0, "positions": [], "error": None}
        if not alp:
            d["error"] = "clés absentes (.env)"; return d
        try:
            from packages.execution.alpaca_broker import AlpacaBroker
            b = AlpacaBroker(paper=True)
            d["equity"] = round(float(b.equity()), 2)
            d["positions"] = b.positions_detailed()   # positions RÉELLES enrichies (prix/valeur/P&L)
            d["orders"] = b.orders()                   # ordres RÉELS exécutés (page Trades)
            d["open_orders"] = b.open_orders()         # ordres RÉELS en attente d'exécution (non remplis)
            d["history"] = b.portfolio_history()      # historique d'equity RÉEL (Alpaca le stocke)
            d["ok"] = True
        except Exception as e:  # noqa: BLE001
            d["error"] = str(e)[:160]
        return d

    def _bitmart():
        d = {"name": "Bitmart", "configured": bit, "ok": False, "equity": 0.0, "positions": [], "error": None}
        if not bit:
            d["error"] = "clés absentes (.env)"; return d
        try:
            from packages.execution.bitmart_broker import BitmartBroker
            b = BitmartBroker(dry_run=False)
            d["equity"] = round(float(b.equity()), 2)
            d["positions"] = b.positions_detailed()   # positions SPOT RÉELLES enrichies
            d["orders"] = b.orders()                   # transactions RÉELLES (page Trades)
            d["open_orders"] = b.open_orders()         # ordres SPOT en attente d'exécution (non remplis)
            # bougies réelles (Bitmart) pour les graphes des positions/ordres crypto (absents de YAHOO.db)
            _csyms = {p["symbol"] for p in d["positions"]} | {o.get("symbol") for o in d["orders"]}
            d["ohlcv"] = {s: bars for s in _csyms if s and (bars := b.ohlcv(s))}
            d["ok"] = True
        except Exception as e:  # noqa: BLE001
            d["error"] = str(e)[:160]
        return d

    # Interroge les DEUX brokers EN PARALLÈLE (threads — appels HTTP bloquants alpaca-py/ccxt) :
    # réconciliation ~2× plus rapide quand les deux comptes sont connectés. Chaque _broker() est
    # déjà isolé/try-except → non bloquant et sortie identique au mode série.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as _ex:
        _fa, _fb = _ex.submit(_alpaca), _ex.submit(_bitmart)
        a_d, b_d = _fa.result(), _fb.result()
    _real_trades = sorted((a_d.get("orders", []) + b_d.get("orders", [])),
                          key=lambda o: o.get("date", ""), reverse=True)
    _real_open = sorted((a_d.get("open_orders", []) + b_d.get("open_orders", [])),
                        key=lambda o: o.get("date", ""), reverse=True)
    real = {
        "connected": a_d["ok"] or b_d["ok"],
        "equity": round(a_d["equity"] + b_d["equity"], 2),
        "positions": a_d["positions"] + b_d["positions"],
        "trades": _real_trades,                    # ordres RÉELS exécutés (Alpaca + Bitmart)
        "open_orders": _real_open,                 # ordres RÉELS en attente d'exécution (non remplis)
        "alpaca": a_d, "bitmart": b_d,
    }
    # enregistre l'equity réelle du jour (construit l'historique réel par broker)
    try:
        from packages.execution.equity_history import record as _eq_record
        if a_d["ok"] or b_d["ok"]:
            _eq_record({"alpaca": a_d["equity"], "bitmart": b_d["equity"]})
    except Exception:  # noqa: BLE001
        pass
    if target_weights or crypto_weights:          # allocation PRESET (2 poches : actions + crypto)
        from packages.execution.routing import route as _route
        targets = []
        # poche actions/ETF → capital ALPACA ; poche crypto → capital BITMART (comptes distincts)
        for s, w in sorted((target_weights or {}).items(), key=lambda kv: -kv[1]):
            if w <= 0:
                continue
            r = _route(s, acmap.get(s, "equity"))
            targets.append({"symbol": s, "broker": r["broker"], "broker_symbol": r["broker_symbol"],
                            "asset_class": acmap.get(s, ""), "weight_pct": round(w, 4),
                            "side": "long", "tradeable": r["tradeable"], "capital": "alpaca"})
        for s, w in sorted((crypto_weights or {}).items(), key=lambda kv: -kv[1]):
            if w <= 0:
                continue
            r = _route(s, "crypto")
            targets.append({"symbol": s, "broker": r["broker"], "broker_symbol": r["broker_symbol"],
                            "asset_class": "crypto", "weight_pct": round(w, 4),
                            "side": "long", "tradeable": r["tradeable"], "capital": "bitmart"})
    else:                                         # repli : poids du portefeuille modèle (swing)
        tot = sum(p["current_value"] for p in positions) or 1.0
        targets = [{"symbol": p["symbol"], "broker": "Bitmart" if acmap.get(p["symbol"]) == "crypto" else "Alpaca",
                    "asset_class": acmap.get(p["symbol"], ""),
                    "weight_pct": round(p["current_value"] / tot, 4), "side": p["side"]}
                   for p in positions]
    return {
        "allocation_source": "preset (risk-parity + DD-target + blackout)" if target_weights else "swing",
        "connected": alp or bit,
        "real": real,                              # positions/equity RÉELLES du broker (vide si non connecté)
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
                         current_weights: dict[str, float],
                         target_weights: dict | None = None,
                         crypto_weights: dict | None = None) -> dict:
    """_live_section + aperçu de la BANDE DE NON-TRADING (réduit le churn)."""
    from packages.execution.algos import twap_schedule
    from packages.execution.reconciliation import reconcile
    from packages.execution.tca import decompose_cost
    from packages.portfolio.rebalance import apply_no_trade_band
    live = _live_section(positions, acmap, kpis, target_weights=target_weights,
                         crypto_weights=crypto_weights)
    targets = {o["symbol"]: o["weight_pct"] for o in live["target_orders"]}
    live["rebalance"] = apply_no_trade_band(targets, current_weights, band=0.02)
    # réconciliation cible ↔ positions + TCA (coût d'exécution estimé)
    equity = (kpis or {}).get("value", 0.0) or sum(p["current_value"] for p in positions)
    cur_vals = {p["symbol"]: p["current_value"] for p in positions}
    rec = reconcile(targets, cur_vals, equity)
    rec["tca"] = decompose_cost(rec["drift_usd"])      # coût attendu pour rééquilibrer le drift
    live["reconciliation"] = rec
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

    def feats(c, sma, rsi, atr, rets_c, t):
        if t < 60 or t >= len(c) or sma[t] != sma[t] or rsi[t] != rsi[t] or atr[t] != atr[t]:
            return None
        vol = atr[t] / c[t] if c[t] else 0.0
        hi52 = c[max(0, t - 252):t + 1].max()                  # plus-haut 52 sem. (point-in-time)
        # Proxy PEAD (post-earnings drift) SANS donnée payante : plus gros choc quotidien des
        # 10 derniers jours (signé). Bernard & Thomas : le cours dérive dans le sens du choc.
        win = c[max(1, t - 10):t + 1]
        rr = win[1:] / win[:-1] - 1 if len(win) > 1 else None
        gap = float(rr[abs(rr).argmax()]) if rr is not None and len(rr) else 0.0
        # Ticket #6 : RÉGIME de volatilité conditionnel (percentile de la vol court terme vs sa
        # propre histoire, point-in-time) → le modèle apprend des relations DIFFÉRENTES par régime.
        rv = rets_c[max(0, t - 20):t]
        cur_v = float(rv.std()) if rv.size > 3 else 0.0
        hist = rets_c[max(0, t - 252):t]
        reg = float((np.abs(hist) < cur_v).mean()) if hist.size > 20 else 0.5   # ∈ [0,1]
        return [c[t] / c[t - 20] - 1, c[t] / c[t - 60] - 1,
                (c[t] - sma[t]) / sma[t], rsi[t] / 100.0, vol,
                (c[t] / c[t - 60] - 1) / (vol + 1e-6),          # momentum ajusté du risque
                c[t] / hi52 - 1 if hi52 else 0.0,               # distance au plus-haut 52 sem.
                -(c[t] / c[t - 5] - 1),                         # reversal court terme (5 j)
                gap,                                            # dérive post-choc (proxy PEAD)
                reg]                                            # régime de volatilité (percentile)

    X, y, T0, T1, last = [], [], [], [], {}    # T0/T1 = fenêtre du label (pour la purge)
    for s, bars in data.items():
        c = np.array([b.close for b in bars], float)
        ncl = len(c)
        if ncl < 90 + H:
            continue
        sma, rsi, atr = SMA(50).compute(bars), RSI(14).compute(bars), ATR(14).compute(bars)
        rets_c = np.diff(c) / c[:-1] if ncl > 1 else np.zeros(0)   # pour le régime de vol
        rets_c = np.concatenate([[0.0], rets_c])                   # aligné sur les index de c
        for t in range(60, ncl - H, 5):
            f = feats(c, sma, rsi, atr, rets_c, t)
            if f is None:
                continue
            X.append(f); y.append(1.0 if c[t + H] > c[t] else 0.0)
            T0.append(t); T1.append(t + H)     # le label couvre [t, t+H] → purge des chevauchements
        fl = feats(c, sma, rsi, atr, rets_c, ncl - 1)
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

    fn = ["momentum 1 mois", "momentum 3 mois", "tendance vs MM50", "RSI", "volatilité (ATR)",
          "momentum ajusté risque", "distance plus-haut 52 sem.", "reversal 5 j",
          "dérive post-choc (PEAD)", "régime de volatilité"]
    # Ticket #2 (Huang/Musk) : serving DÉCOUPLÉ de l'entraînement. On charge le modèle final depuis
    # un artefact (produit hors-ligne par `make train` / cron) s'il est frais ; sinon on entraîne
    # inline et on le persiste. Fini le réentraînement complet à chaque requête web.
    from packages.ml import artifact as _art
    _sig = (len(X), X.shape[1], len(last), int(T1.max()) if len(T1) else 0)
    _cached = _art.load(_sig)
    if _cached is not None:
        model = _cached[0]
        _served = "artefact (cron)"
    else:
        model.fit(X, y)                          # entraînement inline (repli sûr)
        _art.save(_sig, model, {"fn": fn})
        _served = "inline"
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

    # META-LABELING : un 2e modèle filtre les faux positifs du primaire → précision ↑.
    meta = {"available": False}
    try:
        from packages.ml.meta import evaluate as meta_eval
        from packages.ml.meta import meta_labels
        a0, a1, a2 = int(len(X) * 0.5), int(len(X) * 0.75), len(X)
        if a0 > 100 and a2 - a1 > 50:
            mp, _ = _ml_model(); mp.fit(X[:a0], y[:a0])               # primaire
            pm = np.asarray(mp.predict_proba(X[a0:a1]), float)        # proba primaire (méta-train)
            ml_lbl = meta_labels(pm, y[a0:a1])
            Xm = np.column_stack([X[a0:a1], pm])
            if len(set(ml_lbl)) > 1:
                mm, _ = _ml_model(); mm.fit(Xm, ml_lbl)              # méta-modèle
                pte = np.asarray(mp.predict_proba(X[a1:a2]), float)
                mte = np.asarray(mm.predict_proba(np.column_stack([X[a1:a2], pte])), float)
                from packages.ml.sizing import evaluate_sizing
                meta = {"available": True, **meta_eval(pte, mte, y[a1:a2]),
                        "sizing": evaluate_sizing(pte, y[a1:a2], mte)}
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

    # HISTORIQUE D'ENTRAÎNEMENT + DRIFT DE PERFORMANCE (journal append-only, sans dépendance) :
    # suit l'AUC OOS run après run et signale une dégradation du modèle (ré-entraînement à revoir).
    training_history: dict = {"available": False}
    try:
        from packages.ml.tracking import detect_drift, load_history
        _hist = load_history(limit=30)
        if _hist:
            training_history = {"available": True,
                                "runs": [{"ts": h.get("ts"), "status": h.get("status"),
                                          "auc_oos": h.get("metrics", {}).get("auc_oos")} for h in _hist[-15:]],
                                "drift": detect_drift(_hist, metric="auc_oos")}
    except Exception:  # noqa: BLE001
        pass

    # GARDE-FOU edge : un AUC OOS ≤ 0.52 = pas d'edge prédictif exploitable (le score reste
    # affiché mais ne doit PAS piloter de sizing agressif). Discipline anti-surapprentissage.
    edge_ok = bool(cv_auc is not None and cv_auc >= 0.52)
    edge_msg = ("Edge OOS détecté (AUC ≥ 0.52) — utilisable avec prudence." if edge_ok
                else "Pas d'edge OOS prouvé (AUC ≤ 0.52) : score indicatif, ne pas surpondérer.")
    return {
        "available": True, "model": model_name, "horizon_days": H,
        "validation": f"CV purgée + embargo (k={n_splits})", "served_from": _served,
        "edge_ok": edge_ok, "edge_message": edge_msg, "auc_floor": 0.52,
        "n_train": int(len(X)), "n_splits": len(aucs), "auc": cv_auc,
        "feature_importance": [{"feature": f, "weight": round(v / mx, 3)} for f, v in imp],
        "top_conviction": [{"symbol": s, "name": names.get(s, ""),
                            "sector": sector_of.get(s, ""), "ml_score": round(p, 3)}
                           for s, p in top],
        "scores": {s: round(p, 3) for s, p in probs.items()},
        "calibration": calibration,
        "conformal": conformal,
        "walk_forward": walk_forward,
        "meta_labeling": meta,
        "drift": drift,
        "training_history": training_history,
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
    # Δsentiment (révision) : meilleur prédicteur EOD que le niveau. Persisté quotidiennement.
    try:
        from packages.sentiment.history import record_and_delta
        _delta = record_and_delta({r["symbol"]: r["score"] for r in rows})
        for r in rows:
            r["score_change"] = _delta["by_symbol"].get(r["symbol"], 0.0)
        mood_change = _delta["mood_delta"]
    except Exception:  # noqa: BLE001
        mood_change = 0.0
    # Fils d'actualité (RSS gratuit) — marché + MACRO (FED/BCE/FMI/économie). Toujours tentés.
    # ACTUALITÉS : uniquement l'ANNÉE EN COURS, dédupliquées, triées du + récent au + ancien.
    # Qualité > quantité : on garde une sélection courte et fraîche (avec la date affichée).
    market_news, macro_news = [], []
    try:
        from packages.sentiment.rss import MACRO_FEEDS, fetch_headlines
        for h in fetch_headlines(limit=8, timeout=3.0, current_year_only=True):
            sc = S.analyze([h["title"]])[0]
            market_news.append({"title": h["title"], "link": h.get("link", ""), "date": h.get("date", ""),
                                "label": sc["label"], "score": sc["score"]})
        for h in fetch_headlines(MACRO_FEEDS, limit=6, timeout=3.0, current_year_only=True):
            sc = S.analyze([h["title"]])[0]
            macro_news.append({"title": h["title"], "link": h.get("link", ""), "date": h.get("date", ""),
                               "label": sc["label"], "score": sc["score"]})
    except Exception:  # noqa: BLE001
        pass
    return {
        "available": bool(rows),
        "engine": S.engine_name() if (has_news or market_news) else "momentum 63 j (repli hors-ligne)",
        "source": "news RSS" if (has_news or market_news) else "dérivé du momentum (QUANT_NEWS=1 pour les news par actif)",
        "market_mood": mood, "market_label": S.label_of(mood), "mood_change": mood_change,
        "rows": rows, "market_news": market_news, "macro_news": macro_news,
    }


def _fund_provider():
    """Provider fondamentaux. Priorité : FMP (clé) → **yfinance par défaut si en ligne** → synthétique.

    - **FMP** : réel, free tier limité (~40 actifs) — si `FMP_API_KEY`.
    - **yfinance** : réel, GRATUIT sans clé — utilisé **par défaut** quand le réseau répond
      (désactivable avec `QUANT_FUND=synthetic` pour forcer l'offline/démo).
    - **synthétique** : fondamentaux FABRIQUÉS (déterministes) → repli hors-ligne, PAS pour décider.
    """
    import os
    mode = os.environ.get("QUANT_FUND", "").lower()
    if os.environ.get("FMP_API_KEY") and mode != "synthetic":
        try:
            from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
            return FMPFundamentalsProvider(), "FMP (free tier)"
        except Exception:  # noqa: BLE001
            pass
    # yfinance par défaut (réel, gratuit) sauf demande explicite de synthétique ; garde-fou réseau.
    if mode != "synthetic":
        try:
            from packages.common.net import online
            if mode == "yf" or online():
                from packages.fundamentals.yfinance_provider import YFinanceFundamentalsProvider
                return YFinanceFundamentalsProvider(), "yfinance (réel, gratuit)"
        except Exception:  # noqa: BLE001
            pass
    from packages.fundamentals.provider import SyntheticFundamentalsProvider
    return SyntheticFundamentalsProvider(), "synthétique (démo)"


def _fund_provider_chain() -> list:
    """Chaîne ORDONNÉE de providers fondamentaux pour 1 actif : yfinance → FMP (si clé) → SEC EDGAR,
    avec le synthétique en DERNIER recours (offline) → une note est TOUJOURS produite."""
    import os as _osf
    mode = _osf.environ.get("QUANT_FUND", "").lower()
    out: list = []
    if mode != "synthetic":
        try:
            from packages.common.net import online
            net = (mode == "yf") or online()
        except Exception:  # noqa: BLE001
            net = False
        if net:
            try:
                from packages.fundamentals.yfinance_provider import YFinanceFundamentalsProvider
                out.append(("yfinance (réel)", YFinanceFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _osf.environ.get("FMP_API_KEY"):
            try:
                from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
                out.append(("FMP (réel)", FMPFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if net:
            try:
                from packages.fundamentals.sec_provider import SECFundamentalsProvider
                out.append(("SEC EDGAR (réel)", SECFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
    from packages.fundamentals.provider import SyntheticFundamentalsProvider
    out.append(("synthétique (repli)", SyntheticFundamentalsProvider()))   # toujours en dernier
    return out


def fetch_financials_chain(symbol: str):
    """Récupère un `Financials` pour UN symbole via la chaîne réelle (yfinance→FMP→SEC EDGAR) puis
    le synthétique en repli, + l'exercice N-1 si la source l'expose. Renvoie (financials, prior,
    source). Sert la note d'analyse (endpoint /api/company_report) — produit TOUJOURS une note."""
    for src, prov in _fund_provider_chain():
        try:
            f = prov.get(symbol)
        except Exception:  # noqa: BLE001
            f = None
        if f is None:
            continue
        prior = None
        for meth in ("get_prior", "get_previous"):
            fn = getattr(prov, meth, None)
            if callable(fn):
                try:
                    prior = fn(symbol)
                except Exception:  # noqa: BLE001
                    prior = None
                break
        return f, prior, src
    return None, None, "indisponible"


def _fundamentals_section(symbols: list, acmap: dict, names: dict, sector_of: dict,
                          data: dict | None = None) -> dict:
    """Analyse FONDAMENTALE : ratios (PER, EV/EBITDA, P/B, ROE/ROIC, marges), valorisation DCF
    (marge de sécurité) et score composite value+quality. Equities/ETF uniquement.
    FMP si `FMP_API_KEY`, sinon fondamentaux synthétiques déterministes (offline-safe)."""
    from packages.fundamentals import ratios, valuation
    from packages.fundamentals.scoring import altman_z, f_score, f_score_label

    import os as _osf

    all_eq = [s for s in symbols if acmap.get(s) in ("equity", "etf")]
    if not all_eq:
        return {"available": False}
    # SOURCES RÉELLES EN CHAÎNE, PAR ACTIF : yfinance → FMP (clé) → SEC EDGAR. On couvre TOUT
    # l'univers actions (pas de plafond), en parallèle ; le synthétique n'est qu'un repli hors-ligne.
    _mode = _osf.environ.get("QUANT_FUND", "").lower()
    _providers: list = []
    if _mode != "synthetic":
        try:
            from packages.common.net import online
            _net = (_mode == "yf") or online()
        except Exception:  # noqa: BLE001
            _net = False
        if _net:
            try:
                from packages.fundamentals.yfinance_provider import YFinanceFundamentalsProvider
                _providers.append(("yfinance", YFinanceFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _osf.environ.get("FMP_API_KEY"):
            try:
                from packages.fundamentals.fmp_provider import FMPFundamentalsProvider
                _providers.append(("FMP", FMPFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
        if _net:
            try:
                from packages.fundamentals.sec_provider import SECFundamentalsProvider
                _providers.append(("SEC", SECFundamentalsProvider()))
            except Exception:  # noqa: BLE001
                pass
    cap = int(_osf.environ.get("QUANT_FUND_MAX", "1200"))   # large → couvre tout l'univers actions
    eq = all_eq[:cap]
    capped = len(all_eq) > cap
    by_source: dict[str, int] = {}

    def _chain_fetch(universe: list) -> dict:
        """1re source RÉELLE qui répond pour chaque actif (yfinance → FMP → SEC), en parallèle."""
        from concurrent.futures import ThreadPoolExecutor

        def _one(s):
            for label, p in _providers:
                try:
                    f = p.get(s)
                except Exception:  # noqa: BLE001
                    f = None
                if f is not None:
                    return s, label, f
            return s, None, None
        out: dict = {}
        # défaut PRUDENT (6) : trop de threads yfinance simultanés saturent la RAM (Killed:9 / OOM).
        # Montable via QUANT_FUND_WORKERS si la machine a de la marge.
        workers = max(2, min(16, int(_osf.environ.get("QUANT_FUND_WORKERS", "6"))))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for s, label, f in ex.map(_one, universe):
                if f is not None:
                    out[s] = f
                    by_source[label] = by_source.get(label, 0) + 1
        return out

    def _rows_for(fin_by: dict, universe: list):
        out = []
        for s in universe:
            f = fin_by.get(s)
            if f is None:
                continue
            mos = valuation.margin_of_safety(f)
            fs = f_score(f)                            # solidité 0-9 RÉELLE (signaux de l'exercice courant)
            mcap = valuation.market_cap(f)
            ps = mcap / f.revenue if f.revenue else None          # price-to-sales
            # NB : les croissances YoY (CA/bénéf.) sont volontairement RETIRÉES — trop volatiles/aberrantes
            # sur les small-caps (dénominateur ≈ 0) → hors tableau et hors notation.
            _az = altman_z(f)
            out.append({
                "symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
                "per": round(valuation.per(f), 1), "ev_ebitda": round(valuation.ev_ebitda(f), 1),
                "pb": round(valuation.price_to_book(f), 2),
                "ps": None if ps is None else round(ps, 2),
                "roe": round(ratios.roe(f), 3),
                "roic": round(ratios.roic(f), 3), "gross_margin": round(ratios.gross_margin(f), 3),
                "net_margin": round(ratios.net_margin(f), 3),
                "fcf_yield": round(valuation.fcf_yield(f), 3),
                "margin_of_safety": None if mos != mos else round(mos, 3),
                "f_score": fs, "f_score_label": f_score_label(fs),
                "altman_z": _az["z"], "altman_zone": _az["zone"],
                "per_raw": valuation.per(f),
                "_val": (valuation.earnings_yield(f) + valuation.fcf_yield(f)),
                "_qual": (ratios.roic(f) + ratios.gross_margin(f) + ratios.fcf_conversion(f)),
            })
        return out

    rows = []
    if _providers:
        rows = _rows_for(_chain_fetch(eq), eq)
        src = "réel multi-source : " + " → ".join(
            f"{k} {v}" for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])) if by_source else "réel"
    if len(rows) < 5:                                # hors-ligne total → synthétique déterministe
        from packages.fundamentals.provider import SyntheticFundamentalsProvider
        sp = SyntheticFundamentalsProvider()
        eq, capped = all_eq, False
        rows = _rows_for({s: sp.get(s) for s in eq}, eq)
        src = "synthétique (repli — hors-ligne)"
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
    # NOTE TECHNIQUE + premium/discount sectoriel (PER vs médiane secteur) + note combinée
    from statistics import median

    from packages.indicators.technical_score import technical_rating
    sec_pers: dict = {}
    for r in rows:
        sec_pers.setdefault(r["sector"], []).append(r["per_raw"])
    sec_med = {s: median([p for p in v if p > 0]) if any(p > 0 for p in v) else 0.0
               for s, v in sec_pers.items()}
    for r in rows:
        tech = technical_rating([b.close for b in (data or {}).get(r["symbol"], [])])
        r["tech_score"] = tech["score"]
        r["tech_label"] = tech["label"]
        med = sec_med.get(r["sector"], 0.0)
        r["sector_premium"] = round(r["per_raw"] / med - 1.0, 3) if med > 0 and r["per_raw"] > 0 else None
        r["combined_score"] = round(0.6 * r["score"] + 0.4 * r["tech_score"], 1)  # fond. + technique
        del r["per_raw"]
    rows.sort(key=lambda r: r["combined_score"], reverse=True)
    buys = sum(1 for r in rows if r["rating"] == "BUY")
    return {"available": True, "source": src, "n": len(rows), "buys": buys, "rows": rows,
            "total_equities": len(all_eq), "capped": capped,
            "method": "Score = rang percentile value (earnings+FCF yield) 50 % + quality "
                      "(ROIC+marge+conversion FCF) 50 % · DCF FCFF pour la marge de sécurité."}


def _conviction_section(held: list, screener: dict, ml_scores: dict, sentiment: dict,
                        fundamentals: dict, investors: dict, data: dict, sector_of: dict,
                        names: dict) -> dict:
    """Fusionne toutes les lentilles en une NOTE DE CONVICTION + allocation pilotée par conviction
    et contrôlée par le risque (inverse-vol, plafonnée). Best practice multi-facteurs, poids égaux."""
    from packages.strategies.conviction import conviction_rank, conviction_weights

    fund_by = {r["symbol"]: r.get("combined_score") for r in fundamentals.get("rows", [])}
    sent_by = {r["symbol"]: r.get("score") for r in sentiment.get("rows", [])}
    inv_by = {r["symbol"]: r.get("overall") for r in investors.get("rows", [])}
    cand = list(dict.fromkeys(list(held) + [r["symbol"] for r in screener.get("rows", [])]
                              + list(ml_scores)))[:40]
    signals: dict[str, dict] = {}
    vol: dict[str, float] = {}
    for s in cand:
        bars = data.get(s)
        if not bars or len(bars) < 80:
            continue
        c = [b.close for b in bars]
        trend = c[-1] / c[-63] - 1 if len(c) > 63 else 0.0          # momentum 3 mois (point-in-time)
        rets = [c[i] / c[i - 1] - 1 for i in range(1, len(c))][-252:]
        import numpy as _np
        vol[s] = float(_np.std(rets) * (252 ** 0.5)) if rets else 0.0
        signals[s] = {
            "trend": trend,
            "ml": ml_scores.get(s),
            "fundamental": (fund_by.get(s) / 100.0) if fund_by.get(s) is not None else None,
            "sentiment": sent_by.get(s),
            "investor": (inv_by.get(s) / 100.0) if inv_by.get(s) is not None else None,
        }
    if len(signals) < 3:
        return {"available": False}
    ranked = conviction_rank(signals)
    w = conviction_weights(ranked, vol, top_n=15, max_weight=0.20)
    # backtest POINT-IN-TIME (technique, sans fuite) : conviction vs équipondéré
    from packages.backtest.conviction_backtest import conviction_backtest, multi_lens_backtest
    backtest = conviction_backtest(data)
    # comparaison des top-10 par LENTILLE (fondamentaux / investisseurs / ML / toutes catégories)
    lens_backtest = multi_lens_backtest(data, {
        "Fondamentaux": fund_by,
        "Investisseurs": inv_by,
        "Signaux ML": ml_scores,
        "Toutes catégories": {r["symbol"]: r["conviction"] for r in ranked},
    }, top_n=10)
    rows = [{"symbol": r["symbol"], "name": names.get(r["symbol"], ""),
             "sector": sector_of.get(r["symbol"], ""), "conviction": r["conviction"],
             **{k: r["components"].get(k) for k in ("trend", "ml", "fundamental", "sentiment", "investor")},
             "target_weight": w.get(r["symbol"], 0.0)}
            for r in ranked[:25]]
    return {"available": True, "rows": rows, "backtest": backtest,
            "lens_backtest": lens_backtest,
            "method": "Note = moyenne des z-scores (poids égaux) de : momentum 3 m, proba ML, "
                      "qualité fondamentale, sentiment. Allocation = conviction × inverse-vol, "
                      "plafonnée à 20 %. Discipline anti-surapprentissage (pas de poids optimisés)."}


def _investor_section(symbols: list, acmap: dict, names: dict, sector_of: dict) -> dict:
    """Ranking « grands investisseurs » (Graham/Fisher/Thiel/Schwab). Actions/ETF uniquement."""
    from packages.fundamentals.investor_scores import investor_scores
    from packages.fundamentals.provider import degrade_prior

    prov, src = _fund_provider()
    all_eq = [s for s in symbols if acmap.get(s) in ("equity", "etf")]
    cap = 40 if src.startswith("FMP") else (80 if src.startswith("yfinance") else 2000)

    def _rows(provider, universe):
        out = []
        for s in universe:
            try:
                f = provider.get(s)
            except Exception:  # noqa: BLE001
                f = None
            if f is None:
                continue
            sec = sector_of.get(s, "")
            gp = getattr(provider, "get_prior", None)
            prev = gp(s) if callable(gp) else degrade_prior(f)
            out.append({"symbol": s, "name": names.get(s, ""), "sector": sec,
                        **investor_scores(f, sec, prev)})
        return out

    rows = _rows(prov, all_eq[:cap])
    if len(rows) < 5 and src.startswith("FMP"):     # repli synthétique → TOUT l'univers
        from packages.fundamentals.provider import SyntheticFundamentalsProvider
        prov, src = SyntheticFundamentalsProvider(), "synthétique (repli FMP)"
        rows = _rows(prov, all_eq)
    if not rows:
        return {"available": False}
    rows.sort(key=lambda r: r["overall"], reverse=True)
    return {"available": True, "source": src, "n": len(rows), "rows": rows,
            "method": "Scores 0-100 par doctrine (% de critères respectés) : Graham (value défensive), "
                      "Fisher (qualité-croissance), Thiel (moat/monopole), Schwab (4ᵉ révolution). "
                      "Overall = moyenne des 4."}


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
    (et synthétique en complément pour les symboles absents de la base). Renvoie
    (data, mode, real_syms) — `real_syms` = symboles à données RÉELLES (les autres sont synthétiques
    et NE doivent PAS apparaître en production/allocation/graphes : prix factices)."""
    data, real_syms = {}, set()
    db = _price_db_path()
    prov_db = None
    if db is not None:
        try:
            from packages.data.providers.db_provider import DBPriceProvider
            prov_db = DBPriceProvider(db)
        except Exception:  # noqa: BLE001 — base illisible → tout en synthétique
            prov_db = None
    from packages.data.providers.db_provider import DBPriceProvider as _DBP
    # base CRYPTO dédiée (data/crypto.db via `make ingest-crypto`) — la crypto n'est pas dans YAHOO.db
    prov_crypto = None
    _crypto_db = ROOT / "data" / "crypto.db"
    if _crypto_db.exists():
        try:
            prov_crypto = _DBP(_crypto_db)
        except Exception:  # noqa: BLE001
            prov_crypto = None
    # couche de MISE À JOUR fraîche (data/market.db via `make daily`, yfinance) lue PAR-DESSUS
    # YAHOO.db → les barres récentes (jusqu'à aujourd'hui) sont RÉELLES sans toucher YAHOO.db.
    prov_updates = None
    _upd_db = ROOT / "data" / "market.db"
    if _upd_db.exists() and (db is None or _upd_db.resolve() != Path(db).resolve()):
        try:
            prov_updates = _DBP(_upd_db)
        except Exception:  # noqa: BLE001
            prov_updates = None
    # PRELOAD vectorisé (1 scan au lieu de N requêtes/symbole) : on précharge tout l'OHLCV des
    # alias de l'univers dans chaque provider LONG. Best-effort — repli SQL par symbole si échec.
    try:
        _eq_aliases, _cx_aliases = [], []
        for _m in instruments:
            _ac = _m.get("asset_class", "equity")
            (_cx_aliases if _ac == "crypto" else _eq_aliases).extend(_yahoo_aliases(_m["symbol"], _ac))
        for _p in (prov_db, prov_updates):
            if _p:
                _p.preload(_eq_aliases, "1d", start, end)
        if prov_crypto:
            prov_crypto.preload(_cx_aliases, "1d", start, end)
    except Exception:  # noqa: BLE001 — l'accélérateur ne doit jamais casser le chargement
        pass
    for m in instruments:
        s = m["symbol"]
        ac_m = m.get("asset_class", "equity")
        if ac_m == "crypto":
            provs = [prov_crypto] if prov_crypto else []
        else:
            provs = [p for p in (prov_db, prov_updates) if p]   # historique + maj fraîche (fusion)
        merged: dict = {}
        for prov in provs:                               # ordre : YAHOO.db (historique) puis market.db
            got = []
            for alias in _yahoo_aliases(s, ac_m):
                got = prov.fetch_ohlcv(alias, "1d", start, end)
                if len(got) >= 50:
                    break
            for _b in got:                               # EXTENSION sans écrasement : YAHOO.db garde
                merged.setdefault(_b.ts.isoformat()[:10], _b)   # la priorité, market.db complète les dates
        # manquantes → pas de discontinuité d'ajustement (raw vs adjusted) au milieu de l'historique.
        if len(merged) >= 250:
            data[s] = sorted(merged.values(), key=lambda x: x.ts)
            real_syms.add(s)
        else:
            drift, vol = _SECTOR_DV.get(sector_of[s], (0.07, 0.18))
            data[s] = data_providers.create(
                "synthetic", seed=seed, drift=drift, annual_vol=vol).fetch_ohlcv(s, "1d", start, end)
    n_real = len(real_syms)
    _src = db.name if db else ("market.db" if prov_updates else "crypto.db" if prov_crypto else "?")
    _src += " + maj market.db" if (db and prov_updates) else ""
    if n_real == 0:
        mode = "synthetic"
    elif n_real == len(instruments):
        mode = f"réel ({_src})"
    else:
        mode = f"mixte ({n_real} réels / {len(instruments)} via {_src})"
    return data, mode, real_syms


def _index_closes(aliases: list[str], start, end, fallback: list[float]) -> tuple[list[float], bool]:
    """Closes RÉELS d'un indice/ETF : essaie les alias dans TOUTES les bases (YAHOO.db + market.db +
    crypto.db) et garde la série la PLUS LONGUE (ex. QQQ complet via market.db même si YAHOO.db ne
    l'a que récent), puis yfinance. Sinon `fallback` synthétique. Renvoie (closes, is_real)."""
    from packages.data.providers.db_provider import DBPriceProvider
    cands: list[list[float]] = []
    _dbs = [_price_db_path(), ROOT / "data" / "market.db", ROOT / "data" / "crypto.db"]
    for _dbp in _dbs:
        if _dbp is None or not Path(_dbp).exists():
            continue
        try:
            prov = DBPriceProvider(_dbp)
            for a in aliases:
                bars = prov.fetch_ohlcv(a, "1d", start, end)
                if len(bars) >= 250:
                    cands.append([b.close for b in bars])
                    break
        except Exception:  # noqa: BLE001
            continue
    if cands:
        return max(cands, key=len), True               # la série réelle la plus longue
    try:
        from packages.common.net import online
        if online():
            import yfinance as yf
            for a in aliases:
                df = yf.Ticker(a).history(start=start.date().isoformat(), end=end.date().isoformat())
                if len(df) >= 250:
                    return [float(x) for x in df["Close"].tolist()], True
    except Exception:  # noqa: BLE001
        pass
    return fallback, False


def _curve_stats(eq: list[float]) -> dict:
    """KPIs d'une courbe d'equity. Ratios via perf_summary (SOURCE UNIQUE DE VÉRITÉ) ;
    profit_factor/win_rate dérivés des rendements quotidiens (gains/pertes)."""
    import numpy as _np

    from packages.portfolio.metrics import perf_summary
    e = _np.asarray(eq, dtype=float)
    if e.size < 30:
        return {"available": False}
    r = e[1:] / e[:-1] - 1
    ps = perf_summary(r)                                  # cagr/sharpe/sortino/maxdd unifiés
    if not ps.get("available"):
        return {"available": False}
    gains, losses = float(r[r > 0].sum()), float(-r[r < 0].sum())
    return {"available": True, "cagr": ps["cagr"], "total_return": ps["total_return"],
            "sharpe": ps["sharpe"], "sortino": ps["sortino"],
            "max_drawdown": ps["max_drawdown"], "win_rate": round(float((r > 0).mean()), 3),
            "profit_factor": round(gains / losses, 2) if losses > 0 else 0.0}


def _r(x, nd=3):
    """Arrondi NaN-safe (→ None) pour les payloads JSON."""
    return round(float(x), nd) if isinstance(x, (int, float)) and x == x else None


def _screen_section(panel: dict, acmap: dict, names: dict, sector_of: dict, t: int) -> dict:
    """Screener à FILTRES (packages.screening) : filtres durs YAML puis tri par composite z-score.
    Complète le 'screener' (ranking pur) en montrant l'univers RÉDUIT aux candidats éligibles."""
    try:
        from packages.screening import ScreeningEngine
        eng = ScreeningEngine.from_yaml(ROOT / "config" / "screening.yaml")
    except Exception as e:  # noqa: BLE001 - jamais bloquant
        return {"available": False, "error": str(e)}
    # INVESTABLE uniquement : on ne propose pas un actif non achetable (indices ^… = régime/benchmark,
    # pas un ordre). Évite les candidats fantômes (ex. ^KS11) dans le screener.
    investable = {s: bars for s, bars in panel.items()
                  if not s.startswith("^") and acmap.get(s) != "index"}
    excluded = len(panel) - len(investable)
    try:
        results = eng.screen(investable, t=t)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e)}
    rows = []
    for i, r in enumerate(results[:50], 1):
        rows.append({
            "rank": i, "symbol": r.symbol,
            "name": names.get(r.symbol, r.symbol),
            "asset_class": acmap.get(r.symbol, "equity"),
            "sector": sector_of.get(r.symbol, ""),
            "score": _r(r.score),
            "reason": r.reason,
            "ret_12m": _r(r.metrics.get("ret_12m")),
            "drawdown": _r(r.metrics.get("drawdown_from_high")),
            "dollar_volume": _r(r.metrics.get("dollar_volume"), 0),
        })
    return {
        "available": True,
        "count": len(results),
        "universe_size": len(investable),
        "excluded_non_investable": excluded,
        "filters": [f"{f['metric']} {f.get('op', '>=')} {f.get('value')}" for f in eng.filters],
        "weights": eng.weights,
        "rows": rows,
    }


def _psr_block(equity: list) -> dict:
    """Honnêteté statistique (cf. manifeste) : PSR = P(Sharpe vrai > 0) sur la courbe affichée,
    corrigée skew/kurtosis (López de Prado). On assume le DSR≈0 plutôt que de le cacher."""
    import numpy as _np

    from packages.portfolio.psr import probabilistic_sharpe_ratio
    e = _np.asarray(equity, float)
    if e.size < 31:
        return {"available": False}
    r = e[1:] / e[:-1] - 1.0
    sd = float(r.std(ddof=1))
    if sd <= 0:
        return {"available": False}
    sharpe_d = float(r.mean() / sd)
    mu = float(r.mean())
    skew = float(((r - mu) ** 3).mean() / sd ** 3)
    kurt = float(((r - mu) ** 4).mean() / sd ** 4)
    psr = probabilistic_sharpe_ratio(sharpe_d, len(r), skew=skew, kurt=kurt, sr_benchmark=0.0)
    return {
        "available": True,
        "psr": psr,
        "sharpe_annualized": round(sharpe_d * (252 ** 0.5), 2),
        "n_obs": int(len(r)),
        "skew": round(skew, 3),
        "excess_kurtosis": round(kurt - 3.0, 2),
        "note": ("PSR = probabilité que le Sharpe vrai dépasse 0 (corrigé skew/kurtosis). "
                 "DSR multi-essais ≈ 0 → pas d'alpha directionnel prouvé : géré comme béta + risque."),
    }


def _prediction_section(held: list, acmap: dict, names: dict) -> dict:
    """Marchés de prédiction (Kalshi+Polymarket) : probas macro + actifs + résultats.
    Gate QUANT_PREDMKT=1 (réseau) → OFF par défaut (tests/offline). Best-effort."""
    import os
    if os.environ.get("QUANT_PREDMKT") != "1":
        return {"available": False, "reason": "QUANT_PREDMKT!=1"}
    try:
        from packages.data.prediction_markets import (
            DEBIAS_ALPHA,
            asset_detail,
            earnings_detail,
            fetch_markets,
            macro_detail,
        )
        recs = fetch_markets(300)
        if not recs:
            return {"available": False, "reason": "réseau"}
        eq = [s for s in held if acmap.get(s) == "equity"][:25]
        nm = {s: names.get(s, s) for s in eq}
        return {"available": True, "n_markets": len(recs), "alpha": DEBIAS_ALPHA,
                "macro": macro_detail(records=recs),
                "assets": asset_detail(held[:40], records=recs),
                "earnings": earnings_detail(eq, records=recs, names=nm)}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}


def _onchain_section(held: list, acmap: dict) -> dict:
    """Fondamentaux on-chain crypto (CoinGecko + DefiLlama, sans clé).
    Gate QUANT_ONCHAIN=1 (réseau) → OFF par défaut (tests/offline). Best-effort."""
    import os
    if os.environ.get("QUANT_ONCHAIN") != "1":
        return {"available": False, "reason": "QUANT_ONCHAIN!=1"}
    try:
        from packages.data.crypto_onchain import COINS, onchain_metrics
        held_root = {str(s).upper().replace("-USD", "") for s in (held or [])}
        syms = [s for s in COINS if s in held_root] or list(COINS)
        coins = {s: m for s, m in onchain_metrics(syms).items()
                 if any(v is not None for v in m.values())}
        if not coins:
            return {"available": False, "reason": "réseau"}
        from packages.research.crypto_report import generate
        eth_ctx = None
        try:
            from packages.data.growthepie import eth_context
            eth_ctx = eth_context()
        except Exception:  # noqa: BLE001 - enrichissement best-effort
            eth_ctx = None
        return {"available": True, "coins": coins,
                "report": generate(coins, eth_ctx)}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}


def _crypto_cockpit_section() -> dict:
    """Cockpit crypto marché (CoinGecko + DefiLlama + alternative.me, sans clé).
    Gate QUANT_CRYPTO=1 (réseau) → OFF par défaut (tests/offline). Best-effort."""
    import os
    if os.environ.get("QUANT_CRYPTO") != "1":
        return {"available": False, "reason": "QUANT_CRYPTO!=1"}
    try:
        from packages.data.crypto_market import cockpit
        ck = cockpit()
        ok = (ck.get("global") or {}).get("total_mcap") is not None
        if not ok and not ck.get("gainers"):
            return {"available": False, "reason": "réseau"}
        return {"available": True, **ck}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}


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
    data, data_mode, real_syms = _load_prices(instruments, sector_of, start, end, seed)
    # INTÉGRITÉ DES DONNÉES : si une base réelle est branchée, on RETIRE TOUT symbole en repli
    # synthétique de l'univers de travail → screener, ML, thèmes, conviction, preset, graphes…
    # tournent UNIQUEMENT sur des prix réels (zéro donnée fictive). En mode démo (aucune base),
    # real_syms est vide → on garde le synthétique (la bannière « données factices » prévient).
    if len(real_syms) >= 30:
        instruments = [m for m in instruments if m["symbol"] in real_syms]
        symbols = [m["symbol"] for m in instruments]
        data = {s: data[s] for s in symbols}
        acmap = {s: acmap[s] for s in symbols}
        names = {s: names[s] for s in symbols}
        sector_of = {s: sector_of[s] for s in symbols}
    # --- GATE D'AUDIT (PwC) : avant de bâtir screener/ML/preset sur ces prix, on les audite.
    #   QUANT_AUDIT=strict  → REFUSE de servir des données à anomalie CRITIQUE (lève → l'API sert
    #                         le dernier snapshot sain ; un build corrompu n'atteint jamais l'écran).
    #   QUANT_AUDIT=warn|1  → audite et joint le rapport (`_audit`) au snapshot, sans bloquer.
    #   (défaut désactivé ; n'audite QUE des prix réels — le synthétique de démo n'a pas à passer.)
    #   (défaut = `warn` : audite les prix réels + joint le rapport, sans bloquer ;
    #    `strict` reste opt-in pour le gate CI ; `off` désactive.)
    _audit_report: dict | None = None
    _audit_mode = (_os_hist.environ.get("QUANT_AUDIT", "warn") or "warn").lower()
    if _audit_mode in ("strict", "warn", "1", "true") and real_syms and data_mode == "real":
        from packages.data.audit import assert_integrity, audit_and_report
        try:
            _ar = audit_and_report(data, universe=symbols)
            _audit_report = _ar.to_dict()
            if _audit_mode == "strict":
                assert_integrity(_ar)             # lève DataIntegrityError si anomalie critique
        except Exception as _ae:                  # noqa: BLE001
            if _audit_mode == "strict":
                raise                             # strict : on propage → l'API garde le snapshot sain
            _audit_report = {"ok": False, "error": str(_ae)}   # warn : best-effort, jamais bloquant

    n = max(len(b) for b in data.values())
    # VIX RÉEL (^VIX) si dispo (base/yfinance), aligné sur n barres ; sinon synthétique.
    _vix_real, _vix_is_real = _index_closes(["^VIX", "VIX"], start, end, [])
    if _vix_is_real and len(_vix_real) >= 50:
        vix = _vix_real[-n:] if len(_vix_real) >= n else [_vix_real[0]] * (n - len(_vix_real)) + _vix_real
    else:
        vix = _vix_series(n, seed)                # repli synthétique (playbook volatilité + modulation)
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

    # indices RÉELS (S&P 500 / Nasdaq 100) — calculés TÔT car le régime macro s'en sert
    _sp_syn = [b.close for b in data_providers.create(
        "synthetic", seed=101, drift=0.09, annual_vol=0.16).fetch_ohlcv("S&P 500", "1d", start, end)]
    _ndx_syn = [b.close for b in data_providers.create(
        "synthetic", seed=202, drift=0.13, annual_vol=0.22).fetch_ohlcv("Nasdaq 100", "1d", start, end)]
    sp, _sp_real = _index_closes(["^GSPC", "SPX", "SPY"], start, end, _sp_syn)        # VRAI S&P 500
    ndx, _ndx_real = _index_closes(["^NDX", "^IXIC", "QQQ"], start, end, _ndx_syn)    # VRAI Nasdaq 100

    # régime macro RÉEL point-in-time : VIX réel + tendance S&P (proxy activité) + FRED (courbe,
    # chômage) si FRED_API_KEY. Repli synthétique UNIQUEMENT si aucune donnée réelle disponible.
    import os as _os_macro
    _fred_key = _os_macro.environ.get("FRED_API_KEY")
    _macro_sources, _macro_real = {"régime": "synthétique (aucune donnée macro réelle dispo)"}, False
    if _vix_is_real or _sp_real or _fred_key:        # au moins une vraie source macro
        from packages.regime.real_macro import real_macro_store
        _cal = [b.ts for b in max(data.values(), key=len)]
        _vix_d = _cal[-len(vix):] if _vix_is_real else []
        _vix_v = vix if _vix_is_real else []
        _sp_d = _cal[-len(sp):] if _sp_real else []
        _sp_v = sp if _sp_real else []
        ms, _macro_sources, _macro_real = real_macro_store(_vix_v, _vix_d, _sp_v, _sp_d, fred_key=_fred_key)
    if not _macro_real or ms.count() == 0:
        months = int(_HISTORY_DAYS / 30) + 4
        ms = MacroStore(":memory:"); ms.upsert(synthetic_macro(start, months=months))
        _macro_sources, _macro_real = {"régime": "synthétique (aucune donnée macro réelle dispo)"}, False
    regime = MacroRegimeClassifier(ms).classify(end - timedelta(days=2))
    impact = MacroImpactMap(load_yaml(ROOT / "config" / "macro_impact.yaml"))
    expo = impact.exposure_multiplier(regime)

    # ranking / screener sur TOUT l'univers
    ranker = RankingEngine(load_yaml(ROOT / "config" / "factors.yaml"), acmap)
    ranked = ranker.rank(data, t=n - 1, regime=regime, top_n=12)

    # benchmark JUSTE = univers équipondéré (buy & hold) → mesure l'alpha actif du swing.
    # (S&P 500 / Nasdaq 100 RÉELS déjà chargés plus haut pour le régime macro.)
    norm = [[b.close / d0[0].close for b in d0] for d0 in (data[s] for s in symbols)]
    eqw = [sum(col) / len(col) * 100 for col in zip(*norm)]
    bench_px = eqw
    benches = {"Univers (équipondéré)": eqw, "S&P 500": sp, "Nasdaq 100": ndx}
    # backtest MULTI-STRATÉGIE sur l'indice équipondéré (tendance/momentum/retour moyenne + ensemble)
    from packages.backtest.multi_strategy import run_multi_strategy
    from packages.common.memo import cached_stage
    # étape PURE (courbe → stratégies) : mémoïsée par contenu → non recalculée si l'indice équipondéré
    # n'a pas changé (pas de nouvelle barre). Repli transparent sur le calcul direct si cache indispo.
    multi_strategy = cached_stage("multi_strategy", [float(x) for x in eqw],
                                  lambda: run_multi_strategy(eqw))

    # --- analyse de portefeuille (mesures relatives, risque, thèmes, ML) ---
    rel = relative_metrics(equity, bench_px)
    rets = returns_from_equity(equity)
    rm = risk_metrics_fn(rets)
    # VaR multi-horizon (mise à l'échelle racine-du-temps) : 1 j / 10 j (Bâle) / 21 j (1 mois)
    _v1 = rm.get("var_95", 0.0)
    rm["var_horizons"] = [{"days": h, "var_95": round(_v1 * (h ** 0.5), 4)} for h in (1, 10, 21)]
    # Monte-Carlo (2000 sims, seedé → déterministe) mémoïsé par contenu : non relancé si les
    # rendements du portefeuille n'ont pas changé (cf. packages/common/memo.py).
    mc = cached_stage("monte_carlo", [float(x) for x in rets], lambda: monte_carlo(rets, seed=1))
    all_trades = journal.all()
    attr = attribution.attribute(all_trades, "strategy")
    agg = {**PL.metrics_payload(equity), **rel, **rm, **mc}
    themes = safe_section("themes", _themes_section, data, sector_of, end)  # isolé
    stance_by = themes.get("stance_by_sector", {})
    ml = safe_section("ml", _ml_section, data, sector_of, names)            # isolé
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
    # diagnostic de conditionnement (qualité du risque) : cov empirique vs régularisée + δ retenu
    _cov_diag: dict = {}
    _cov_cache_stats: dict = {}
    try:
        import numpy as _npd

        from packages.data.engine import (auto_ttl_days, covariance_diagnostics,
                                          covariance_matrix, ledoit_wolf_shrinkage,
                                          persist_cov_cache_stats, purge_cov_disk_cache)
        purge_cov_disk_cache(auto_ttl_days())              # purge TTL auto-réglé (1×/build)
        _rets = {s: list(rets_by[s]) for s in syms}
        _, _cov_raw = covariance_matrix(_rets, shrink=False)
        _csyms = [s for s in cb_syms if _rets.get(s) and len(_rets[s]) >= 2]
        _m = min(len(_rets[s]) for s in _csyms) if _csyms else 0
        _delta = 0.0
        if _m >= 2:
            _mat = _npd.array([_rets[s][-_m:] for s in _csyms], dtype=float)
            _, _delta = ledoit_wolf_shrinkage(_mat)
        _cov_diag = covariance_diagnostics(_cov_raw, cov, delta=_delta)
        _cov_cache_stats = persist_cov_cache_stats()       # cumul persistant (hit-rate multi-builds)
    except Exception:  # noqa: BLE001 — diagnostic best-effort, jamais bloquant
        _cov_diag = {}
    risk_budget = {"symbols": cb_syms, "contrib_pct": rb["contrib_pct"],
                   "portfolio_vol": rb["portfolio_vol"],
                   "diversification_ratio": rb["diversification_ratio"],
                   "covariance_diagnostics": _cov_diag}
    # #3 audit : la corrélation de stress PILOTE les limites (resserre si diversif faiblit)
    try:
        import numpy as _np_lim

        from packages.portfolio.correlation import conditional_correlation
        from packages.risk.limits import concentration_report_adaptive
        _rb = {k: list(v) for k, v in rets_by.items() if len(v) >= 10}
        _ml = min((len(v) for v in _rb.values()), default=0)
        if len(_rb) >= 2 and _ml >= 10:
            _aligned = {k: v[-_ml:] for k, v in _rb.items()}
            _proxy = [float(x) for x in _np_lim.mean(list(_aligned.values()), axis=0)]
            _corr_cond = conditional_correlation(_aligned, _proxy)
            limits = concentration_report_adaptive(w_by_name, w_by_sector, _corr_cond,
                                                   max_name=0.20, max_sector=0.40)
        else:
            limits = concentration_report(w_by_name, w_by_sector, max_name=0.20,
                                          max_sector=0.40)
    except Exception:  # noqa: BLE001 — repli sur le rapport fixe
        limits = concentration_report(w_by_name, w_by_sector, max_name=0.20,
                                      max_sector=0.40)

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
    from packages.portfolio.optimize import equal_risk_contribution
    cur_w = [w_by_name.get(s, 0.0) for s in cb_syms]
    optimal = {"symbols": cb_syms, "current": [round(x, 4) for x in cur_w],
               "hrp": [round(x, 4) for x in hrp_weights(cov)],
               "min_variance": [round(x, 4) for x in min_variance_weights(cov)],
               "risk_parity": [round(x, 4) for x in equal_risk_contribution(cov)]}
    # skfolio (optionnel, qualité recherche) : max-diversification si la lib est installée
    try:
        import numpy as _np
        from packages.portfolio.skfolio_adapter import skfolio_available, skfolio_weights
        if skfolio_available() and len(cb_syms) >= 3:
            _ml = min(len(rets_by[s]) for s in cb_syms)
            if _ml >= 30:
                _mat = _np.array([list(rets_by[s])[-_ml:] for s in cb_syms]).T
                _sk = skfolio_weights(_mat, "max_diversification")
                if _sk and len(_sk) == len(cb_syms):
                    optimal["skfolio_maxdiv"] = _sk
    except Exception:  # noqa: BLE001
        pass
    # allocation RECOMMANDÉE : risk-parity + bande de non-trading + exposition pilotée par DD-cible
    import os as _os
    from packages.portfolio.construction import (build_target, tail_adjusted_dd_target,
                                                 vol_target_from_drawdown)
    _dd = float(_os.environ.get("QUANT_DD_TARGET", "0.25"))   # best practice (DSR≈0 → risk-managed) :
    # DD-cible 0.25 (équilibre exposition/DD). 0.15 = max-défensif · 0.45 = agressif. Le cœur QQQ
    # (QUANT_CORE_SPEC) porte la bêta/le rendement ; le preset = satellite à risque maîtrisé.
    # ticket #5 : durcit le DD-cible si les queues sont épaisses (CVaR/VaR > gaussien)
    _tail = (rm.get("cvar_95", 0.0) / rm["var_95"]) if rm.get("var_95") else None
    _dd_eff = tail_adjusted_dd_target(_dd, _tail)
    recommended = build_target(cb_syms, cov, {s: w_by_name.get(s, 0.0) for s in cb_syms},
                               dd_target=_dd_eff, band=0.03, max_gross=1.0)
    recommended["dd_target_nominal"] = _dd
    recommended["dd_target_tail_adjusted"] = round(_dd_eff, 4)
    recommended["tail_ratio"] = round(_tail, 3) if _tail else None
    # ticket #7 : edge gate — sans edge OOS prouvé (DSR/AUC), les signaux ne pilotent PAS l'allocation
    _edge_proven = bool(ml.get("edge_ok")) and (rm.get("dsr", 0.0) or 0.0) >= 0.90
    recommended["edge_proven"] = _edge_proven
    recommended["edge_note"] = ("Edge OOS prouvé : les signaux peuvent incliner l'allocation."
                                if _edge_proven else
                                "Aucun edge OOS prouvé (DSR≈0) → allocation 100 % pilotée par le "
                                "RISQUE (risk-parity), les signaux ne surpondèrent rien.")
    # overlay VOLATILITÉ GÉRÉE (Moreira-Muir) sur les rendements de la stratégie
    from packages.portfolio.vol_managed import vol_managed_backtest
    rm["vol_managed"] = vol_managed_backtest(rets, target_vol=vol_target_from_drawdown(_dd),
                                             window=20, max_leverage=1.0)
    # RÉGIME DE VOLATILITÉ (calme/normal/stress) → multiplicateur d'exposition au-delà du VIX
    from packages.regime.vol_regime import vol_regime
    rm["vol_regime"] = vol_regime(rets, window=20)

    # Sharpe probabiliste & DÉFLATÉ (garde-fou surapprentissage / essais multiples)
    from packages.portfolio.psr import deflated_sharpe_ratio, probabilistic_sharpe_ratio
    sr = rm.get("sharpe", 0.0) / (252 ** 0.5) if rm.get("sharpe") else 0.0   # Sharpe journalier
    nobs = len(rets)
    rm["psr"] = probabilistic_sharpe_ratio(sr, nobs, sr_benchmark=0.0)
    rm["dsr"] = deflated_sharpe_ratio(sr, nobs, n_trials=20)   # ~20 configs essayées

    # EVT (risque de queue extrême) + risque de LIQUIDITÉ
    from packages.portfolio.evt import evt_var_es
    from packages.portfolio.liquidity import portfolio_liquidity
    rm["evt"] = evt_var_es(rets, alpha=0.999)
    from packages.portfolio.fragility import fragility as _fragility
    rm["fragility"] = _fragility(rets)            # Taleb : exposition aux extrêmes
    liq_positions = []
    for r in comp["rows"]:
        bars = data.get(r["symbol"], [])[-20:]
        adv = (sum(b.close * b.volume for b in bars) / len(bars)) if bars else 0.0
        liq_positions.append({"symbol": r["symbol"], "value": r["current_value"], "adv": adv})
    rm["liquidity"] = portfolio_liquidity(liq_positions, participation=0.10)
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
    from packages.execution.costs import cost_assumptions
    trade_stats["cost_assumptions"] = cost_assumptions()   # transparence : coûts par classe (bps)
    # 300 trades les plus récents (couvre la récence + de nombreux actifs)
    recent = sorted(all_trades, key=lambda t: t.entry_ts, reverse=True)[:300]
    dates = [t.isoformat() for t in ts_list]
    screener = PL.screener_payload(ranked, regime.ts)
    for r in screener["rows"]:                    # enrichit le screener du score ML + secteur
        r["ml_score"] = ml_scores.get(r["symbol"])
        r["sector"] = sector_of.get(r["symbol"], "")
    # Screener à FILTRES (packages.screening) — univers réduit aux candidats éligibles.
    screen_sec = safe_section("screen", _screen_section, data, acmap, names, sector_of, n - 1)
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

    # --- NOTE DE CONVICTION : fusion des lentilles (best practice multi-facteurs) ---
    sentiment_sec = safe_section("sentiment", _sentiment_section, held, names, sector_of, data)
    _cand_eq = list(dict.fromkeys(held + [r["symbol"] for r in screener["rows"]] + symbols))
    fundamentals_sec = safe_section(
        "fundamentals", _fundamentals_section, _cand_eq, acmap, names, sector_of, data)
    investors_sec = safe_section(
        "investors", _investor_section, _cand_eq, acmap, names, sector_of)
    conviction_sec = safe_section(
        "conviction", _conviction_section,
        held, screener, ml_scores, sentiment_sec, fundamentals_sec, investors_sec,
        data, sector_of, names)
    # --- PRESET « best practice » : qualité + risk-parity + DD-target + blackout + no-trade band ---
    # Backtest point-in-time, comparé au swing actuel et à l'équipondéré.
    from packages.backtest.preset_backtest import preset_backtest
    _quality = {r["symbol"]: r.get("combined_score") for r in fundamentals_sec.get("rows", [])}
    # UNIVERS NÉGOCIABLE : production restreinte aux instruments (1) négociables par les brokers
    # (actions US + ETF via Alpaca, crypto via Bitmart) ET (2) à DONNÉES RÉELLES uniquement — les
    # symboles en repli synthétique (prix factices, ex. RZLV absent de YAHOO.db) sont EXCLUS de
    # l'allocation/des ordres/des graphes pour ne JAMAIS afficher de prix halluciné.
    from packages.execution.routing import is_tradeable, route
    _tradeable_data = {s: b for s, b in data.items()
                       if is_tradeable(s, acmap.get(s, "equity")) and s in real_syms}
    if len(_tradeable_data) < 30:                        # garde-fou (mode démo/synthétique) :
        # pas assez de réel → on retombe sur le négociable (la bannière « données factices » prévient)
        _tradeable_data = {s: b for s, b in data.items() if is_tradeable(s, acmap.get(s, "equity"))} or data
    _ro = _os_hist.environ.get("QUANT_RISK_OVERLAY") == "1"   # opt-in overlay risque
    preset_bt = preset_backtest(_tradeable_data, _quality, asset_classes=acmap, swing_equity=equity,
                                dd_target=_dd, band=0.03, risk_overlay=_ro)
    recommended["preset_backtest"] = preset_bt          # rattaché à l'allocation recommandée affichée
    # JOURNAL DES TRADES DU PRESET (rebalancements) → page Trades (remplace le swing legacy)
    from packages.backtest.preset_backtest import preset_trade_log
    _preset_trades = preset_trade_log(_tradeable_data, _quality, asset_classes=acmap,
                                      dd_target=_dd, band=0.03, init_cap=init_cap)
    # ALLOCATION DE PRODUCTION = poids ACTUELS du preset (ce que make live réplique en paper)
    from packages.backtest.preset_backtest import preset_latest_weights
    _preset_weights = preset_latest_weights(_tradeable_data, _quality, asset_classes=acmap,
                                            dd_target=_dd, band=0.03)
    # SLEEVE CRYPTO (best practice, risk-parity) — poche SÉPARÉE, dimensionnée sur le capital BITMART.
    # Comptes distincts : les actions sont dimensionnées sur le capital ALPACA, la crypto sur Bitmart.
    _crypto_weights = {}
    try:
        from packages.backtest.crypto_sleeve import crypto_weights
        _crypto_weights = crypto_weights(data, asset_classes=acmap, dd_target=_dd)
    except Exception:  # noqa: BLE001
        pass
    # Courbe d'equity QUOTIDIENNE du preset → c'est ELLE qui pilote le dashboard (le swing est legacy)
    from packages.backtest.preset_backtest import preset_equity_daily
    _pe = preset_equity_daily(_tradeable_data, _quality, asset_classes=acmap, dd_target=_dd, init_cap=init_cap)
    # --- CŒUR(S) INDICIEL(S) + SATELLITE PRESET (multi-cœur) --------------------------------
    # Mélange un/des cœur(s) passif(s) au preset. DÉFAUT : 50% QQQ + 50% preset (meilleur couple
    # rendement/risque sur l'historique réel : Sharpe 0,98 · CAGR 20,3% · maxDD -31% vs preset pur
    # 0,93/17,8%/-34%). Le momentum sectoriel et le top-10 méga-caps sont dominés par QQQ → écartés
    # du défaut (restent activables via la spec). Spec configurable :
    #   QUANT_CORE_SPEC="qqq:0.5"            (défaut)
    #   QUANT_CORE_SPEC="qqq:0.15,megacap:0.10" / "sector_mom:0.25"   (le reste = preset)
    from packages.backtest.index_core import blend_equity_multi
    _spec_raw = _os.environ.get("QUANT_CORE_SPEC", "qqq:0.5")
    _spec: dict[str, float] = {}
    for _part in _spec_raw.split(","):
        if ":" in _part:
            _k, _, _v = _part.partition(":")
            try:
                _spec[_k.strip().lower()] = max(0.0, float(_v))
            except ValueError:
                pass
    _qqq_pct, _mc_pct, _sm_pct = _spec.get("qqq", 0.0), _spec.get("megacap", 0.0), _spec.get("sector_mom", 0.0)
    # market caps (sidecar) → pondération « comme un vrai indice »
    _mktcaps = {}
    try:
        from packages.data.market_cap import load_market_caps
        _mktcaps = load_market_caps()
    except Exception:  # noqa: BLE001
        pass
    # cœur ETF (QQQ) et cœur top-10 méga-caps
    _qqq_closes, _qqq_real = (_index_closes(["QQQ", "^NDX", "^IXIC"], start, end, ndx)
                              if _qqq_pct > 0 else ([], False))
    _mc_curve, _mc_top, _mc_w, _mc_real, _mc_weighting = [], [], {}, False, "—"
    if _mc_pct > 0:
        from packages.backtest.megacap import megacap_equity_daily
        _mc = megacap_equity_daily(_tradeable_data, asset_classes=acmap, init_cap=init_cap,
                                   market_caps=_mktcaps or None)
        if _mc.get("available"):
            _mc_curve, _mc_top = _mc["equity"], _mc.get("current_top", [])
            _mc_w, _mc_real, _mc_weighting = _mc.get("current_weights", {}), True, _mc.get("weighting", "—")
    # cœur MOMENTUM SECTORIEL — TOUJOURS calculé (pour le sweep `make index-core`), activé en prod
    # seulement si présent dans la spec (QUANT_CORE_SPEC="sector_mom:0.25").
    _sm_curve, _sm_holds, _sm_secs = [], [], []
    try:
        from packages.backtest.sector_momentum import sector_momentum_equity_daily
        _sm = sector_momentum_equity_daily(_tradeable_data, sector_of, asset_classes=acmap, init_cap=init_cap)
        if _sm.get("available"):
            _sm_curve = _sm["equity"]
            _sm_holds, _sm_secs = _sm.get("current_holdings", []), _sm.get("current_sectors", [])
    except Exception:  # noqa: BLE001
        pass
    _index_core_info = {"enabled": False, "core_pct": 0.0, "symbol": "QQQ+TOP10",
                        "core_type": "multi",
                        "spec": {"qqq": _qqq_pct, "megacap": _mc_pct, "sector_mom": _sm_pct},
                        "core_holdings": _mc_top, "core_weights": _mc_w,
                        "mc_weighting": _mc_weighting, "mktcap_real": bool(_mktcaps),
                        "qqq_is_real": bool(_qqq_real), "mc_is_real": bool(_mc_real)}
    _preset_pure = list(_pe.get("equity", []))           # courbe preset PURE (avant mélange) → sweep
    _preset_pure_dates = list(_pe.get("dates", []))      # dates alignées (pour le stress-test bear)
    _cores = []
    if _qqq_pct > 0 and _qqq_closes and len(_qqq_closes) > 60:
        _cores.append((_qqq_closes, _qqq_pct, "qqq"))
    if _mc_pct > 0 and _mc_curve and len(_mc_curve) > 60:
        _cores.append((_mc_curve, _mc_pct, "megacap"))
    if _sm_pct > 0 and _sm_curve and len(_sm_curve) > 60:
        _cores.append((_sm_curve, _sm_pct, "sector_mom"))
    _total_core = sum(w for _, w, _ in _cores)
    if _pe.get("available") and _cores and 0 < _total_core <= 1.0:
        _blended, _m = blend_equity_multi(_pe["equity"], [(c, w) for c, w, _ in _cores], init_cap=init_cap)
        if _blended:
            _base_stats = _curve_stats(_pe["equity"][-_m:])
            _pe["equity"], _pe["dates"] = _blended, _pe["dates"][-_m:]
            _preset_weights = {s: w * (1.0 - _total_core) for s, w in _preset_weights.items()}
            if _qqq_pct > 0:
                _preset_weights["QQQ"] = _preset_weights.get("QQQ", 0.0) + _qqq_pct
            if _mc_pct > 0 and _mc_top:                   # top-10 réparti PAR market cap (sinon égal)
                _w = _mc_w or {s: 1.0 / len(_mc_top) for s in _mc_top}
                _sw = sum(_w.get(s, 0.0) for s in _mc_top) or 1.0
                for _s in _mc_top:
                    _preset_weights[_s] = _preset_weights.get(_s, 0.0) + _mc_pct * _w.get(_s, 0.0) / _sw
            if _sm_pct > 0 and _sm_holds:                 # momentum sectoriel : équipondéré sur les titres tenus
                _per = _sm_pct / len(_sm_holds)
                for _s in _sm_holds:
                    _preset_weights[_s] = _preset_weights.get(_s, 0.0) + _per
            _index_core_info.update({"enabled": True, "core_pct": round(_total_core, 2),
                                     "components": [{"kind": k, "pct": w} for _, w, k in _cores],
                                     "base_stats": _base_stats,
                                     "blended_stats": _curve_stats(_pe["equity"])})
    _core_px = float(_qqq_closes[-1]) if _qqq_closes else 0.0
    _core_sym = "QQQ"
    # blocs de courbes (preset pur + cœurs) → permet au script make index-core de balayer N'IMPORTE
    # quel ratio instantanément, sur la VRAIE mesure de production (source de vérité unique).
    _ic_curves = {"preset": _preset_pure, "qqq": list(_qqq_closes), "megacap": list(_mc_curve),
                  "sector_mom": list(_sm_curve), "dates": _preset_pure_dates, "sp": list(sp)}
    # JOURNAL DÉTAILLÉ + P&L du portefeuille de production (cœur QQQ + satellite preset) → justifie
    # la perf affichée (clic « Portefeuille (preset) » sur le dashboard). Prix réels, parts/cash.
    try:
        from packages.backtest.preset_backtest import preset_ledger
        _preset_ledger = preset_ledger(_tradeable_data, _quality, asset_classes=acmap, dd_target=_dd,
                                       band=0.03, init_cap=init_cap, max_trades=6000,
                                       core_closes=list(_qqq_closes) if _qqq_pct > 0 else None,
                                       core_pct=_qqq_pct, core_sym="QQQ")
    except Exception:  # noqa: BLE001
        _preset_ledger = {"available": False}
    # COURBE DU DASHBOARD = courbe du JOURNAL (exécution discrète réaliste, parts/cash) → le graphe
    # et l'historique des trades RÉCONCILIENT exactement (même source). Repli : blend continu / swing.
    if _preset_ledger.get("available") and len(_preset_ledger.get("equity", [])) > 30:
        _dash_metrics = PL.metrics_payload(_preset_ledger["equity"])
        _dash_equity = [{"t": d, "v": v} for d, v in zip(_preset_ledger["dates"], _preset_ledger["equity"])]
        _dash_dates = _preset_ledger["dates"]
        _dash_eq_curve = _preset_ledger["equity"]
    elif _pe.get("available"):
        _dash_metrics = PL.metrics_payload(_pe["equity"])
        _dash_equity = [{"t": d, "v": v} for d, v in zip(_pe["dates"], _pe["equity"])]
        _dash_dates = _pe["dates"]
        _dash_eq_curve = _pe["equity"]
    else:                                              # repli swing si preset indisponible
        _dash_metrics = PL.metrics_payload(equity)
        _dash_equity = PL.equity_series(equity, ts_list)
        _dash_dates = dates
        _dash_eq_curve = equity
    # Honnêteté statistique : PSR sur la courbe affichée (isolé — best-effort).
    _honesty = safe_section("honesty", _psr_block, _dash_eq_curve)
    # Exécution réelle (lit les comptes brokers) — calculée TÔT pour dimensionner chaque poche
    # sur le capital de SON compte (actions ← Alpaca, crypto ← Bitmart).
    _live = _live_with_rebalance(comp["rows"], acmap, portfolio_kpis, w_by_name,
                                 target_weights=_preset_weights, crypto_weights=_crypto_weights)
    _alp_cap = (_live["real"]["alpaca"]["equity"] or 0.0) or init_cap
    _bit_cap = _live["real"]["bitmart"]["equity"] or 0.0
    # Allocation PRESET détaillée (page Positions) : 2 poches, chacune sur le capital de son broker
    _preset_alloc = []
    _px_override = {_core_sym: _core_px} if _core_px > 0 else {}
    def _alloc_rows(weights, cap, ac_default):
        for s, w in sorted(weights.items(), key=lambda kv: -kv[1]):
            if w <= 0:
                continue
            r = route(s, acmap.get(s, ac_default))
            px = data[s][-1].close if data.get(s) else _px_override.get(s, 0.0)
            notion = round(w * cap, 2)
            _preset_alloc.append({"symbol": s, "sector": sector_of.get(s, ""),
                                  "asset_class": acmap.get(s, ac_default), "broker": r["broker"],
                                  "broker_symbol": r["broker_symbol"], "tradeable": r["tradeable"],
                                  "weight": round(w, 4), "notional": notion, "price": round(px, 2),
                                  "qty": round(notion / px, 4) if px else 0.0})
    _alloc_rows(_preset_weights, _alp_cap, "equity")     # actions/ETF → capital Alpaca
    _alloc_rows(_crypto_weights, _bit_cap, "crypto")     # crypto → capital Bitmart
    # Séries OHLC pour les graphiques cliquables (Positions/Trades/Réel) — bornées (~500 barres)
    # MARQUEURS achat/vente du PRESET (par symbole) → fléchés sur le graphe technique des pages
    # Trades & Positions, exactement aux dates des rebalancements (corrige l'absence de signaux).
    _preset_markers: dict[str, list] = {}
    for _t in (_preset_trades.get("trades", []) if _preset_trades.get("available") else []):
        _preset_markers.setdefault(_t["symbol"], []).append(
            {"t": _t["date"][:10], "side": "buy" if _t["side"] == "BUY" else "sell"})
    # MARQUEURS RÉELS (depuis les ordres exécutés Alpaca/Bitmart) → pages Positions & Trades RÉELLES
    _real_markers: dict[str, list] = {}
    for _o in _live["real"].get("trades", []):
        _sym = _o.get("symbol", "")
        if _sym:
            _real_markers.setdefault(_sym, []).append(
                {"t": str(_o.get("date", ""))[:10], "side": "buy" if _o.get("side") == "buy" else "sell"})
    # NEWS RECENTRÉES SUR TON PORTEFEUILLE : on reconstruit les lignes de sentiment à partir des
    # positions RÉELLES (Alpaca + Bitmart) + de l'allocation PRESET (production), pas du modèle legacy
    # → les actualités collent enfin à ce que tu détiens réellement.
    try:
        if _os.environ.get("QUANT_NEWS") == "1":
            from packages import sentiment as _Snews
            _pf_syms, _seen = [], set()
            for _s in ([p.get("symbol") for p in _live["real"]["positions"]]
                       + [o["symbol"] for o in _preset_alloc] + list(held)):
                if _s and _s not in _seen:
                    _seen.add(_s); _pf_syms.append(_s)
            _pf_syms = _pf_syms[:30]

            def _yahoo_sym(sym: str) -> str:               # crypto "BTC/USDT" → "BTC-USD" pour le flux Yahoo
                if acmap.get(sym) == "crypto" or "/" in sym:
                    return sym.split("/")[0].upper() + "-USD"
                return sym
            _new_rows = []
            for _s in _pf_syms:
                _r = _Snews.news_sentiment(_yahoo_sym(_s))
                _score, _n, _heads = _r["score"], _r["n"], _r["headlines"]
                if _n == 0:                                # repli momentum (hors-ligne) — cohérent
                    _b = data.get(_s)
                    if _b and len(_b) > 64:
                        _score = round(max(-1.0, min(1.0, (_b[-1].close / _b[-64].close - 1) * 3.0)), 4)
                _new_rows.append({"symbol": _s, "name": names.get(_s, ""), "sector": sector_of.get(_s, ""),
                                  "score": _score, "label": _Snews.label_of(_score), "n_news": _n,
                                  "headlines": _heads[:5]})
            if _new_rows:
                sentiment_sec["rows"] = _new_rows
                sentiment_sec["portfolio_driven"] = True
                _mood = round(sum(r["score"] for r in _new_rows) / len(_new_rows), 4)
                sentiment_sec["market_mood"] = _mood
                sentiment_sec["market_label"] = _Snews.label_of(_mood)
                sentiment_sec["source"] = "news RSS — recentré sur ton portefeuille (positions réelles + preset)"
    except Exception:  # noqa: BLE001
        pass
    # symboles cliquables = alloc preset + positions/ordres RÉELS + symboles tradés par le preset
    _chart_syms = ({o["symbol"] for o in _preset_alloc}
                   | {p.get("symbol") for p in _live["real"]["positions"]}
                   | {o.get("symbol") for o in _live["real"].get("trades", [])}
                   | set(_preset_markers.keys()) | set(_real_markers.keys())) - {""}
    _chart_series = {}
    for s in _chart_syms:
        b = data.get(s)
        if not b:
            continue
        mks = (_preset_markers.get(s) or []) + (_real_markers.get(s) or [])
        mks = [m for m in mks if m.get("t")]
        if mks:                                          # couvre depuis le 1er signal (sinon il est
            first = min(m["t"] for m in mks)             # hors fenêtre et invisible sur le graphe)
            idx = next((i for i, x in enumerate(b) if x.ts.isoformat()[:10] >= first), max(0, len(b) - 500))
            bb = b[max(0, idx - 10):][-2600:]
        else:
            bb = b[-500:]
        _chart_series[s] = [{"t": x.ts.isoformat()[:10], "o": round(x.open, 4), "h": round(x.high, 4),
                             "l": round(x.low, 4), "c": round(x.close, 4), "v": round(x.volume, 0)} for x in bb]
    # bougies RÉELLES Bitmart pour les positions/ordres crypto (absents de YAHOO.db)
    for _sym, _bars in (_live["real"].get("bitmart", {}).get("ohlcv", {}) or {}).items():
        if _bars and _sym not in _chart_series:
            _chart_series[_sym] = _bars
    # le cœur QQQ n'est pas dans l'univers → courbe cliquable depuis ses closes réels
    if _index_core_info.get("enabled") and _qqq_pct > 0 and len(_qqq_closes) > 1:
        _cc = [round(float(c), 4) for c in _qqq_closes[-500:]]
        _cd = _dash_dates[-len(_cc):] if len(_dash_dates) >= len(_cc) else []
        if _cd:
            _chart_series["QQQ"] = [{"t": d[:10], "o": c, "h": c, "l": c, "c": c, "v": 0}
                                    for d, c in zip(_cd, _cc)]
    # PERF PAR COMPTE — PRIORITÉ AUX DONNÉES RÉELLES (historique Alpaca / suivi equity quotidien).
    # Repli "modèle" (backtest du sleeve) UNIQUEMENT si le compte n'est pas connecté.
    from packages.execution.equity_history import series as _eq_series

    def _broker_perf(bd: dict, broker_key: str, model_curve: list | None) -> dict:
        if bd.get("ok"):                                   # compte connecté → on veut du RÉEL
            rc = bd.get("history") or []                   # Alpaca portfolio history (réel)
            if len(rc) < 10:
                rc = _eq_series(broker_key)                # sinon suivi quotidien persistant
            if len(rc) >= 10:
                return {**_curve_stats([p["v"] for p in rc]), "curve": rc, "source": "réel"}
            return {"available": False, "source": "réel-court",
                    "note": "Compte récent : historique réel en cours de constitution "
                            "(quelques jours de suivi nécessaires)."}
        if model_curve:                                    # non connecté → modèle (backtest sleeve)
            return {**_curve_stats([p["v"] for p in model_curve]), "curve": model_curve, "source": "modèle"}
        return {"available": False}

    _eq_model = ([{"t": d, "v": v} for d, v in zip(_pe["dates"], _pe["equity"])]
                 if _pe.get("available") else None)
    _cr_model = None
    try:
        _crypto_data = {s: b for s, b in data.items()
                        if acmap.get(s) == "crypto" or s.upper().endswith(("USDT", "USDC")) or "/USD" in s.upper()}
        if len(_crypto_data) >= 3:
            _pe_cr = preset_equity_daily(_crypto_data, {}, asset_classes=acmap, dd_target=_dd,
                                         top_k=12, min_names=3, max_weight=0.20, init_cap=init_cap)
            if _pe_cr.get("available"):
                _cr_model = [{"t": d, "v": v} for d, v in zip(_pe_cr["dates"], _pe_cr["equity"])]
    except Exception:  # noqa: BLE001
        pass
    _live["alpaca_perf"] = _broker_perf(_live["real"]["alpaca"], "alpaca", _eq_model)
    _live["bitmart_perf"] = _broker_perf(_live["real"]["bitmart"], "bitmart", _cr_model)
    # COMPARAISON COMPTES RÉELS vs INDICES (Alpaca vs Crypto vs S&P vs Nasdaq) pour le dashboard
    _cal_full = [b.ts for b in max(data.values(), key=len)]
    _account_cmp = _account_compare(
        _live["alpaca_perf"].get("curve", []) if _live["alpaca_perf"].get("source") == "réel" else [],
        _live["bitmart_perf"].get("curve", []) if _live["bitmart_perf"].get("source") == "réel" else [],
        sp, ndx, _cal_full)
    # PORTEFEUILLE RÉEL combiné (Alpaca + Bitmart) : courbe d'equity réelle + stats → ligne cliquable
    # du dashboard (réconcilie avec les ORDRES réellement exécutés + positions réelles).
    _alp_c = _live["alpaca_perf"].get("curve", []) if _live["alpaca_perf"].get("source") == "réel" else []
    _cr_c = _live["bitmart_perf"].get("curve", []) if _live["bitmart_perf"].get("source") == "réel" else []
    _real_portfolio = {"available": False}
    if _alp_c or _cr_c:
        _rdates = sorted(set(p["t"][:10] for p in _alp_c) | set(p["t"][:10] for p in _cr_c))

        def _ffill(cv):
            m = {p["t"][:10]: p["v"] for p in cv}
            out, last = [], None
            for d in _rdates:
                last = m.get(d, last)
                out.append(last if last is not None else 0.0)
            return out
        _comb = [a + b for a, b in zip(_ffill(_alp_c), _ffill(_cr_c))]
        if len(_comb) >= 2:
            _real_portfolio = {"available": True, "stats": _curve_stats(_comb),
                               "curve": [{"t": d, "v": round(v, 2)} for d, v in zip(_rdates, _comb)]}
    # BLACK-LITTERMAN : prior équipondéré + vues = conviction z-scorée → poids postérieurs
    try:
        import numpy as _np2
        from packages.portfolio.black_litterman import black_litterman, views_from_scores
        _wm = _np2.array([1.0 / len(cb_syms)] * len(cb_syms))
        if _edge_proven:                         # ticket #7 : vues seulement si edge prouvé
            _conv = {r["symbol"]: r.get("conviction") for r in conviction_sec.get("rows", [])}
            _scores = [_conv.get(s) if _conv.get(s) is not None else float("nan") for s in cb_syms]
            _P, _Q = views_from_scores(_scores)
        else:                                    # sinon : prior pur (aucune vue) = risk-parity-like
            _P, _Q = _np2.zeros((0, len(cb_syms))), _np2.zeros(0)
        optimal["black_litterman"] = black_litterman(cov, _wm, _P, _Q)["weights"]
    except Exception:  # noqa: BLE001
        pass
    # AUDIT BIAIS DU SURVIVANT (honnêteté des backtests longs)
    try:
        from packages.data.survivorship import survivorship_audit
        _uni_syms = [m["symbol"] if isinstance(m, dict) else m for m in full_universe]
        data_sec_extra = survivorship_audit(_uni_syms)
    except Exception:  # noqa: BLE001
        data_sec_extra = None
    # === PORTEFEUILLE & ANALYSE — COHÉRENT avec l'ALLOCATION DE PRODUCTION (preset + cœur QQQ) ===
    # Remplace l'analyse du swing legacy (Sharpe 0.17 / maxDD -53 % / revue 28 — hors-sujet) par
    # la même boîte à outils appliquée à ce qui est RÉELLEMENT alloué/tradé. Garde-fou : repli swing.
    _port_payload = {**comp, "metrics": PL.metrics_payload(equity),
                     "benchmarks": PL.benchmark_comparison(equity, benches), "strategy_label": "swing (legacy)",
                     "analysis": {"relative": rel, "risk": rm, "monte_carlo": mc,
                                  "mc_projection": mc_projection(rets, horizon=252, start_value=100.0, seed=1),
                                  "attribution": attr, "correlation": PL.correlation_payload(syms, corr, clusters),
                                  "risk_budget": risk_budget, "limits": limits, "stress": stress,
                                  "optimal_allocation": optimal, "recommended_allocation": recommended,
                                  "review": PL.review_payload(expert_review({**agg, **comp["totals"]})),
                                  "multi_strategy": multi_strategy}}
    if _pe.get("available") and _preset_alloc:
        try:
            _pl = (" + ".join([f"{int(round(_qqq_pct*100))}% QQQ"]*(_qqq_pct > 0)
                   + [f"{int(round(_mc_pct*100))}% TOP10"]*(_mc_pct > 0)
                   + [f"{int(round((1-_index_core_info['core_pct'])*100))}% preset"])
                   if _index_core_info.get("enabled") else "preset (risk-parity + DD-target)")
            _pr = [{"symbol": r["symbol"], "name": names.get(r["symbol"], r["symbol"]), "sector": r["sector"],
                    "asset_class": r["asset_class"], "current_value": r["notional"], "qty": r.get("qty", 0.0),
                    "weight_pct": r["weight"], "broker": r.get("broker", ""), "side": "long",
                    "avg_price": r.get("price", 0.0), "last": r.get("price", 0.0), "pnl": 0.0, "pnl_pct": 0.0,
                    "stance": stance_by.get(r["sector"], "neutral"), "ml_score": ml_scores.get(r["symbol"])}
                   for r in _preset_alloc]
            _pt = sum(r["current_value"] for r in _pr) or 1.0
            _pcomp = {"rows": _pr, "totals": {"current_value": round(_pt, 2), "n_positions": len(_pr),
                      "exposure_pct": 1.0, "pnl": 0.0, "pnl_pct": 0.0, "cost_basis": round(_pt, 2)}}
            _peq = _pe["equity"]; _prt = returns_from_equity(_peq)
            _prm = risk_metrics_fn(_prt)
            _pv = _prm.get("var_95", 0.0); _prm["var_horizons"] = [{"days": h, "var_95": round(_pv*(h**0.5), 4)} for h in (1, 10, 21)]
            _prm["var_cornish_fisher_95"] = cornish_fisher_var(_prt, 0.95); _prm["vol_ewma"] = ewma_vol(_prt)
            _prm["garch"] = fit_garch(_prt); _prm["var_backtest"] = backtest_var(_prt, _prm.get("var_95", 0.0), alpha=0.95)
            _prm["vol_regime"] = vol_regime(_prt, window=20)
            _prel = relative_metrics(_peq, bench_px); _pmc = monte_carlo(_prt, seed=1)
            _psy = [r["symbol"] for r in sorted(_pr, key=lambda x: -x["current_value"]) if r["symbol"] in data][:12]
            _pcorr_payload, _prb_payload, _popt, _prec = PL.correlation_payload(syms, corr, clusters), risk_budget, optimal, recommended
            if len(_psy) >= 2:
                _prb_by = {s: returns_from_equity([b.close for b in data[s]]) for s in _psy}
                _ps, _pc = correlation_matrix({k: list(v) for k, v in _prb_by.items()})
                _pcorr_payload = PL.correlation_payload(_ps, _pc, cluster(_ps, _pc, 0.7))
                _pcb, _pcov = covariance({s: list(_prb_by[s]) for s in _ps})
                _pwn = {r["symbol"]: r["current_value"]/_pt for r in _pr}
                _prbk = risk_contributions([_pwn.get(s, 0.0) for s in _pcb], _pcov)
                _prb_payload = {"symbols": _pcb, "contrib_pct": _prbk["contrib_pct"],
                                "portfolio_vol": _prbk["portfolio_vol"], "diversification_ratio": _prbk["diversification_ratio"]}
                _prm["factor_risk"] = pca_risk({s: list(_prb_by[s]) for s in _ps})
                _popt = {"symbols": _pcb, "current": [round(_pwn.get(s, 0.0), 4) for s in _pcb],
                         "hrp": [round(x, 4) for x in hrp_weights(_pcov)],
                         "min_variance": [round(x, 4) for x in min_variance_weights(_pcov)],
                         "risk_parity": [round(x, 4) for x in equal_risk_contribution(_pcov)]}
                try:                                     # allocation recommandée sur les titres PRESET
                    _prec = build_target(_pcb, _pcov, {s: _pwn.get(s, 0.0) for s in _pcb},
                                         dd_target=_dd_eff, band=0.03, max_gross=1.0)
                    for _k in ("dd_target_nominal", "dd_target_tail_adjusted", "tail_ratio",
                               "edge_proven", "edge_note", "preset_backtest"):
                        if _k in recommended:
                            _prec[_k] = recommended[_k]
                except Exception:  # noqa: BLE001
                    _prec = recommended
            _pwn = {r["symbol"]: r["current_value"]/_pt for r in _pr}
            _pws, _pwc = {}, {}
            for r in _pr:
                _pws[r["sector"]] = _pws.get(r["sector"], 0.0) + r["current_value"]/_pt
                _pwc[r["asset_class"]] = _pwc.get(r["asset_class"], 0.0) + r["current_value"]/_pt
            _plim = concentration_report(_pwn, _pws, max_name=0.20, max_sector=0.40)
            _pstress = {"scenarios": scenario_analysis(_pwc), "hedge": hedge_suggestion(_pwc, target_max_loss=-0.15)}
            _pagg = {**PL.metrics_payload(_peq), **_prel, **_prm, **_pmc}
            _port_payload = {**_pcomp, "metrics": PL.metrics_payload(_peq),
                             "benchmarks": PL.benchmark_comparison(_peq, benches), "strategy_label": _pl,
                             "analysis": {"relative": _prel, "risk": _prm, "monte_carlo": _pmc,
                                          "mc_projection": mc_projection(_prt, horizon=252, start_value=100.0, seed=1),
                                          "correlation": _pcorr_payload, "risk_budget": _prb_payload,
                                          "limits": _plim, "stress": _pstress, "optimal_allocation": _popt,
                                          "recommended_allocation": _prec,
                                          "review": PL.review_payload(expert_review({**_pagg, **_pcomp["totals"]})),
                                          "multi_strategy": multi_strategy}}
        except Exception:  # noqa: BLE001 — au moindre souci, on garde l'analyse swing (jamais de page cassée)
            pass
    return {
        "meta": {
            "generated_at": now.isoformat(),
            "last_bar": last_bar.isoformat(),
            "period_start": start.isoformat(),
            "delay_minutes": 15,                 # flux différé 15 min (EOD/synthétique)
            "mode": data_mode,
            "audit": _audit_report,              # rapport d'intégrité PwC (None si QUANT_AUDIT inactif)
            "cov_cache": _cov_cache_stats,       # hit-rate du cache de covariance (gain réel en prod)
            "data_synthetic": data_mode.startswith("synthetic"),
            "data_warning": ("⚠️ DONNÉES FACTICES (synthétiques) — démo UI uniquement, NE PAS "
                             "décider ni backtester dessus. Branche QUANT_PRICE_DB."
                             if data_mode.startswith("synthetic") else None),
            "strategy": "swing",
            "initial_capital": init_cap,
            "universe_size": len(symbols),
            "traded_assets": len({t.instrument for t in all_trades}),
            "n_trades": len(all_trades),
            "profile": "offensif · moyen-long terme",
        },
        "dashboard": {
            "as_of": last_bar.isoformat(),
            "regime": {**PL.regime_payload(regime, expo), "macro_real": _macro_real,
                       "macro_sources": _macro_sources},
            "metrics": _dash_metrics,                 # PRESET (production), pas le swing legacy
            "honesty": _honesty,                       # PSR / honnêteté statistique (manifeste)
            "equity": _dash_equity,
            "account_compare": _account_cmp,           # comptes réels (Alpaca/Crypto) vs S&P/Nasdaq
            "real_portfolio": _real_portfolio,         # courbe RÉELLE combinée (Alpaca+Bitmart) + stats
            "real_trades": _live["real"].get("trades", []),     # ordres RÉELS exécutés (journal réel)
            "real_positions": _live["real"].get("positions", []),  # positions RÉELLES + P&L
            "index_core": _index_core_info,            # cœur(s) indiciel(s) + satellite preset
            "strategy_label": (
                " + ".join([f"{int(round(_qqq_pct*100))}% QQQ"] * (_qqq_pct > 0)
                           + [f"{int(round(_mc_pct*100))}% TOP10"] * (_mc_pct > 0)
                           + [f"{int(round((1-_index_core_info['core_pct'])*100))}% preset"])
                if _index_core_info.get("enabled")
                else ("preset (risk-parity + DD-target)" if _pe.get("available") else "swing")),
            "benchmarks": _bench_series({"S&P 500": sp, "Nasdaq 100": ndx}, _dash_dates, init_cap),
            "dates": _dash_dates,
            "positions": comp["rows"], "totals": comp["totals"],
            "preset_allocation": _preset_alloc,        # allocation PRESET (production) → page Positions
            "alloc_capital": {"alpaca": round(_alp_cap, 2), "bitmart": round(_bit_cap, 2),
                              "total": round(_alp_cap + _bit_cap, 2)},  # base réelle par compte
            "chart_series": _chart_series,             # OHLC cliquables (preset + positions réelles)
            "portfolio": portfolio_kpis,
            "position_series": position_series,
            "position_markers": position_markers,
            "preset_markers": _preset_markers,         # signaux achat/vente du preset (par symbole)
            "real_markers": _real_markers,             # signaux achat/vente RÉELS (ordres brokers)
            "earnings_risk": _earnings_risk(held),
            "trade_stats": trade_stats,
            "vix": vix_now, "vix_playbook": _vix_playbook(vix_now),
            "vix_series": vix[::max(1, n // 240)],   # sous-échantillonné pour le graphe
        },
        "screener": screener,
        "screen": screen_sec,
        "prediction_markets": safe_section("prediction_markets", _prediction_section,
                                           held, acmap, names),
        "crypto_onchain": safe_section("crypto_onchain", _onchain_section, held, acmap),
        "crypto_cockpit": safe_section("crypto_cockpit", _crypto_cockpit_section),
        "portfolio": _port_payload,
        "trades": [PL.trade_payload(t) for t in recent],
        "open_trades": comp["rows"],
        "trade_stats": trade_stats,
        "preset_trades": _preset_trades,           # journal des rebalancements du preset (production)
        "preset_ledger": _preset_ledger,           # journal détaillé + P&L (justifie la perf du dashboard)
        "index_core_curves": _ic_curves,           # courbes preset/QQQ/megacap → sweeps instantanés
        "universe": safe_section("universe", _universe_section, full_universe),
        "data": {**safe_section("data", _data_section, data, acmap, len(full_universe), data_mode),
                 "fundamentals_provider": fundamentals_sec.get("source", "—"),   # source RÉELLE utilisée (runtime)
                 **({"survivorship": data_sec_extra} if data_sec_extra else {})},
        "themes": themes,
        "ml": ml,
        "sentiment": sentiment_sec,
        "fundamentals": fundamentals_sec,
        "investors": investors_sec,
        "conviction": conviction_sec,
        "live": _live,
    }


def _earnings_risk(held: list) -> list[dict]:
    """Positions détenues dont les résultats sont imminents (risque binaire). Gate QUANT_EARNINGS=1."""
    import os
    if os.environ.get("QUANT_EARNINGS") != "1" or not held:
        return []
    try:
        from packages.strategies.earnings_blackout import flag_positions
        return flag_positions(list(held)[:25], within=7)
    except Exception:  # noqa: BLE001
        return []


def _account_compare(alp_curve: list, cr_curve: list, sp: list, ndx: list, cal_dates: list) -> dict:
    """Compare les comptes RÉELS (Alpaca, Crypto/Bitmart) vs S&P 500 / Nasdaq 100, rebasés à 100 sur
    la fenêtre où des données réelles existent. Courbes réelles courtes au début (compte récent)."""
    import numpy as np

    def by_date(px, cal):
        if not px:
            return {}
        off = len(cal) - len(px)
        return {cal[off + i].date().isoformat(): float(px[i]) for i in range(len(px)) if off + i >= 0}

    spd, ndxd = by_date(sp, cal_dates), by_date(ndx, cal_dates)
    reals = {}
    if len(alp_curve) >= 2:
        reals["Alpaca (réel)"] = {str(p["t"])[:10]: p["v"] for p in alp_curve}
    if len(cr_curve) >= 2:
        reals["Crypto (réel)"] = {str(p["t"])[:10]: p["v"] for p in cr_curve}
    if not reals:
        return {"available": False}
    axis = sorted(set().union(*[set(d) for d in reals.values()]))

    def stats(vals):
        v = np.asarray(vals, float)
        if v.size < 2:
            return {"return": 0.0, "cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0}
        r = v[1:] / v[:-1] - 1
        tot = float(v[-1] / v[0] - 1)
        sd = float(r.std())
        mdd = float((v / np.maximum.accumulate(v) - 1).min())
        cagr = float((1 + tot) ** (252.0 / len(r)) - 1) if tot > -1 else -1.0
        return {"return": round(tot, 4), "cagr": round(cagr, 4),
                "sharpe": round(r.mean() / sd * 252 ** 0.5, 2) if sd > 0 else 0.0, "maxdd": round(mdd, 4)}

    def build(dmap):
        out, last = [], None
        for d in axis:
            if d in dmap:
                last = dmap[d]
            if last is not None:
                out.append((d, last))
        if len(out) < 2:
            return None
        base = out[0][1] or 1.0
        return [{"t": d, "v": round(100 * v / base, 2)} for d, v in out], stats([v for _, v in out])

    series, kpis = {}, []
    for name, dmap in list(reals.items()) + [("S&P 500", spd), ("Nasdaq 100", ndxd)]:
        b = build(dmap)
        if b:
            series[name], st = b
            kpis.append({"name": name, **st})
    return {"available": bool(series), "window": [axis[0], axis[-1]], "series": series, "kpis": kpis}


def _bench_series(benches: dict, dates: list, init_cap: float) -> dict:
    """Rebasera chaque benchmark sur le capital initial, aligné sur les dates de l'equity (overlay)."""
    out = {}
    for name, px in benches.items():
        if not px:
            continue
        L = min(len(px), len(dates))
        base = px[len(px) - L] or 1.0
        out[name] = [{"t": dates[len(dates) - L + i],
                      "v": round(init_cap * px[len(px) - L + i] / base, 2)} for i in range(L)]
    return out


def _top_traded(journal, k: int) -> list[tuple[str, int]]:
    """k symboles les plus tradés (pour une matrice de corrélation lisible)."""
    counts: dict[str, int] = {}
    for t in journal.all():
        counts[t.instrument] = counts.get(t.instrument, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
