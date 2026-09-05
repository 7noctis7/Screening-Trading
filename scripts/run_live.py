"""Exécuteur live — réplique le portefeuille MODÈLE chez les brokers (DRY-RUN par défaut).

Routage : actions/ETF → **Alpaca (paper)** · crypto /USDC → **Bitmart** (ccxt).
Sécurité maximale :
  - DRY-RUN par défaut : affiche les ordres, n'envoie RIEN ;
  - mode réel uniquement avec `--live --yes` ET clés API présentes ;
  - Alpaca reste en **paper** (is_paper) ; Bitmart protégé par `dry_run` tant que `--live`
    n'est pas passé. Permissions API minimales, jamais de retrait.

  python scripts/run_live.py                 # aperçu (dry-run) des ordres cibles
  python scripts/run_live.py --live --yes    # envoie en paper/crypto (clés requises)

Chaque run réel JOURNALISE ses ouvertures (`data/journal.db`, `legacy=0`) avec les features figées
à la DÉCISION (cf. `packages/execution/live_journal.py`) → alimente la calibration ML (P0-4).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _parse_args():
    ap = argparse.ArgumentParser(description="Réplique le portefeuille modèle (dry-run par défaut)")
    ap.add_argument("--live", action="store_true", help="envoyer réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true", help="confirmation obligatoire pour le mode --live")
    ap.add_argument("--equity", type=float, default=None,
                    help="dry-run : SIMULE un portefeuille neuf de ce capital (détenu "
                         "ignoré). Sans lui, l'aperçu lit l'equity et les positions "
                         "RÉELLES. En live : toujours l'equity réelle du broker.")
    return ap.parse_args()


def _setup_alerts(dry: bool):
    """Bus + moteur d'alertes PROD (Console + Telegram/Discord si clés). None en dry-run."""
    if dry:
        return None, None
    from packages.alerts.wiring import attach_to_bus
    from packages.common.event_bus import EventBus
    bus = EventBus()
    return bus, attach_to_bus(bus)


def _kill_switch(bus):
    """Alertes TradingView → veto / réduction d'exposition. Retourne le facteur `reduce` ∈ [0,1]."""
    from packages.mcp_tradingview.alerts import (
        AGE_MAX_DEFAUT,
        fetch_tv_technical_alerts,
        to_risk_veto,
    )
    # Appel SANS filtre d'âge jusqu'au 25/08 : une alerte critique reçue des
    # semaines plus tôt
    # bloquait encore tout le portefeuille, jusqu'à effacement manuel du drop.
    risk = to_risk_veto(fetch_tv_technical_alerts(max_age_s=AGE_MAX_DEFAUT))
    if risk.get("n_sans_date"):
        print(f"⚠️  {risk['n_sans_date']} alerte(s) TV sans date lisible — conservées par "
              "prudence (elles pèsent sur la décision sans pouvoir être périmées)")
    for r in risk.get("severites_reinterpretees", []):
        print(f"⚠️  sévérité TV réinterprétée : {r}")
    reduce = 0.0 if risk.get("veto") else float(risk.get("reduce", 1.0))
    if risk.get("veto"):
        print(f"⛔ KILL-SWITCH ACTIF (alertes TV critiques) : {', '.join(risk['reasons']) or '—'}")
        print("   → exposition forcée à 0, aucun ordre ne sera envoyé.")
        if bus:
            from packages.common.event_bus import Topic
            bus.publish(Topic.KILL_SWITCH,
                        {"drawdown": "veto TV: " + (", ".join(risk["reasons"]) or "—")})
    elif reduce < 1.0:
        print(f"⚠️  Alertes TV : exposition réduite ×{reduce:.2f} ({', '.join(risk['reasons']) or '—'})")
    return reduce


def _alpaca_ou_rien():
    """Alpaca paper, best-effort — l'indisponibilité est DITE, jamais silencieuse."""
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        return AlpacaBroker(paper=True)                   # actions TOUJOURS en paper
    except Exception as e:  # noqa: BLE001
        print(f"Alpaca indisponible ({str(e)[:60]}) → actions ignorées")
        return None


