"""Démo excellence opérationnelle (offline) — drift, audit, télémétrie, tear sheet PDF."""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from packages.alerts import AlertEngine, ConsoleSink, Severity, Alert  # noqa: E402
from packages.common.audit import AuditTrail  # noqa: E402
from packages.common.telemetry import Metrics  # noqa: E402
from packages.ml import feature_drift  # noqa: E402
from packages.reporting import to_pdf  # noqa: E402


def main() -> int:
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, (500, 2))
    cur = np.column_stack([rng.normal(0, 1, 500), rng.normal(3, 1, 500)])
    drift = feature_drift(ref, cur, ["rsi", "macro_vix"])
    eng = AlertEngine([ConsoleSink(Severity.INFO)])
    if drift["drift_detected"]:
        eng.emit(Alert("data", Severity.WARNING,
                       f"Drift détecté: {drift['flagged']} → réentraînement recommandé",
                       dedup_key="drift"))
    au = AuditTrail(":memory:")
    au.record("order", {"sym": "AAPL", "regime": "risk_off", "model": "logit_v3"})
    m = Metrics(); m.incr("orders"); m.gauge("equity", 98857)
    with m.timer("pipeline_step"):
        time.sleep(0.002)
    pdf = to_pdf("Tear Sheet — Démo", {"Sharpe": "0.46", "Max DD": "-3.9%",
                 "VaR 95%": "1.4%"}, [100, 102, 101, 104, 108, 106, 110],
                 ROOT / "out" / "tearsheet.pdf")
    print(f"\n audit: {au.count()} entrée(s) rejouable(s) · télémétrie: {m.snapshot()}")
    print(f" tear sheet PDF: {pdf}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
