"""Alertes techniques TradingView → **veto / kill-switch** du Risk Engine.

Flux : TradingView (alerte Pine/indicateur) → webhook HTTP `POST /api/tv/webhook` → fichier
`.cache/tv_alerts.json` (drop). Ici on LIT ce drop (polling) et on le mappe en signal de veto.

⚠️ LIVE-ONLY : ces alertes n'alimentent QUE la décision en temps réel (réduire/bloquer l'expo).
Elles ne sont JAMAIS injectées dans le backtest ni l'entraînement ML (aucune fuite point-in-time).
Robuste : fichier absent/corrompu → liste vide (le risk-engine continue sans veto, jamais de crash).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / ".cache" / "tv_alerts.json"
_SEVERITIES = ("info", "warning", "critical")


@dataclass(frozen=True, slots=True)
class TVAlert:
    """Alerte normalisée venue de TradingView."""

    time: str
    ticker: str
    kind: str                       # ex. "vix_spike", "trend_break", "circuit_breaker"
    severity: str = "info"          # info | warning | critical
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_alert(raw: dict) -> TVAlert | None:
    """Normalise un payload webhook TradingView (souple) en TVAlert, ou None si inexploitable."""
    if not isinstance(raw, dict):
        return None
    ticker = str(raw.get("ticker") or raw.get("symbol") or "").strip().upper()
    kind = str(raw.get("kind") or raw.get("type") or raw.get("alert") or "alert").strip()
    sev = str(raw.get("severity") or raw.get("level") or "info").strip().lower()
    if sev not in _SEVERITIES:
        sev = "critical" if sev in ("crit", "high", "severe") else "warning" if sev in ("warn", "med") else "info"
    if not ticker and not raw.get("message"):
        return None
    return TVAlert(
        time=str(raw.get("time") or raw.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ticker=ticker or "*", kind=kind, severity=sev, message=str(raw.get("message") or "")[:300],
    )


def append_alert(raw: dict, path: str | Path | None = None, keep: int = 200) -> TVAlert | None:
    """Ajoute une alerte au drop (appelé par le webhook de l'API). Borne l'historique à `keep`."""
    alert = parse_alert(raw)
    if alert is None:
        return None
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        if not isinstance(cur, list):
            cur = []
    except (json.JSONDecodeError, OSError):
        cur = []
    cur.append(alert.to_dict())
    p.write_text(json.dumps(cur[-keep:], ensure_ascii=False), encoding="utf-8")
    return alert


def fetch_tv_technical_alerts(path: str | Path | None = None, max_age_s: float | None = None) -> list[TVAlert]:
    """Lit les alertes TV (polling du drop webhook). `max_age_s` filtre les trop vieilles (optionnel)."""
    p = Path(path) if path else _DEFAULT_PATH
    try:
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except (json.JSONDecodeError, OSError):
        return []
    out = [a for a in (parse_alert(r) for r in rows) if a is not None]
    return out


def to_risk_veto(alerts: list[TVAlert]) -> dict:
    """Mappe les alertes en décision risk-engine : veto si ≥1 alerte 'critical'.

    Returns: {"veto": bool, "reduce": float (0..1), "reasons": [...], "by_ticker": {...}}.
    'reduce' = facteur d'exposition conseillé (1=normal, 0.5 si warning, 0=veto total).
    """
    crit = [a for a in alerts if a.severity == "critical"]
    warn = [a for a in alerts if a.severity == "warning"]
    veto = len(crit) > 0
    reduce = 0.0 if veto else (0.5 if warn else 1.0)
    by_ticker: dict[str, str] = {}
    for a in alerts:
        if a.severity in ("critical", "warning"):
            by_ticker[a.ticker] = a.severity
    reasons = [f"{a.severity}:{a.kind} ({a.ticker})" for a in (crit + warn)][:10]
    return {"veto": veto, "reduce": reduce, "reasons": reasons, "by_ticker": by_ticker,
            "n_alerts": len(alerts)}