def _make_brokers(dry: bool, apercu: bool = False):
    """(alpaca paper, place crypto). Rien en SIMULATION ; Alpaca seul en APERÇU.

    Un aperçu doit lire l'equity et les positions RÉELLES, sinon il n'annonce pas le run
    suivant — mesuré le 05/09 : sans broker construit, l'aperçu affichait `détenu
    0 $` sur un compte plein, puis `cible 0 $` une fois l'equity lue sur un broker
    inexistant.
    AUCUN ordre ne peut partir pour autant : `_reconcile` sort sur `if dry or broker is
    None` AVANT tout envoi. La place crypto reste absente en dry-run — `cron_live.sh` la
    neutralise de toute façon, et les paires crypto d'Alpaca sont dans ses positions.

    La place crypto n'est pas codée en dur : elle vient de QUANT_CRYPTO_VENUE (défaut
    Binance, taker 0,10 % contre 0,25 % chez Bitmart). Cf. packages/execution/venues.
    """
    if dry:
        return (_alpaca_ou_rien(), None) if apercu else (None, None)
    from packages.execution.venues import venue_crypto
    _v = venue_crypto()
    try:
        crypto = _v.broker(dry_run=False)
    except Exception as e:  # noqa: BLE001 — clés/dépendance absentes : on continue
        print(f"{_v.nom} indisponible ({str(e)[:60]}) → poche crypto ignorée")
        crypto = None
    return _alpaca_ou_rien(), crypto


# Garde-fous d'exécution (audit 07/15) : inconnu ≠ zéro, fail-loud, kill-switch DD réel.
# Extraits dans packages/execution/live_guards.py (règle <400 l./fichier).


def _nsym(s: str) -> str:
    """Clé de matching : Alpaca renvoie les POSITIONS sans slash (BTCUSD) mais les CIBLES
    sont en BTC/USD → sans normalisation, le même actif compte 2 fois (fix 07/07 : la
    réconciliation RACHETAIT BTC chaque jour tout en échouant à vendre « l'autre »)."""
    return (s or "").replace("/", "").replace("-", "").upper()


def _broker_targets(targets, bname: str, cap: float, reduce: float, cur: dict) -> tuple[dict, float]:
    """Carte cible {clé normalisée: {o, val, sym}} d'UN broker + bande d'inaction.

    ANTI-LEVIER : Σ cibles plafonnée à 100 % du capital du broker. Le détenu hors-cible
    est ajouté avec val=0 (liquidation). `sym` = symbole à ENVOYER au broker (format
    cible « BTC/USD » si connue, sinon le format position)."""
    tgs = [o for o in targets if (o.get("capital") == "bitmart") == (bname == "Bitmart")]
    sw = sum(o["weight_pct"] for o in tgs)
    scale = min(1.0, 1.0 / sw) if sw > 1.0 else 1.0
    tgt: dict[str, dict] = {}
    for o in tgs:
        bsym = o.get("broker_symbol", o["symbol"])
        tgt[_nsym(bsym)] = {"o": o, "val": o["weight_pct"] * cap * reduce * scale, "sym": bsym}
    for bsym in cur:                                      # détenu hors-cible → liquidation (cible 0)
        tgt.setdefault(_nsym(bsym), {"o": None, "val": 0.0, "sym": bsym})
    return tgt, max(0.005 * cap, 5.0)                     # bande : 0,5 % du capital, min 5 $


def _log_rejet(bsym: str, bname: str, intention, issue: str) -> None:
    """Trace structurée d'un refus courtier. Best-effort : ne casse jamais le run."""
    try:
        import logging
        logging.getLogger("live.execution").error(
            "ordre refusé par le courtier",
            extra={"symbole": bsym, "broker": bname, "action": intention.action,
                   "montant": intention.montant, "issue": issue})
    except Exception:  # noqa: BLE001
        pass


