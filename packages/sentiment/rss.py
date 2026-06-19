"""Lecteur **RSS/Atom** de titres financiers — stdlib pure (`urllib` + `xml`), hors-ligne-safe.

Aucune clé, aucune dépendance. En cas d'absence de réseau (CI/cloud) ou d'erreur, renvoie une
liste vide : l'appelant retombe alors sur un signal dérivé du momentum (cf. snapshot).

Parse la DATE de publication (pubDate / dc:date / Atom updated|published), permet de ne garder que
les articles RÉCENTS (année en cours), déduplique et trie du plus récent au plus ancien →
qualité plutôt que quantité, fini les liens de 2025 et antérieurs.
"""

from __future__ import annotations

import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

# Flux génériques marché (gratuits, sans clé, mis à jour en continu). Court timeout → build non bloquant.
DEFAULT_FEEDS = [
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",      # CNBC Markets
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",  # WSJ Markets
    "http://feeds.marketwatch.com/marketwatch/topstories/",      # MarketWatch top
    "https://www.investing.com/rss/news_25.rss",                 # Investing.com marchés
]

# Macro & banques centrales (décisions FED/BCE/FMI, économie) — flux RSS publics gratuits.
MACRO_FEEDS = [
    "https://www.federalreserve.gov/feeds/press_all.xml",       # FED (communiqués)
    "https://www.ecb.europa.eu/rss/press.xml",                  # BCE
    "https://www.imf.org/en/News/RSS?Language=ENG&Series=News",  # FMI
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",     # CNBC (économie/marchés)
    "https://www.investing.com/rss/news_95.rss",                # économie / banques centrales
]


def yahoo_feed(symbol: str) -> str:
    """Flux RSS Yahoo Finance par ticker (titres spécifiques à un actif)."""
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()      # enlève le namespace XML ({...}title → title)


def _parse_date(item) -> datetime | None:
    """Date de publication (RSS pubDate/dc:date ou Atom updated/published) → datetime UTC."""
    raw = None
    for el in item:
        if _local(el.tag) in ("pubdate", "date", "published", "updated") and (el.text or "").strip():
            raw = el.text.strip()
            break
    if not raw:
        return None
    try:                                       # RFC 2822 (RSS) : "Wed, 02 Oct 2026 13:00:00 GMT"
        d = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:                                   # ISO 8601 (Atom) : "2026-10-02T13:00:00Z"
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _link_of(item) -> str:
    for el in item:
        if _local(el.tag) == "link":
            return (el.text or el.get("href") or "").strip()   # RSS (texte) ou Atom (href)
    return ""


def fetch_headlines(feeds: list[str] | None = None, limit: int = 20, timeout: float = 4.0,
                    current_year_only: bool = True, max_age_days: int | None = None) -> list[dict]:
    """Titres `{title, link, source, date, ts}` RÉCENTS, dédupliqués, triés du plus récent au plus
    ancien. Par défaut ne garde que l'ANNÉE EN COURS. [] si réseau indisponible."""
    now = datetime.now(timezone.utc)
    out: dict[str, dict] = {}                  # clé = titre normalisé → déduplication
    for url in (feeds or DEFAULT_FEEDS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 quant-terminal"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixe/contrôlée)
                root = ET.fromstring(r.read())
            for item in root.iter():
                if _local(item.tag) not in ("item", "entry"):
                    continue
                title = next((e.text for e in item if _local(e.tag) == "title" and e.text), None)
                if not title:
                    continue
                title = title.strip()
                d = _parse_date(item)
                if d is not None:              # filtres de fraîcheur (on EXIGE une date sinon on garde)
                    if current_year_only and d.year != now.year:
                        continue
                    if max_age_days is not None and (now - d).days > max_age_days:
                        continue
                key = title.lower()
                if key in out:
                    continue
                out[key] = {"title": title, "link": _link_of(item), "source": url,
                            "date": d.date().isoformat() if d else "",
                            "ts": d.timestamp() if d else 0.0}
        except Exception:  # noqa: BLE001  — hors-ligne / flux HS → on ignore
            continue
    items = sorted(out.values(), key=lambda x: x["ts"], reverse=True)   # plus récent d'abord
    return items[:limit]
