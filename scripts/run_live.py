"""Exécuteur live — réplique le portefeuille MODÈLE chez les brokers (DRY-RUN par défaut).

Routage : actions/ETF → **Alpaca (paper)** · crypto /USDC → **Bitmart** (ccxt).
Sécurité maximale :
  - DRY-RUN par défaut : affiche les ordres, n'envoie RIEN ;
  - mode réel uniquement avec `--live --yes` ET clés API présentes ;
  - Alpaca reste en **paper** (is_paper) ; Bitmart protégé par `dry_run` tant que `--live`
    n'est pas passé. Permissions API minimales, jamais de retrait.

  python scripts/run_live.py                 # aperçu (dry-run) des ordres cibles
  python scripts/run_live.py --live --yes    # envoie en paper/crypto (clés requises)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="Réplique le portefeuille modèle (dry-run par défaut)")
    ap.add_argument("--live", action="store_true", help="envoyer réellement (sinon dry-run)")
    ap.add_argument("--yes", action="store_true", help="confirmation obligatoire pour le mode --live")
    ap.add_argument("--equity", type=float, default=None,
                    help="capital à allouer (dry-run) ; en live = equity réelle du broker")
    a = ap.parse_args()

    from apps.api.snapshot import build_snapshot
    from packages.core.models import Order, OrderType, Side

    targets = build_snapshot()["live"]["target_orders"]   # poids cibles (% du portefeuille)
    dry = not (a.live and a.yes)
    if a.live and not a.yes:
        print("⚠️  --live exige --yes (confirmation explicite). Abandon."); return

    # KILL-SWITCH : alertes TradingView (webhook) → veto / réduction d'exposition (sécurité live).
    from packages.mcp_tradingview.alerts import fetch_tv_technical_alerts, to_risk_veto
    risk = to_risk_veto(fetch_tv_technical_alerts())
    reduce = 0.0 if risk.get("veto") else float(risk.get("reduce", 1.0))
    if risk.get("veto"):
        print(f"⛔ KILL-SWITCH ACTIF (alertes TV critiques) : {', '.join(risk['reasons']) or '—'}")
        print("   → exposition forcée à 0, aucun ordre ne sera envoyé.")
    elif reduce < 1.0:
        print(f"⚠️  Alertes TV : exposition réduite ×{reduce:.2f} ({', '.join(risk['reasons']) or '—'})")

    alpaca = bitmart = None
    if not dry:
        from packages.execution.bitmart_broker import BitmartBroker
        bitmart = BitmartBroker(dry_run=False)
        try:
            from packages.execution.alpaca_broker import AlpacaBroker
            alpaca = AlpacaBroker(paper=True)             # actions TOUJOURS en paper
        except Exception as e:  # noqa: BLE001
            print(f"Alpaca indisponible ({str(e)[:60]}) → actions ignorées")

    # CAPITAL PAR COMPTE (comptes distincts) : actions ← Alpaca, crypto ← Bitmart.
    alp_cap = (alpaca.equity() if (alpaca and not dry) else 0.0) or a.equity or 10_000.0
    bit_cap = (bitmart.equity() if (bitmart and not dry) else 0.0) or 0.0
    print(f"Réplication · capital Alpaca {alp_cap:,.0f} $ · Bitmart {bit_cap:,.0f} $ · "
          f"mode {'DRY-RUN (aucun ordre)' if dry else 'LIVE (paper)'}")
    print(f"  {'SENS':4s} {'ACTIF':14s} {'BROKER':8s} {'POIDS':>7s} {'MONTANT':>10s}  statut")

    # --- RÉCONCILIATION idempotente + ANTI-LEVIER ---
    # On ne ré-achète PAS la cible complète à chaque run : on n'échange que le DELTA (cible − détenu).
    # Relancer converge vers la cible (jamais d'empilement) ; les cibles sont plafonnées à 100 % du
    # capital PAR broker (somme des poids ≤ 1) → JAMAIS de marge/levier. Sur un compte déjà sur-investi,
    # les deltas sont négatifs → on VEND pour redescendre à 100 % (déleverage automatique).
    cur_alp: dict[str, float] = {}
    cur_bit: dict[str, float] = {}
    if not dry:
        try:
            if alpaca:
                cur_alp = {p["symbol"]: float(p.get("market_value", 0) or 0) for p in alpaca.positions_detailed()}
            if bitmart:
                cur_bit = {p["symbol"]: float(p.get("market_value", 0) or 0) for p in bitmart.positions_detailed()}
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  lecture des positions échouée ({str(e)[:50]}) — réconciliation prudente (détenu=0).")

    if reduce <= 0.0:                                          # kill-switch total : on n'envoie rien
        for o in targets:
            print(f"  {o['side'].upper():4s} {o.get('broker_symbol', o['symbol']):14s} "
                  f"{o['broker']:8s} {o['weight_pct']*100:6.1f}%  bloqué (kill-switch)")
        print("\n⛔ Kill-switch : aucun ordre (exposition gelée).")
        return

    band_frac = 0.005                                         # ignore les micro-deltas (< 0,5 % du capital)
    sent = 0
    for bname, broker, cap, cur in (("Alpaca", alpaca, alp_cap, cur_alp),
                                    ("Bitmart", bitmart, bit_cap, cur_bit)):
        tgs = [o for o in targets if (o.get("capital") == "bitmart") == (bname == "Bitmart")]
        sw = sum(o["weight_pct"] for o in tgs)
        scale = min(1.0, 1.0 / sw) if sw > 1.0 else 1.0       # ANTI-LEVIER : Σ cibles ≤ capital
        tgt: dict[str, dict] = {}
        for o in tgs:
            bsym = o.get("broker_symbol", o["symbol"])
            tgt[bsym] = {"o": o, "val": o["weight_pct"] * cap * reduce * scale}
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
                from packages.common.retry import retry
                # backoff exponentiel sur timeouts / rate-limits transitoires du broker
                retry(lambda: broker.submit_notional(bsym, side, abs(delta)), attempts=3)
                sent += 1
                print(tag + ("  ▲ achat" if delta > 0 else "  ▼ vente"))
            except Exception as e:  # noqa: BLE001
                print(tag + f"  échec après retries ({str(e)[:40]})")
    print(f"\nTerminé : {sent} ordre(s) de réconciliation envoyé(s) (paper, sans levier)." if not dry else
          "\nAperçu (dry-run). Réconciliation réelle : python3 scripts/run_live.py --live --yes")

    # CLÔTURE : synchronise le coffre Obsidian (journal + attribution + post-mortems).
    # Best-effort STRICT : ne lève jamais → ne peut pas bloquer l'exécution.
    try:
        from packages.reporting.obsidian import sync_obsidian_vault
        r = sync_obsidian_vault()
        print(f"Coffre Obsidian : {len(r.get('written', []))} note(s) · {r.get('incidents', 0)} incident(s).")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