def _reconcile(targets, brokers, reduce, alert_engine, dry) -> tuple[int, list, list]:
    """Réconciliation idempotente + ANTI-LEVIER. Retourne (nb ordres, ouvertures, ventes).

    On n'échange que le DELTA (cible − détenu). `opened` = achats RÉELLEMENT envoyés (à
    journaliser, `legacy=0`) ; `sold` = ventes RÉELLEMENT envoyées (round-trip Phase 2)."""
    from dataclasses import replace

    from packages.common.retry import retry
    from packages.core.models import Side
    from packages.execution.market_calendar import (
        feries_a_jour,
        is_open,
        prochaine_ouverture,
        raison_fermeture,
    )
    from packages.execution.order_outcome import compte_comme_envoye, resume
    from packages.execution.routing import classe_actif as _classe_actif
    # ÉCHAPPATOIRE EXPLICITE. `QUANT_IGNORE_SESSION=1` envoie quand même hors séance —
    # utile pour empiler des ordres avant l'ouverture en connaissance de cause, et pour
    # les tests qui isolent le PORTAIL DE RISQUE du calendrier. Jamais le défaut : un
    # ordre qui ne peut pas se remplir doit être dit, pas envoyé dans le vide.
    _verif_seance = os.environ.get("QUANT_IGNORE_SESSION", "") != "1"
    sent, opened, sold, differes, rejetes = 0, [], [], [], []
    if _verif_seance and not feries_a_jour():
        print("  ⚠️  fériés NYSE périmés — voir packages/execution/market_calendar")
    for bname, broker, cap, cur in brokers:
        tgt, band = _broker_targets(targets, bname, cap, reduce, cur)
        curn = {}                                             # détenu par clé NORMALISÉE (cumul)
        for k, v in cur.items():
            curn[_nsym(k)] = curn.get(_nsym(k), 0.0) + v
        from packages.execution.rebalance_plan import decider
        from packages.risk.order_gate import EtatCompte, Limites, evaluer, ligne_journal
        # PORTAIL DE RISQUE — indépendant de la stratégie, lu depuis l'environnement
        # seul.
        # Jusqu'ici les limites du projet (`packages.risk`) n'existaient que dans
        # les démos :
        # le chemin de production n'avait aucun veto PAR ORDRE.
        _lim = Limites.depuis_env()
        _expo = sum(abs(v) for v in curn.values())
        _npos = sum(1 for v in curn.values() if abs(v) > 0)
        if not dry:
            print(f"  portail de risque : {_lim.resume()} · brut actuel {_expo:.0f}$ / {cap:.0f}$")
        for nkey, info in sorted(tgt.items(), key=lambda kv: -kv[1]["val"]):
            o, bsym = info["o"], info["sym"]
            detenu = curn.get(nkey, 0.0)
            delta = info["val"] - detenu                      # >0 acheter · <0 vendre
            tag = f"  {bsym:14s} {bname:8s} cible {info['val']:8.0f}$ détenu {detenu:8.0f}$ Δ {delta:+8.0f}$"
            if o is not None and o.get("tradeable") is False:
                print(tag + "  non négociable"); continue
            # SÉANCE OUVERTE ? Les actions partent en TimeInForce.DAY sans
            # extended_hours :
            # hors séance l'ordre ne peut PAS se remplir. La crypto (GTC, 24/7) passe.
            # Constat du 26/08 : sans ce contrôle, un run lancé d'Europe (03 h à NY)
            # remplissait tout le crypto et AUCUNE action — 28 % de cash restaient à
            # la place du satellite, sans un mot au journal. On REPORTE en le disant.
            _ac = _classe_actif(bsym, (o or {}).get("asset_class") or "")
            if _verif_seance and not is_open(asset_class=_ac):
                _pq = prochaine_ouverture()
                print(tag + f"  ⏸  REPORTÉ — {raison_fermeture(asset_class=_ac)}"
                            f" · prochaine ouverture {_pq:%d/%m %H:%M ET}")
                differes.append({"symbol": bsym, "broker": bname, "asset_class": _ac,
                                 "montant": round(info["val"] - detenu, 2)})
                continue
            # Décision déléguée (testée) : solder hors bande, ne pas ouvrir sous le
            # plancher.
            intention = decider(info["val"], detenu, band)
            if not intention.agit:
                print(tag + f"  ✓ {intention.motif}"); continue
            # DERNIÈRE BARRIÈRE : le portail peut réduire ou refuser, jamais
            # augmenter. Un
            # désengagement le traverse toujours (le bloquer augmenterait le risque).
            _etat = EtatCompte(equity=cap, exposition_brute=_expo, n_positions=_npos,
                               detenu_ligne=detenu)
            _v = evaluer(intention.action, intention.montant, _etat, _lim,
                         liquidation=intention.liquidation)
            if not _v.autorise:
                print(tag + f"  ⛔ REFUSÉ par le portail [{_v.regle}] {_v.motif}")
                if alert_engine:
                    from packages.alerts import Alert, Severity
                    alert_engine.emit(Alert("risk", Severity.WARNING,
                        f"Ordre {bsym} refusé par le portail de risque : {_v.motif}"))
                continue
            if _v.reduit:
                print(tag + f"  ⚠️  {_v.motif}")
                intention = replace(intention, montant=_v.montant)
            if not dry:
                print("  " + ligne_journal(bsym, intention.action, _v.montant, _v))
            side = Side.LONG if intention.action == "acheter" else Side.SHORT
            if dry or broker is None:
                print(tag + f"  {'aperçu' if dry else 'broker absent'} ({intention.action})"); continue
            try:
                if intention.liquidation and hasattr(broker, "close_position"):
                    # Sortie totale EN QUANTITÉ : aucun résidu, donc aucune
                    # poussière future.
                    _res = retry(lambda: broker.close_position(bsym), attempts=3)
                else:
                    _res = retry(
                        lambda: broker.submit_notional(bsym, side, intention.montant),
                        attempts=3)
                # UN ORDRE ENVOYÉ N'EST PAS UN ORDRE EXÉCUTÉ. `sent += 1` dès l'absence
                # d'exception comptait comme réussi un ordre qu'Alpaca venait de
                # REJETER : le récapitulatif annonçait des ordres partis alors que rien
                # n'était passé. C'est ce trou qui a laissé le satellite actions vide
                # sans une ligne de journal (ADR-0040).
                if not compte_comme_envoye(_res):
                    print(tag + "  " + resume(_res))
                    rejetes.append({"symbol": bsym, "broker": bname,
                                    "action": intention.action,
                                    "montant": round(intention.montant, 2),
                                    "issue": resume(_res)})
                    _log_rejet(bsym, bname, intention, resume(_res))
                    continue          # ni compté, ni journalisé comme une ouverture
                sent += 1
                # Le plafond d'exposition doit voir les ordres DÉJÀ envoyés dans
                # cette boucle,
                # sinon chacun est jugé contre l'état initial et la somme dépasse la
                # limite.
                _expo += intention.montant if intention.action == "acheter" else -intention.montant
                if intention.action == "acheter" and detenu <= 0:
                    _npos += 1
                print(tag + {"acheter": "  ▲ achat", "alleger": "  ▼ vente",
                             "solder": "  ▼ SOLDE (quantité)"}[intention.action])
                if delta > 0 and o is not None:               # ACHAT/ADD → ouverture à journaliser
                    opened.append({"symbol": o["symbol"], "venue": bname, "broker_symbol": bsym,
                                   "asset_class": o.get("asset_class"), "weight_pct": o.get("weight_pct")})
                elif delta < 0:                               # VENTE/REDUCE → round-trip à fermer
                    sold.append({"symbol": (o or {}).get("symbol", bsym), "venue": bname,
                                 "broker_symbol": bsym, "notional": abs(delta)})
            except Exception as e:  # noqa: BLE001
                # `str(e)[:40]` tronquait le message : un rejet de courtier (« invalid
                # time_in_force », « market closed »…) devenait illisible, et c'est
                # exactement pourquoi le satellite actions vide est resté invisible.
                # Le motif COMPLET va au journal structuré, un extrait large à l'écran.
                _msg = str(e).replace("\n", " ")
                print(tag + f"  ❌ ÉCHEC après retries : {_msg[:200]}")
                try:
                    import logging
                    logging.getLogger("live.execution").error(
                        "ordre refusé",
                        extra={"symbole": bsym, "broker": bname,
                               "action": intention.action,
                               "montant": intention.montant, "erreur": _msg})
                except Exception:  # noqa: BLE001 — journaliser ne casse jamais le run
                    pass
                if alert_engine:
                    from packages.alerts import Alert, Severity
                    alert_engine.emit(Alert("execution", Severity.CRITICAL,
                        f"Ordre {'achat' if delta > 0 else 'vente'} {bsym} ({bname}) échoué "
                        f"après retries : {str(e)[:80]}",
                        dedup_key=f"execution:submit_fail:{bsym}"))
    if rejetes:
        _tr = f"{sum(abs(r['montant']) for r in rejetes):,.0f}".replace(",", " ")
        print(f"\n  ❌ {len(rejetes)} ordre(s) REFUSÉ(S) par le courtier, "
              f"{_tr}$ au total.")
        print("     Ils ne comptent PAS comme envoyés. Motif par ligne ci-dessus.")
    if differes:
        _recap_differes(differes)
    return sent, opened, sold


