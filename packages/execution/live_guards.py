"""Garde-fous du run d'exécution (audit 07/15) — fail-loud, brokers vétés, kill-switch DD réel.

Trois principes, chacun né d'un finding CRITIQUE du comité :
  1. **Inconnu ≠ zéro** : positions/equity illisibles ⇒ le broker est ÉCARTÉ du run
     (l'ancien « détenu=0 prudent » faisait RACHETER tout le portefeuille par-dessus
     l'existant quand l'API positions toussait).
  2. **Fail-loud** : plus jamais de run vert-fantôme — broker mort, clé invalide ou
     lecture KO ⇒ alerte CRITICAL + exit ≠ 0 (le job Actions/launchd devient ROUGE).
  3. **Kill-switch sur l'équité RÉELLE** : le drawdown du compte coupe l'exposition,
     pas seulement les alertes TradingView.
"""

from __future__ import annotations

import os


def current_values(alpaca, bitmart) -> tuple[dict | None, dict | None]:
    """Valeurs de marché détenues PAR broker. Lecture en échec → **None** (inconnu),
    JAMAIS {} (zéro détenu) — cf. principe 1."""
    def _read(br):
        if not br:
            return {}
        try:
            return {p["symbol"]: float(p.get("market_value", 0) or 0)
                    for p in br.positions_detailed()}
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  lecture des positions {getattr(br, 'name', '?')} échouée "
                  f"({str(e)[:50]}) → broker ÉCARTÉ de ce run (aucun ordre).")
            return None
    return _read(alpaca), _read(bitmart)


def vet_brokers(alpaca, bitmart, dry: bool, cli_equity: float | None):
    """(alpaca, bitmart, alp_cap, bit_cap, fatal) — équity par compte, brokers morts écartés.

    En LIVE : equity nulle/illisible = broker MORT → écarté + motif `fatal` (l'ancien
    repli 10 000 $ faisait « trader » un broker à clé invalide, run vert à jamais).
    Bitmart sans clés = simple inactivité (normal en cloud), pas une erreur."""
    fatal: list[str] = []
    if dry:
        return alpaca, bitmart, (cli_equity or 10_000.0), 0.0, fatal
    alp_cap = alpaca.equity() if alpaca else 0.0
    if alpaca and alp_cap <= 0:
        fatal.append("equity Alpaca nulle/illisible (clé invalide ?) → broker écarté")
        alpaca, alp_cap = None, 0.0
    bit_cap = bitmart.equity() if bitmart else 0.0
    if bitmart and bit_cap <= 0:
        if getattr(bitmart, "_live", lambda: False)():         # clés présentes, equity inconnue
            fatal.append("equity Bitmart nulle/illisible → broker écarté (aucune vente)")
        bitmart, bit_cap = None, 0.0
    return alpaca, bitmart, alp_cap, bit_cap, fatal


def dd_kill_switch(total_equity: float, bus, alert_engine) -> float:
    """Kill-switch sur le DRAWDOWN RÉEL du compte (principe 3). Lit l'historique
    d'equity persisté + le point du jour ; DD depuis le pic ≤ `QUANT_INTRADAY_DD`
    (défaut −15 %) → 0.0 (exposition coupée). Historique court/indispo → 1.0."""
    limit = float(os.environ.get("QUANT_INTRADAY_DD", "-0.15"))
    try:
        from packages.execution.equity_history import _load
        from packages.portfolio.stress import drawdown_breach
        curve = [sum(v for k, v in h.items() if k != "date" and isinstance(v, (int, float)))
                 for h in _load()]
        curve = [x for x in curve if x > 0]
        if total_equity > 0:
            curve.append(total_equity)
        out = drawdown_breach(curve, dd_limit=limit)
        if not out.get("available") or not out.get("breach"):
            return 1.0
        msg = (f"drawdown réel {out['drawdown']*100:.1f}% ≤ seuil {limit*100:.0f}% "
               f"(pic {out['peak']}, dernier {out['last']})")
        print(f"⛔ KILL-SWITCH DRAWDOWN RÉEL : {msg} → exposition forcée à 0.")
        if bus:
            from packages.common.event_bus import Topic
            bus.publish(Topic.KILL_SWITCH, {"drawdown": out["drawdown"]})
        if alert_engine:
            from packages.alerts import Alert, Severity
            alert_engine.emit(Alert("risk", Severity.CRITICAL,
                                    f"Kill-switch drawdown réel déclenché : {msg}",
                                    dedup_key="risk:dd_kill_switch"))
        return 0.0
    except Exception as e:  # noqa: BLE001 — le check ne doit jamais BLOQUER un run sain
        print(f"· kill-switch DD réel : check indisponible ({str(e)[:50]}) — non appliqué.")
        return 1.0


def fail_loud(reasons: list[str], alert_engine, code: int) -> None:
    """Échec BRUYANT (principe 2) : alerte CRITICAL + exit ≠ 0."""
    for m in reasons:
        print(f"⛔ {m}")
    if alert_engine:
        try:
            from packages.alerts import Alert, Severity
            alert_engine.emit(Alert("execution", Severity.CRITICAL,
                                    "run_live en échec : " + " · ".join(reasons)[:180],
                                    dedup_key="execution:fail_loud"))
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(code)
