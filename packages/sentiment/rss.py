"""Lecteur **RSS** de titres financiers — stdlib pure (`urllib` + `xml`), hors-ligne-safe.

Aucune clé, aucune dépendance. En cas d'absence de réseau (CI/cloud) ou d'erreur, renvoie une
liste vide : l'appelant retombe alors sur un signal dérivé du momentum (cf. snapshot). Les flux
par défaut sont génériques ; on peut viser un ticker précis via Yahoo Finance (gratuit).
"""

from __future__ import annotations

import urllib.request
from xml.etree import ElementTree as ET

# Flux génériques marché (gratuits, sans clé). Court timeout → ne bloque jamais un build.
DEFAULT_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.investing.com/rss/news_25.rss",
]

# Macro & banques centrales (décisions FED/BCE/FMI, économie) — flux RSS publics gratuits.
MACRO_FEEDS = [
    "https://www.federalreserve.gov/feeds/press_all.xml",       # FED (communiqués)
    "https://www.ecb.europa.eu/rss/press.xml",                  # BCE
    "https://www.imf.org/en/News/RSS?Language=ENG&Series=News",  # FMI
    "https://www.investing.com/rss/news_95.rss",                # économie / banques centrales
]


def yahoo_feed(symbol: str) -> str:
    """Flux RSS Yahoo Finance par ticker (titres spécifiques à un actif)."""
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


def fetch_headlines(feeds: list[str] | None = None, limit: int = 20,
                    timeout: float = 4.0) -> list[dict]:
    """Récupère des titres `{title, link, source}` ; [] si réseau indisponible.

    Tolère les erreurs feed par feed (jamais d'exception remontée).
    """
    out: list[dict] = []
    for url in (feeds or DEFAULT_FEEDS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 quant-terminal"})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixe/contrôlée)
                root = ET.fromstring(r.read())
            for item in root.iter("item"):
                t = item.findtext("title")
                if t:
                    out.append({"title": t.strip(), "link": (item.findtext("link") or "").strip(),
                                "source": url})
                if len(out) >= limit:
                    return out
        except Exception:  # noqa: BLE001  — hors-ligne / flux HS → on ignore
            continue
    return out