def _recap_differes(differes: list) -> None:
    """Le report n'est pas une erreur — mais il ne doit pas être SUBI.

    L'ancien message disait « ils partiront à la prochaine séance ». C'est faux dès
    que le rebalancement est planifié hors séance : la prochaine exécution sera elle
    aussi hors séance, et les mêmes ordres seront reportés indéfiniment. Un ordre
    reporté ne part QUE si une exécution tombe DANS la séance — rien ne le met en
    file d'attente.
    """
    tot = f"{sum(abs(d['montant']) for d in differes):,.0f}".replace(",", " ")
    par_classe: dict[str, int] = {}
    for d in differes:
        cl = d.get("asset_class", "?")
        par_classe[cl] = par_classe.get(cl, 0) + 1
    detail = ", ".join(f"{n} {c}" for c, n in sorted(par_classe.items()))
    print(f"\n  ⏸  {len(differes)} ordre(s) REPORTÉ(S) hors séance ({detail}), "
          f"{tot}$ au total.")
    print("     Ils ne sont PAS mis en file d'attente : un ordre reporté ne part que")
    print("     si une exécution tombe DANS la séance NYSE"
          " (15:30-22:00, heure de Paris).")
    print("     Si ce report revient chaque jour, c'est le planning, pas le marché :")
    print("       • à la main, un soir avant 22h  →  make live-go")
    print("       • ou décaler le rebalancement   →  "
          "QUANT_LIVE_HOUR=21 make live-cron-install")
    print("     Le crypto n'est jamais concerné : il tourne 24/7.")


