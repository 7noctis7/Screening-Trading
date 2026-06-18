"""Sources de news enrichies (optionnelles) : OpenBB / FinNLP si installés, sinon RSS Yahoo.

Import paresseux + repli propre (comme l'adaptateur skfolio) : aucune dépendance requise. Plus de
sources = meilleure CORROBORATION pour le garde-fou sémantique (Taleb) → moins de faux signaux.

Installation : `pip install openbb` (ou `finnlp`). Sinon, le RSS gratuit existant suffit.
"""

from __future__ import annotations


def _from_openbb(symbol: str, limit: int) -> list[dict] | None:
    try:
        from openbb import obb
        res = obb.news.company(symbol=symbol, limit=limit)
        rows = res.results if hasattr(res, "results") else res
        out = []
        for r in rows[:limit]:
            title = getattr(r, "title", None) or (r.get("title") if isinstance(r, dict) else None)
            if title:
                out.append({"title": title, "link": getattr(r, "url", "") or "", "source": "openbb"})
        return out or None
    except Exception:  # noqa: BLE001
        return None


def fetch_company_news(symbol: str, limit: int = 12) -> list[dict]:
    """Titres pour un actif : OpenBB si dispo, sinon RSS Yahoo (toujours fonctionnel)."""
    rows = _from_openbb(symbol, limit)
    if rows:
        return rows
    try:
        from packages.sentiment.rss import fetch_headlines, yahoo_feed
        return [{**h, "source": "rss"} for h in fetch_headlines([yahoo_feed(symbol)], limit=limit)]
    except Exception:  # noqa: BLE001
        return []


def sources_available() -> dict:
    """Quelles sources enrichies sont installées (pour affichage / diagnostic)."""
    def _ok(mod: str) -> bool:
        try:
            __import__(mod); return True
        except Exception:  # noqa: BLE001
            return False
    return {"openbb": _ok("openbb"), "finnlp": _ok("finnlp"), "rss": True}
