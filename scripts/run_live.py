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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _parse_args():
    ap = argparse.ArgumentParser(description="Réplique le portefeuille modèle (dry-run par défaut)")
    ap.add_argument("--live", action="store_true", help="envoyer réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true", help="confirmation obligatoire pour le mode --live")
    ap.add_argument("--equity", type=float, default=None,
                    help="capital à allouer (dry-run) ; en live = equity réelle du broker")
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
    from packages.mcp_tradingview.alerts import fetch_tv_technical_alerts, to_risk_veto
    risk = to_risk_veto(fetch_tv_technical_alerts())
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


def _make_brokers(dry: bool):
    """(alpaca paper, bitmart) en mode réel ; (None, None) en dry-run. Alpaca best-effort."""
    if dry:
        return None, None
    from packages.execution.bitmart_broker import BitmartBroker
    bitmart = BitmartBroker(dry_run=False)
    alpaca = None
    try:
        from packages.execution.alpaca_broker import AlpacaBroker
        alpaca = AlpacaBroker(paper=True)                 # actions TOUJOURS en paper
    except Exception as e:  # noqa: BLE001
        print(f"Alpaca indisponible ({str(e)[:60]}) → actions ignorées")
    return alpaca, bitmart


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


def _reconcile(targets, brokers, reduce, alert_engine, dry) -> tuple[int, list, list]:
    """Réconciliation idempotente + ANTI-LEVIER. Retourne (nb ordres, ouvertures, ventes).

    On n'échange que le DELTA (cible − détenu). `opened` = achats RÉELLEMENT envoyés (à
    journaliser, `legacy=0`) ; `sold` = ventes RÉELLEMENT envoyées (round-trip Phase 2)."""
    from packages.common.retry import retry
    from packages.core.models import Side
    sent, opened, sold = 0, [], []
    for bname, broker, cap, cur in brokers:
        tgt, band = _broker_targets(targets, bname, cap, reduce, cur)
        curn = {}                                             # détenu par clé NORMALISÉE (cumul)
        for k, v in cur.items():
            curn[_nsym(k)] = curn.get(_nsym(k), 0.0) + v
        for nkey, info in sorted(tgt.items(), key=lambda kv: -kv[1]["val"]):
            o, bsym = info["o"], info["sym"]
            delta = info["val"] - curn.get(nkey, 0.0)         # >0 acheter · <0 vendre
            tag = f"  {bsym:14s} {bname:8s} cible {info['val']:8.0f}$ détenu {curn.get(nkey,0.0):8.0f}$ Δ {delta:+8.0f}$"
            if o is not None and o.get("tradeable") is False:
                print(tag + "  non négociable"); continue
            if abs(delta) < band:
                print(tag + "  ✓ déjà aligné"); continue
            side = Side.LONG if delta > 0 else Side.SHORT     # SHORT = vendre le surplus (spot/long-only)
            if dry or broker is None:
                print(tag + "  " + ("aperçu" if dry else "broker absent")); continue
            try:
                retry(lambda: broker.submit_notional(bsym, side, abs(delta)), attempts=3)
                sent += 1
                print(tag + ("  ▲ achat" if delta > 0 else "  ▼ vente"))
                if delta > 0 and o is not None:               # ACHAT/ADD → ouverture à journaliser
                    opened.append({"symbol": o["symbol"], "venue": bname, "broker_symbol": bsym,
                                   "asset_class": o.get("asset_class"), "weight_pct": o.get("weight_pct")})
                elif delta < 0:                               # VENTE/REDUCE → round-trip à fermer
                    sold.append({"symbol": (o or {}).get("symbol", bsym), "venue": bname,
                                 "broker_symbol": bsym, "notional": abs(delta)})
            except Exception as e:  # noqa: BLE001
                print(tag + f"  échec après retries ({str(e)[:40]})")
                if alert_engine:
                    from packages.alerts import Alert, Severity
                    alert_engine.emit(Alert("execution", Severity.CRITICAL,
                        f"Ordre {'achat' if delta > 0 else 'vente'} {bsym} ({bname}) échoué "
                        f"après retries : {str(e)[:80]}",
                        dedup_key=f"execution:submit_fail:{bsym}"))
    return sent, opened, sold


def _journal_opens(snap: dict, opened: list, alpaca, bitmart) -> None:
    """Journalise les ouvertures (`legacy=0`) : features de DÉCISION (snap) + faits de fill (broker).

    Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution."""
    if not opened:
        return
    try:
        from packages.execution.live_journal import feature_map, journal_opens, regime_context
        from packages.storage import SqliteTradeJournal

        def _norm(s):                                        # BTC/USD ↔ BTCUSD (format broker vs routing)
            return (s or "").replace("/", "").replace("-", "").upper()
        feats_by_sym = feature_map(snap)
        regime_lbl, regime_ctx = regime_context(snap)
        _series = (snap.get("dashboard") or {}).get("chart_series") or {}

        def _decision_px(sym):                        # dernier close CONNU à la décision
            bars = _series.get(sym) or []
            return float(bars[-1]["c"]) if bars else None
        pos: dict = {}                                        # faits d'exécution : positions RÉELLES post-fill
        for bn, br in (("Alpaca", alpaca), ("Bitmart", bitmart)):
            if br is None:
                continue
            for p in br.positions_detailed():
                pos[(bn, _norm(p["symbol"]))] = {"avg_price": p.get("avg_price"), "qty": p.get("qty")}
        opens = [{
            "symbol": op["symbol"], "venue": op["venue"], "asset_class": op.get("asset_class"),
            "fill": pos.get((op["venue"], _norm(op["broker_symbol"]))),
            "features": {**feats_by_sym.get(op["symbol"], {}), **regime_ctx,
                         "target_weight": op.get("weight_pct"),
                         # prix de DÉCISION (close du snapshot) → slippage réel mesurable
                         # au fill (exec_costs.py). None si série absente (jamais inventé).
                         **({"decision_price": _decision_px(op["symbol"])}
                            if _decision_px(op["symbol"]) else {})},
            "regime": regime_lbl,
        } for op in opened]
        n = journal_opens(SqliteTradeJournal(), opens)
        skipped = len(opened) - n
        print(f"Journal : {n} ouverture(s) enregistrée(s) (legacy=0, features de décision)"
              + (f" · {skipped} sans fill exploitable (capturé au prochain run)." if skipped else "."))
    except Exception as e:  # noqa: BLE001
        print(f"Journal : journalisation ignorée ({str(e)[:60]}).")


def _exit_price(br, bsym: str) -> float:
    """Prix de sortie FACTUEL, par ordre de fiabilité : fill VENTE du jour (`orders`),
    sinon ticker broker (`last_price`), sinon prix courant de la position. 0.0 = inconnu
    (le lot restera OUVERT — on n'invente jamais un prix)."""
    from datetime import datetime, timezone
    if br is None:
        return 0.0
    try:
        today = datetime.now(timezone.utc).date().isoformat()
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


def _prepare_brokers(dry: bool, cli_equity: float | None, alert_engine):
    """Brokers vétés + positions lues (inconnu ⇒ broker écarté). Cf. live_guards."""
    from packages.execution.live_guards import current_values, fail_loud, vet_brokers
    alpaca, bitmart = _make_brokers(dry)
    alpaca, bitmart, alp_cap, bit_cap, fatal = vet_brokers(alpaca, bitmart, dry, cli_equity)
    print(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {'DRY-RUN (aucun ordre)' if dry else 'LIVE (paper)'}")
    print(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")
    cur_alp, cur_bit = current_values(alpaca, bitmart) if not dry else ({}, {})
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