def _fills_achats(brokers: tuple, jour: str) -> dict:
    """Achats RÉELLEMENT exécutés `jour`, par (place, symbole canonique) :
    quantité + VWAP.

    C'est la VÉRITÉ TERRAIN de l'ouverture. La position du courtier ne l'est pas : elle
    porte la quantité TOTALE et le prix de revient MOYEN, et elle peut n'être pas encore
    rafraîchie à l'instant du run — l'achat devenait alors introuvable et n'était JAMAIS
    journalisé (mesuré le 03/09 : 30 symboles sur 87 couverts à moitié ou moins).

    Best-effort par courtier : un courtier muet n'empêche pas l'autre d'être lu."""
    from packages.execution.live_journal import agreger_achats
    out: dict = {}
    for bn, br in brokers:
        if br is None or not hasattr(br, "orders"):
            continue
        try:
            ordres = br.orders(limit=500)
        except Exception:  # noqa: BLE001
            continue                     # courtier muet : le repli position reste
        for sym, fill in agreger_achats(ordres, jour).items():
            out[(bn, sym)] = fill
    return out


def _positions_repli(brokers: tuple) -> dict:
    """Positions du courtier par (place, symbole canonique) — REPLI quand aucun
    fill n'est lisible.

    Approximation assumée (quantité totale, prix moyen) : mieux qu'une ouverture perdue,
    moins bon qu'un fill. Jamais prioritaire sur `_fills_achats`."""
    from packages.execution.live_journal import normaliser
    pos: dict = {}
    for bn, br in brokers:
        if br is None:
            continue
        try:
            detail = br.positions_detailed()
        except Exception:  # noqa: BLE001
            continue
        for p in detail:
            pos[(bn, normaliser(p["symbol"]))] = {"avg_price": p.get("avg_price"),
                                                  "qty": p.get("qty")}
    return pos


