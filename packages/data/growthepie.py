"""Growthepie — TPS & frais de l'écosystème Ethereum + L2 (gratuit, sans clé).

NB honnête : Growthepie ne couvre QU'Ethereum/L2 (pas SOL/NEAR/HYPE…). Sert de CONTEXTE
réseau Ethereum pour enrichir le rapport. Best-effort : parser défensif (l'API peut
évoluer) → {} si la forme ne matche pas, jamais bloquant. Parser séparé (testable).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

_URL = "https://api.growthepie.xyz/v1/fundamentals_full.json"


def _get_json(url: str, timeout: float = 10.0) -> Any:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def parse_fundamentals(data: Any, origin: str = "ethereum") -> dict:
    """Records [{metric_key, origin_key, date, value}] → dernières valeurs (`origin`).

    Renvoie {txcount, txcosts_median_usd} (les clés trouvées). Défensif : ignore tout ce
    qui ne matche pas. Garde la valeur à la date la plus récente par métrique.
    """
    latest: dict[str, tuple[str, float]] = {}     # metric -> (date, value)
    for r in data or []:
        if not isinstance(r, dict):
            continue
        if str(r.get("origin_key") or r.get("origin") or "").lower() != origin:
            continue
        metric = str(r.get("metric_key") or r.get("metric") or "")
        date = str(r.get("date") or "")
        val = r.get("value")
        if not metric or val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if metric not in latest or date > latest[metric][0]:
            latest[metric] = (date, v)
    out: dict[str, float] = {}
    if "txcount" in latest:
        out["txcount"] = latest["txcount"][1]
    for k in ("txcosts_median_usd", "txcosts_median", "fees_paid_usd"):
        if k in latest:
            out["txcosts_median_usd"] = latest[k][1]
            break
    return out


def eth_context() -> dict:
    """Contexte réseau Ethereum (TPS estimé + frais médian). available=False sinon."""
    f = parse_fundamentals(_get_json(_URL))
    if not f:
        return {"available": False}
    out: dict = {"available": True}
    if "txcount" in f:
        out["tps"] = round(f["txcount"] / 86400.0, 2)         # TPS ≈ tx/jour / 86400
    if "txcosts_median_usd" in f:
        out["median_fee_usd"] = round(f["txcosts_median_usd"], 4)
    return out if len(out) > 1 else {"available": False}
