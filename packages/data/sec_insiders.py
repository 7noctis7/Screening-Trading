"""Insiders SEC (Form 4) via EDGAR full-text search — lecture publique, sans clé, 0 €.

Thèse : une GRAPPE de transactions d'initiés signale une asymétrie d'info → dérive
positive 1-3 mois. Fetcher best-effort (offline-safe) + score de cluster = nb de dépôts
Form 4 récents pour un ticker.

Limite : la full-text donne les DÉPÔTS, pas le code (P=achat/S=vente) → distinguer
achat/vente exige le XML du Form 4 (TODO). Le score mesure l'ACTIVITÉ (proxy), pas le
sens. Parsing séparé du réseau → testable hors-ligne.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from typing import Any

_EFTS = "https://efts.sec.gov/LATEST/search-index?forms=4&q=%22%22&from=0&size={limit}"
_TICKER_RE = re.compile(r"\(([A-Z.]{1,6})\)")


def _get_json(url: str, timeout: float = 6.0) -> Any:
    try:
        ua = {"User-Agent": "quant-terminal research@example.com"}
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URL publique fixe
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - best-effort
        return None


def _parse_efts(data: Any) -> list[dict]:
    """Normalise la réponse EFTS → [{ticker, date, who}] (1 par dépôt Form 4)."""
    out: list[dict] = []
    for h in ((data or {}).get("hits", {}) or {}).get("hits", []):
        src = h.get("_source", {}) or {}
        names = " ".join(src.get("display_names", []) or [])
        m = _TICKER_RE.search(names)
        if not m:
            continue
        out.append({"ticker": m.group(1).replace(".", "-"),
                    "date": src.get("file_date"),
                    "who": (src.get("display_names") or [""])[0]})
    return out


def fetch_recent_form4(limit: int = 100) -> list[dict]:
    """Derniers dépôts Form 4 (best-effort EDGAR). [] si réseau indisponible."""
    return _parse_efts(_get_json(_EFTS.format(limit=limit)))


def insider_cluster_score(filings: list[dict], ticker: str,
                          window_days: int = 30, now: date | None = None) -> int:
    """Dépôts Form 4 DISTINCTS (par déclarant) pour `ticker` sur `window_days`.
    Proxy d'activité d'initiés ; un score élevé = grappe (signal candidat)."""
    from datetime import UTC, datetime
    today = now or datetime.now(UTC).date()
    seen = set()
    for f in filings:
        if f.get("ticker") != ticker or not f.get("date"):
            continue
        try:
            d = date.fromisoformat(str(f["date"])[:10])
        except ValueError:
            continue
        if 0 <= (today - d).days <= window_days:
            seen.add(f.get("who", ""))
    return len(seen)
