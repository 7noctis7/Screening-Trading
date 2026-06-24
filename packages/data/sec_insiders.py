"""Insiders SEC (Form 4) via EDGAR full-text search — lecture publique, sans clé, 0 €.

Thèse : une GRAPPE de transactions d'initiés signale une asymétrie d'info → dérive
positive 1-3 mois. Fetcher best-effort (offline-safe) + score de cluster = nb de dépôts
Form 4 récents pour un ticker.

Deux niveaux : (1) `insider_cluster_score` = ACTIVITÉ (proxy, depuis la full-text) ;
(2) `parse_form4_xml` + `net_insider_signal` = SENS réel achat/vente (depuis le XML du
Form 4). Parsing séparé du réseau → testable hors-ligne.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from typing import Any

_EFTS = "https://efts.sec.gov/LATEST/search-index?forms=4&q=%22%22&from=0&size={limit}"
_TICKER_RE = re.compile(r"\(([A-Z.]{1,6})\)")
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


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


def _parse_cik_registry(data: Any, ticker: str) -> str | None:
    """Registre SEC ticker→CIK → CIK 10 chiffres (zero-paddé). None si absent."""
    if not isinstance(data, dict):
        return None
    want = ticker.upper()
    for row in data.values():
        if str((row or {}).get("ticker", "")).upper() == want:
            try:
                return f"{int(row['cik_str']):010d}"
            except (KeyError, ValueError, TypeError):
                return None
    return None


def ticker_to_cik(ticker: str) -> str | None:
    """Ticker → CIK (10 chiffres) via le registre public SEC. None si introuvable."""
    return _parse_cik_registry(_get_json(_TICKERS_URL), ticker)


def _parse_form4_dates(submissions: Any, limit: int = 120) -> list[str]:
    """Réponse submissions EDGAR → dates de dépôt des Form 4 (triées, dédup)."""
    recent = (((submissions or {}).get("filings", {}) or {}).get("recent", {}) or {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    out = [d for f, d in zip(forms, dates) if str(f) == "4" and d]
    return sorted(set(out))[-limit:]


def form4_dates_for_ticker(ticker: str, limit: int = 120) -> list[str]:
    """Dates de dépôt des Form 4 d'UN ticker (EDGAR submissions par CIK). [].

    Contrairement à `fetch_recent_form4` (flux global), cette requête est ciblée :
    ticker → CIK → /submissions → on filtre form == "4". C'est ce qui permet
    l'event-study insiders par ticker (et le mode PANIER --source insider).
    """
    cik = ticker_to_cik(ticker)
    if not cik:
        return []
    return _parse_form4_dates(_get_json(_SUBMISSIONS.format(cik=int(cik))), limit)


def _parse_form4_filings(submissions: Any) -> list[dict]:
    """Submissions EDGAR → [{date, accession, primary_doc}] des Form 4 (testable)."""
    recent = (((submissions or {}).get("filings", {}) or {}).get("recent", {}) or {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accs = recent.get("accessionNumber", []) or []
    docs = recent.get("primaryDocument", []) or []
    out: list[dict] = []
    for f, d, acc, doc in zip(forms, dates, accs, docs):
        if str(f) == "4" and d and acc and doc:
            out.append({"date": d, "accession": acc, "primary_doc": doc})
    return out


def _form4_xml_url(cik: str, accession: str, primary_doc: str) -> str:
    """URL du document Form 4 (XML brut) sur EDGAR.

    `primaryDocument` pointe souvent vers la version XSLT-rendue (HTML), ex.
    `xslF345X03/wf-form4.xml` ; le XML brut est le même nom SANS ce préfixe.
    """
    acc = accession.replace("-", "")
    doc = primary_doc
    if "/" in doc and doc.lower().startswith("xsl"):
        doc = doc.split("/", 1)[1]                 # retire le préfixe XSLT → XML brut
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}"


def _get_text(url: str, timeout: float = 6.0) -> str | None:
    try:
        ua = {"User-Agent": "quant-terminal research@example.com"}
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - best-effort
        return None


def form4_buy_dates_for_ticker(ticker: str, limit: int = 40,
                               pause: float = 0.12) -> list[str]:
    """Dates des Form 4 = ACHAT NET d'un ticker (XML parsé). Best-effort, [].

    Filtre le bruit : on ne garde que les dépôts où l'initié ACHÈTE plus qu'il ne vend
    (`direction == 'buy'`). Élimine ventes, exercices d'options et plans 10b5-1. `pause`
    espace les requêtes (politesse SEC ≤10/s, anti rate-limit).
    """
    import time

    cik = ticker_to_cik(ticker)
    if not cik:
        return []
    data = _get_json(_SUBMISSIONS.format(cik=int(cik)))
    out: list[str] = []
    for f in _parse_form4_filings(data)[-limit:]:
        xml = _get_text(_form4_xml_url(cik, f["accession"], f["primary_doc"]))
        if xml and parse_form4_xml(xml).get("direction") == "buy":
            out.append(f["date"])
        if pause:
            time.sleep(pause)
    return sorted(set(out))


def parse_form4_xml(xml_text: str) -> dict:
    """Parse un Form 4 (XML) → sens RÉEL (achat/vente), pas juste l'activité.

    Code A = acquired (achat), D = disposed (vente) ; code P=purchase / S=sale en repli.
    Renvoie {available, acquired, disposed, n_buys, n_sells, net_shares, direction}.
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {"available": False}
    acq = dis = 0.0
    n_buys = n_sells = 0
    for tx in root.iter("nonDerivativeTransaction"):
        code = (tx.findtext(".//transactionCode") or "").strip().upper()
        ad_path = ".//transactionAcquiredDisposedCode/value"
        ad = (tx.findtext(ad_path) or "").strip().upper()
        raw = tx.findtext(".//transactionShares/value")
        try:
            shares = float(raw) if raw else 0.0
        except ValueError:
            shares = 0.0
        if ad == "A" or code == "P":
            acq += shares
            n_buys += 1
        elif ad == "D" or code == "S":
            dis += shares
            n_sells += 1
    direction = "buy" if acq > dis else "sell" if dis > acq else "neutral"
    return {"available": True, "acquired": acq, "disposed": dis,
            "n_buys": n_buys, "n_sells": n_sells, "net_shares": acq - dis,
            "direction": direction}


def net_insider_signal(parsed: list[dict]) -> dict:
    """Agrège des Form 4 parsés → cluster directionnel (achat net vs vente)."""
    avail = [p for p in parsed if p.get("available")]
    if not avail:
        return {"available": False}
    buys = sum(1 for p in avail if p["direction"] == "buy")
    sells = sum(1 for p in avail if p["direction"] == "sell")
    net_sh = sum(p["net_shares"] for p in avail)
    return {"available": True, "n_buyers": buys, "n_sellers": sells,
            "net_shares": net_sh, "cluster": buys - sells,
            "bullish": buys > sells and net_sh > 0}


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
