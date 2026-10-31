"""Live : positions, rééquilibrage, sentiment par position.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations


def _live_section(positions: list, acmap: dict, kpis: dict | None = None,
                  target_weights: dict | None = None, crypto_weights: dict | None = None) -> dict:
    """Portefeuille RÉEL : statut de connexion aux brokers (Alpaca actions, Bitmart crypto).
    Non connecté tant que les clés API ne sont pas fournies → ordres « cibles » à répliquer.
    Si `target_weights` est fourni (allocation PRESET de production), les ordres cibles en découlent ;
    sinon on réplique les poids du portefeuille modèle (swing)."""
    import os
    alp = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_API_SECRET"))
    from packages.execution.venues import venue_crypto as _venue_crypto
    _VC = _venue_crypto()                      # place crypto active (QUANT_CRYPTO_VENUE, déf. Binance)
    bit = _VC.configuree()
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

    def _place_crypto():
        """Place crypto ACTIVE (Binance par défaut). Le nom vient de la place, plus du code :
        changer de place ne demande plus de renommer une trentaine de fichiers."""
        d = {"name": _VC.nom, "venue": _VC.cle, "configured": bit, "ok": False,
             "equity": 0.0, "positions": [], "error": None}
        if not bit:
            d["error"] = f"clés absentes (.env) : {', '.join(_VC.env)}"; return d
        try:
            b = _VC.broker(dry_run=False)
            d["equity"] = round(float(b.equity()), 2)
            d["positions"] = b.positions_detailed()   # positions SPOT RÉELLES enrichies
            # Toutes les places n'exposent pas le même surface : une méthode absente donne une
            # section VIDE, jamais une exception qui priverait le site de la poche crypto.
            d["orders"] = b.orders() if hasattr(b, "orders") else []
            d["open_orders"] = b.open_orders() if hasattr(b, "open_orders") else []
            _csyms = {p["symbol"] for p in d["positions"]} | {o.get("symbol") for o in d["orders"]}
            d["ohlcv"] = ({s: bars for s in _csyms if s and (bars := b.ohlcv(s))}
                          if hasattr(b, "ohlcv") else {})
            d["ok"] = True
        except Exception as e:  # noqa: BLE001
            d["error"] = str(e)[:160]
        return d

    # Interroge les DEUX brokers EN PARALLÈLE (threads — appels HTTP bloquants alpaca-py/ccxt) :
    # réconciliation ~2× plus rapide quand les deux comptes sont connectés. Chaque _broker() est
    # déjà isolé/try-except → non bloquant et sortie identique au mode série.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as _ex:
        _fa, _fb = _ex.submit(_alpaca), _ex.submit(_place_crypto)
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
        # « crypto » = la place ACTIVE, quelle qu'elle soit. L'alias « bitmart » a été retiré :
        # le front lit la place dans les données, plus aucun consommateur ne dépend du nom.
        "alpaca": a_d, "crypto": b_d,
    }
    # enregistre l'equity réelle du jour (construit l'historique réel par broker)
    try:
        from packages.execution.equity_history import record as _eq_record
        # QML-024 : Alpaca illisible → rien (`record` le refuse) ; crypto seulement si elle
        # a répondu ET n'est pas un bac à sable. Même périmètre que `run_live.releve_equity`.
        if a_d["ok"]:
            _eq_record({"alpaca": a_d["equity"],
                        **({_VC.cle: b_d["equity"]}
                           if b_d["ok"] and b_d["equity"] > 0 and not _VC.en_testnet()
                           else {})})
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
        # Ère paper (ADR-0029) : crypto → capital ALPACA. Base hors whitelist Alpaca → EXCLUE
        # de l'univers papier (log explicite), jamais routée vers Bitmart (OFF, futur-live gated).
        from packages.common.logging import get_logger as _get_logger
        _clog = _get_logger("snapshot.routing")
        for s, w in sorted((crypto_weights or {}).items(), key=lambda kv: -kv[1]):
            if w <= 0:
                continue
            r = _route(s, "crypto")
            if not r["tradeable"]:
                _clog.info("crypto exclue de l'univers papier : %s (%s)", s, r["reason"])
                continue
            targets.append({"symbol": s, "broker": r["broker"], "broker_symbol": r["broker_symbol"],
                            "asset_class": "crypto", "weight_pct": round(w, 4),
                            "side": "long", "tradeable": True, "capital": "alpaca"})
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
            {"name": "Alpaca", "scope": "Actions & ETF US + Crypto paper (paires /USD)", "connected": alp,
             "paper": True, "env": ["ALPACA_API_KEY", "ALPACA_API_SECRET"]},
            {"name": _VC.nom, "venue": _VC.cle,
             "scope": f"{_VC.portee} — adaptateur futur-live (OFF, gated)", "connected": bit,
             "paper": False, "env": list(_VC.env)},
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


def _sentiment_section(held: list, names: dict, sector_of: dict, data: dict) -> dict:
    """Sentiment / news par position. News RSS réelles si `QUANT_NEWS=1` (FinBERT si dispo),
    sinon **repli hors-ligne** déterministe dérivé du momentum 63 jours (cohérent, jamais vide)."""
    import os

    from packages import sentiment as S
    from packages.sentiment.portefeuille import score_momentum as _momentum

    from packages.sentiment.origine import humeur as _humeur
    from packages.sentiment.origine import qualifier_ligne

    use_news = os.environ.get("QUANT_NEWS") == "1"
    rows: list[dict] = []
    for s in (held or [])[:30]:
        score_news, n, heads = None, 0, []
        if use_news:
            r = S.news_sentiment(s)
            score_news, n, heads = r["score"], r["n"], r["headlines"]
        bars = data.get(s)
        tendance = _momentum([b.close for b in bars]) if bars else None
        qual = qualifier_ligne(n, score_news if n else None, tendance)
        rows.append({"symbol": s, "name": names.get(s, ""), "sector": sector_of.get(s, ""),
                     "score": qual["score"], "label": qual["label"], "origine": qual["origine"],
                     "n_news": n, "headlines": heads[:5]})
    meta_h = _humeur(rows)
    mood = meta_h["market_mood"]
    has_news = meta_h["humeur_est_fil"]
    # Δsentiment (révision) : meilleur prédicteur EOD que le niveau. Persisté quotidiennement.
    try:
        from packages.sentiment.history import record_and_delta
        _delta = record_and_delta({r["symbol"]: r["score"] for r in rows if r["score"] is not None})
        for r in rows:
            if r["score"] is None:
                r["score_change"] = None
            else:
                r["score_change"] = _delta["by_symbol"].get(r["symbol"])
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
        "engine": S.engine_name() if has_news else "momentum 63 j (repli hors-ligne)",
        "source": "news RSS" if has_news else "tendance 63 j — pas un fil d'actualité",
        "market_mood": mood, "market_label": meta_h["market_label"],
        "humeur_est_fil": has_news,
        "n_lignes_news": meta_h["n_lignes_news"],
        "n_lignes_tendance": meta_h["n_lignes_tendance"],
        "n_lignes_vides": meta_h["n_lignes_vides"],
        "mood_change": mood_change,
        "rows": rows, "market_news": market_news, "macro_news": macro_news,
    }