def _journal_opens(snap: dict, opened: list, alpaca, bitmart) -> None:
    """Journalise les ouvertures (`legacy=0`) : features de DÉCISION (snap) + faits de fill (broker).

    Ordre des sources de fill : fills d'achat du jour (vérité terrain), puis
    position (repli).

    Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not opened:
        return
    try:
        from packages.execution.live_journal import (
            feature_map,
            journal_opens,
            normaliser,
            regime_context,
        )
        from packages.storage import SqliteTradeJournal

        feats_by_sym = feature_map(snap)
        regime_lbl, regime_ctx = regime_context(snap)
        _series = (snap.get("dashboard") or {}).get("chart_series") or {}

        def _decision_px(sym):                        # dernier close CONNU à la décision
            bars = _series.get(sym) or []
            return float(bars[-1]["c"]) if bars else None
        brokers = (("Alpaca", alpaca), ("Bitmart", bitmart))
        jour = datetime.now(UTC).date().isoformat()
        fills = _fills_achats(brokers, jour)
        repli = _positions_repli(brokers)

        def _fill(op):          # le fill du jour d'abord, la position ensuite
            cle = (op["venue"], normaliser(op["broker_symbol"]))
            return fills.get(cle) or repli.get(cle)
        opens = [{
            "symbol": op["symbol"], "venue": op["venue"], "asset_class": op.get("asset_class"),
            "fill": _fill(op),
            "features": {**feats_by_sym.get(op["symbol"], {}), **regime_ctx,
                         "target_weight": op.get("weight_pct"),
                         # prix de DÉCISION (close du snapshot) → slippage réel
                         # mesurable
                         # au fill (exec_costs.py). None si série absente (jamais
                         # inventé).
                         **({"decision_price": _decision_px(op["symbol"])}
                            if _decision_px(op["symbol"]) else {})},
            "regime": regime_lbl,
        } for op in opened]
        n = journal_opens(SqliteTradeJournal(), opens)
        skipped = len(opened) - n
        print(f"Journal : {n} ouverture(s) enregistrée(s) (legacy=0, features de décision)"
              + (f" · {skipped} sans achat exécuté LISIBLE ce jour"
                 " (ni fill, ni position — rien n'est inventé)." if skipped else "."))
    except Exception as e:  # noqa: BLE001
        print(f"Journal : journalisation ignorée ({str(e)[:60]}).")


def _exit_price(br, bsym: str) -> float:
    """Prix de sortie FACTUEL, par ordre de fiabilité : fill VENTE du jour (`orders`),
    sinon ticker broker (`last_price`), sinon prix courant de la position. 0.0 = inconnu
    (le lot restera OUVERT — on n'invente jamais un prix)."""
    if br is None:
        return 0.0
    try:
        today = datetime.now(UTC).date().isoformat()
        for o in (br.orders(limit=50) if hasattr(br, "orders") else []):
            if (o.get("symbol") == bsym and o.get("side") == "sell"
                    and float(o.get("price") or 0) > 0 and (o.get("date") or "")[:10] == today):
                return float(o["price"])
        if hasattr(br, "last_price"):
            px = float(br.last_price(bsym) or 0.0)
            if px > 0:
                return px
        for p in br.positions_detailed():
            if p.get("symbol") == bsym and float(p.get("price") or 0) > 0:
                return float(p["price"])
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _journal_sells(snap: dict, sold: list, alpaca, bitmart) -> None:
    """Round-trip (P0-4 Phase 2) : ferme les lots du journal touchés par les VENTES envoyées.

    Prix de sortie = FAIT broker (cf. `_exit_price`) ; introuvable → lot laissé OUVERT.
    Best-effort strict : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not sold:
        return
    try:
        from packages.execution.live_roundtrip import close_sells
        from packages.storage import SqliteTradeJournal
        brokers = {"Alpaca": alpaca, "Bitmart": bitmart}
        for s in sold:
            s["exit_price"] = _exit_price(brokers.get(s["venue"]), s["broker_symbol"])
        series = (snap.get("dashboard") or {}).get("chart_series") or {}
        n = close_sells(SqliteTradeJournal(), sold, series)
        skipped = sum(1 for s in sold if not s.get("exit_price"))
        print(f"Journal : {n} lot(s) fermé(s) (round-trip, PnL/MFE/MAE)"
              + (f" · {skipped} vente(s) sans prix broker (lots laissés ouverts)." if skipped else "."))
    except Exception as e:  # noqa: BLE001
        print(f"Journal : round-trip ignoré ({str(e)[:60]}).")


def _sync_obsidian() -> None:
    """Synchronise le coffre Obsidian (journal + attribution + post-mortems). Best-effort strict."""
    try:
        from packages.reporting.obsidian import sync_obsidian_vault
        r = sync_obsidian_vault()
        print(f"Coffre Obsidian : {len(r.get('written', []))} note(s) · {r.get('incidents', 0)} incident(s).")
    except Exception:  # noqa: BLE001
        pass


def _decision_snapshot() -> dict:
    """Snapshot de DÉCISION en mode LÉGER : la réconciliation n'a besoin que des poids
    cibles + régime + prix. On coupe les sections réseau lentes (fondamentaux, news, ML…)
    → le build passe de plusieurs minutes (souvent interrompu) à quelques secondes.
    Forçable en complet avec QUANT_LIVE_LITE=0 (ex. debug)."""
    import os
    os.environ.setdefault("QUANT_LIVE_LITE", "1")
    if os.environ["QUANT_LIVE_LITE"] == "1":
        print("Snapshot : mode léger (sections réseau non essentielles coupées pour l'exécution).")
    from apps.api.snapshot import build_snapshot
    return build_snapshot()                                # DÉCISION unique (features figées ici)


def _diag_preset(snap: dict, targets: list) -> None:
    """Dit POURQUOI le satellite actions est vide, au lieu de le laisser deviner.

    Le 26/08, un compte paper sans AUCUNE action a résisté à trois hypothèses
    successives (plancher, horaires de marché, mode léger) simplement parce que
    rien ne disait où la chaîne s'arrêtait. Affiché seulement en cas de problème."""
    # CHEMIN EXACT. `preset_diagnostic` est publié sous `dashboard`, pas à la racine :
    # le lire à la racine renvoyait toujours {} et affichait « aucun diagnostic publié »
    # alors qu'il existait. Repli sur la racine au cas où le schéma évoluerait.
    d = ((snap.get("dashboard") or {}).get("preset_diagnostic")
         or snap.get("preset_diagnostic") or {})
    # NE PAS compter les cibles par classe d'actifs : le CŒUR indiciel (QQQ) est
    # une action, donc un satellite vide passait pour rempli et le diagnostic se
    # taisait — le défaut qu'il devait justement révéler. Le signal direct est
    # l'étage « poids retenus », inscrit seulement si au moins une ligne sort.
    _ = targets          # conservé pour la signature ; le signal vient du diagnostic
    a_des_poids = any(e.get("etape") == "poids retenus"
                      for e in (d.get("etapes") or []))
    if a_des_poids and not d.get("bloque"):
        return
    print("\n  DIAGNOSTIC DU SATELLITE ACTIONS")
    for e in d.get("etapes") or []:
        print(f"    {e.get('etape', ''):<22} {e.get('detail', '')}")
    portes = d.get("portes") or {}
    if portes:
        tot = 1.0
        for v in portes.values():
            tot *= v
        detail = " × ".join(f"{k} {v:.3f}" for k, v in portes.items())
        print(f"    {'exposition brute':<22} {detail}  =  {tot:.4f}")
    if d.get("arret"):
        print(f"    ⛔ ARRÊT : {d['arret']}")
    elif not d.get("etapes"):
        print("    (aucun diagnostic publié — snapshot antérieur à l'ADR-0044 ?)")
    elif not a_des_poids:
        print("    (aucun poids produit, sans étage bloquant signalé — anomalie)")


def _prepare_brokers(dry: bool, cli_equity: float | None, alert_engine):
    """Brokers vétés + positions lues (inconnu ⇒ broker écarté). Cf. live_guards."""
    from packages.execution.live_guards import (
        current_values, fail_loud, simule, vet_brokers,
    )
    # SIMULATION (`--equity`) vs APERÇU : seule la simulation ignore le détenu. Un aperçu
    # sur détenu vide affiche des achats que le run réel ne fera pas — il annonce un
    # portefeuille à construire là où le compte est déjà plein.
    simulation = simule(dry, cli_equity)
    alpaca, bitmart = _make_brokers(dry, apercu=dry and not simulation)
    alpaca, bitmart, alp_cap, bit_cap, fatal = vet_brokers(alpaca, bitmart, dry, cli_equity)
    mode = ("SIMULATION (capital imposé, détenu ignoré)" if simulation else
            "DRY-RUN sur le compte RÉEL (aucun ordre)" if dry else "LIVE (paper)")
    print(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {mode}")
    print(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")
    cur_alp, cur_bit = ({}, {}) if simulation else current_values(alpaca, bitmart)
    if cur_alp is None:                                        # inconnu ≠ zéro : broker écarté
        fatal.append("lecture positions Alpaca échouée → broker écarté (0 ordre)")
        alpaca, cur_alp = None, {}
    if cur_bit is None:
        fatal.append("lecture positions Bitmart échouée → broker écarté (0 ordre)")
        bitmart, cur_bit = None, {}
    if not dry and alpaca is None and bitmart is None:
        fail_loud(fatal or ["aucun broker actif en mode LIVE"], alert_engine, code=3)
    return alpaca, bitmart, alp_cap, bit_cap, cur_alp, cur_bit, fatal


def main() -> None:
    a = _parse_args()
    if a.live and not a.yes:
        print("⚠️  --live exige --yes (confirmation explicite). Abandon."); return
    dry = not (a.live and a.yes)
    snap = _decision_snapshot()
    targets = snap["live"]["target_orders"]                # poids cibles (% du portefeuille)
    _diag_preset(snap, targets)

    from packages.execution.live_guards import dd_kill_switch, fail_loud
    bus, alert_engine = _setup_alerts(dry)
    reduce = _kill_switch(bus)
    alpaca, bitmart, alp_cap, bit_cap, cur_alp, cur_bit, fatal = \
        _prepare_brokers(dry, a.equity, alert_engine)
    if not dry:                                                # kill-switch DRAWDOWN RÉEL (pas que TV)
        reduce = min(reduce, dd_kill_switch(alp_cap + bit_cap, bus, alert_engine))
    if reduce <= 0.0:                                          # kill-switch total : on n'envoie rien
        for o in targets:
            print(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
                  f"{o['broker']:8s} {o['weight_pct']*100:6.1f}%  bloqué (kill-switch)")
        print("\n⛔ Kill-switch : aucun ordre (exposition gelée).")
        return

    brokers = (("Alpaca", alpaca, alp_cap, cur_alp), ("Bitmart", bitmart, bit_cap, cur_bit))
    sent, opened, sold = _reconcile(targets, brokers, reduce, alert_engine, dry)
    print(f"\nTerminé : {sent} ordre(s) de réconciliation envoyé(s) (paper, sans levier)." if not dry else
          "\nAperçu (dry-run). Réconciliation réelle : python3 scripts/run_live.py --live --yes")

    if not dry:
        _journal_opens(snap, opened, alpaca, bitmart)
        _journal_sells(snap, sold, alpaca, bitmart)
        _record_equity(alp_cap, bit_cap)
    _sync_obsidian()
    if fatal:                                        # après journal/equity : rien n'est perdu, mais le run est ROUGE
        fail_loud(fatal, alert_engine, code=4)


def _record_equity(alp_cap: float, bit_cap: float) -> None:
    """Enregistre l'equity RÉELLE du jour → alimente la courbe paper de `make rdv-paper`.

    Corrige un trou (06/07) : l'equity_history n'était écrite que par `build_snapshot()`
    (donc seulement à un `make start`). Le chemin de PROD (cron Mac + runner cloud) ne
    l'alimentait pas → la courbe paper du RDV 2026-08-06 ne se serait jamais accumulée
    si le Mac restait éteint. Best-effort strict."""
    try:
        from packages.execution.equity_history import record
        record({"alpaca": alp_cap, "bitmart": bit_cap})
        print(f"Equity : point du jour enregistré (Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $).")
    except Exception as e:  # noqa: BLE001
        print(f"Equity : enregistrement ignoré ({str(e)[:50]}).")


if __name__ == "__main__":
    main()
