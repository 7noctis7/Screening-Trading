"""Démo alertes multi-canal (offline) — event bus → moteur → canaux, avec anti-spam.

  python scripts/demo_alerts.py

Simule régime/risque/données/exécution. Console = INFO+ ; en prod Telegram (WARNING+)
et Discord (CRITICAL) via .env. Le doublon de kill-switch est throttlé.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.alerts import AlertEngine, ConsoleSink, InMemorySink, Severity, register_on_bus  # noqa: E402
from packages.common.event_bus import EventBus, Topic  # noqa: E402


def main() -> int:
    bus = EventBus()
    mem = InMemorySink(Severity.INFO)
    eng = AlertEngine([ConsoleSink(Severity.INFO), mem])
    register_on_bus(eng, bus)

    print("\n=== Flux d'alertes (console) ===")
    bus.publish(Topic.REGIME_CHANGED, {"from": "expansion", "to": "risk_off"})
    bus.publish(Topic.DATA_QUALITY_FAILED, {"symbol": "BTCUSDT", "detail": "données périmées"})
    bus.publish(Topic.ORDER_FILLED, {"side": "long", "symbol": "AAPL", "qty": 12})
    bus.publish(Topic.KILL_SWITCH, {"drawdown": "-5.4%"})
    bus.publish("execution.reconcile_divergence", {"divergences": [("MSFT", 1.0)]})
    bus.publish(Topic.KILL_SWITCH, {"drawdown": "-5.6%"})   # throttlé

    crit = sum(1 for a in mem.received if a.severity is Severity.CRITICAL)
    print(f"\n {len(mem.received)} alertes tracées (1 doublon throttlé) · {crit} critiques\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
