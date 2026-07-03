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


def _current_values(alpaca, bitmart) -> tuple[dict, dict]:
    """Valeurs de marché détenues par broker (pour le calcul des deltas de réconciliation)."""
    cur_alp: dict[str, float] = {}
    cur_bit: dict[str, float] = {}
    try:
        if alpaca:
            cur_alp = {p["symbol"]: float(p.get("market_value", 0) or 0) for p in alpaca.positions_detailed()}
        if bitmart:
            cur_bit = {p["symbol"]: float(p.get("market_value", 0) or 0) for p in bitmart.positions_detailed()}
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  lecture des positions échouée ({str(e)[:50]}) — réconciliation prudente (détenu=0).")
    return cur_alp, cur_bit


def _reconcile(targets, brokers, reduce, alert_engine, dry) -> tuple[int, list]:
    """Réconciliation idempotente + ANTI-LEVIER. Retourne (nb ordres envoyés, ouvertures à journaliser).

    On n'échange que le DELTA (cible − détenu) ; cibles plafonnées à 100 % du capital PAR broker
    (Σ poids ≤ 1) → jamais de levier. `opened` = achats RÉELLEMENT envoyés (à journaliser, `legacy=0`)."""
    from packages.common.retry import retry
    from packages.core.models import Side
    sent, opened = 0, []
    band_frac = 0.005                                         # ignore les micro-deltas (< 0,5 % du capital)
    for bname, broker, cap, cur in brokers:
        tgs = [o for o in targets if (o.get("capital") == "bitmart") == (bname == "Bitmart")]
        sw = sum(o["weight_pct"] for o in tgs)
        scale = min(1.0, 1.0 / sw) if sw > 1.0 else 1.0       # ANTI-LEVIER : Σ cibles ≤ capital
        tgt: dict[str, dict] = {}
        for o in tgs:
            tgt[o.get("broker_symbol", o["symbol"])] = {"o": o, "val": o["weight_pct"] * cap * reduce * scale}
        for bsym in cur:                                      # détenu hors-cible → liquidation (cible 0)
            tgt.setdefault(bsym, {"o": None, "val": 0.0})
        band = max(band_frac * cap, 5.0)
        for bsym, info in sorted(tgt.items(), key=lambda kv: -kv[1]["val"]):
            o = info["o"]
            delta = info["val"] - cur.get(bsym, 0.0)          # >0 acheter · <0 vendre
            tag = f"  {bsym:14s} {bname:8s} cible {info['val']:8.0f}$ détenu {cur.get(bsym,0.0):8.0f}$ Δ {delta:+8.0f}$"
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
            except Exception as e:  # noqa: BLE001
                print(tag + f"  échec après retries ({str(e)[:40]})")
                if alert_engine:
                    from packages.alerts import Alert, Severity
                    alert_engine.emit(Alert("execution", Severity.CRITICAL,
                        f"Ordre {'achat' if delta > 0 else 'vente'} {bsym} ({bname}) échoué "
                        f"après retries : {str(e)[:80]}",
                        dedup_key=f"execution:submit_fail:{bsym}"))
    return sent, opened


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
                         "target_weight": op.get("weight_pct")},
            "regime": regime_lbl,
        } for op in opened]
        n = journal_opens(SqliteTradeJournal(), opens)
        skipped = len(opened) - n
        print(f"Journal : {n} ouverture(s) enregistrée(s) (legacy=0, features de décision)"
              + (f" · {skipped} sans fill exploitable (capturé au prochain run)." if skipped else "."))
    except Exception as e:  # noqa: BLE001
        print(f"Journal : journalisation ignorée ({str(e)[:60]}).")


def _sync_obsidian() -> None:
    """Synchronise le coffre Obsidian (journal + attribution + post-mortems). Best-effort strict."""
    try:
        from packages.reporting.obsidian import sync_obsidian_vault
        r = sync_obsidian_vault()
        print(f"Coffre Obsidian : {len(r.get('written', []))} note(s) · {r.get('incidents', 0)} incident(s).")
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    a = _parse_args()
    if a.live and not a.yes:
        print("⚠️  --live exige --yes (confirmation explicite). Abandon."); return
    dry = not (a.live and a.yes)

    from apps.api.snapshot import build_snapshot
    snap = build_snapshot()                                # DÉCISION unique (features figées ici)
    targets = snap["live"]["target_orders"]                # poids cibles (% du portefeuille)

    bus, alert_engine = _setup_alerts(dry)
    reduce = _kill_switch(bus)
    alpaca, bitmart = _make_brokers(dry)

    # CAPITAL PAR COMPTE (comptes distincts) : actions ← Alpaca, crypto ← Bitmart.
    alp_cap = (alpaca.equity() if (alpaca and not dry) else 0.0) or a.equity or 10_000.0
    bit_cap = (bitmart.equity() if (bitmart and not dry) else 0.0) or 0.0
    print(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {'DRY-RUN (aucun ordre)' if dry else 'LIVE (paper)'}")
    print(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")

    cur_alp, cur_bit = _current_values(alpaca, bitmart) if not dry else ({}, {})
    if reduce <= 0.0:                                          # kill-switch total : on n'envoie rien
        for o in targets:
            print(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
                  f"{o['broker']:8s} {o['weight_pct']*100:6.1f}%  bloqué (kill-switch)")
        print("\n⛔ Kill-switch : aucun ordre (exposition gelée).")
        return

    brokers = (("Alpaca", alpaca, alp_cap, cur_alp), ("Bitmart", bitmart, bit_cap, cur_bit))
    sent, opened = _reconcile(targets, brokers, reduce, alert_engine, dry)
    print(f"\nTerminé : {sent} ordre(s) de réconciliation envoyé(s) (paper, sans levier)." if not dry else
          "\nAperçu (dry-run). Réconciliation réelle : python3 scripts/run_live.py --live --yes")

    if not dry:
        _journal_opens(snap, opened, alpaca, bitmart)
    _sync_obsidian()


if __name__ == "__main__":
    main()
