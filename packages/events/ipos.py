"""Prochaines IPOs US — source primaire **SEC EDGAR** (dépôts S-1 / S-1/A = pipeline d'introductions
en bourse) + enrichissement **FMP** (ticker, fourchette de prix, valorisation) si `FMP_API_KEY`.

- EDGAR « getcurrent » renvoie les derniers dépôts d'un type de formulaire, tous émetteurs confondus
  (flux Atom, gratuit, sans clé) → société, formulaire, date, lien du dépôt. Source faisant autorité.
- FMP `/v3/ipo_calendar` ajoute le ticker, la fourchette de prix, le nombre d'actions, la valorisation.

Parsing pur (testable) ; réseau encapsulé et tolérant aux pannes (renvoie [] si indisponible).
SEC exige un User-Agent descriptif → on en fournit un."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

_FMP_BASE = "https://financialmodelingprep.com/api/v3"
_EDGAR = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={form}"
          "&company=&dateb=&owner=include&count=100&output=atom")
_UA = {"User-Agent": "quant-terminal/1.0 (research; contact: user@quant-terminal.local)"}
_ATOM = "{http://www.w3.org/2005/Atom}"


def _num(x) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_edgar_atom(xml_text: str) -> list[dict]:
    """Parse un flux Atom EDGAR « getcurrent » → [{name, form, date, link, source:'SEC EDGAR'}].
    Le titre EDGAR ressemble à « S-1 - ACME INC (0001234567) (Filer) »."""
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:  # noqa: BLE001
        return out
    for e in root.findall(f"{_ATOM}entry"):
        title = (e.findtext(f"{_ATOM}title") or "").strip()
        updated = (e.findtext(f"{_ATOM}updated") or "").strip()[:10]
        link_el = e.find(f"{_ATOM}link")
        link = link_el.get("href") if link_el is not None else ""
        form, name = "", title
        m = re.match(r"\s*([A-Z0-9/\-]+)\s*-\s*(.+?)\s*(?:\((\d{6,10})\))?\s*(?:\((Filer)\))?\s*$", title)
        if m:
            form, name = m.group(1), m.group(2).strip()
        out.append({"name": name, "form": form or "S-1", "date": updated,
                    "ticker": "", "exchange": "", "industry": "", "price_range": "",
                    "valuation": None, "shares": None, "status": "dépôt SEC",
                    "link": link, "source": "SEC EDGAR"})
    return out


def parse_fmp_ipos(rows: list[dict]) -> list[dict]:
    """Normalise FMP `/v3/ipo_calendar` → [{date, ticker, name, exchange, price_range, valuation,...}]."""
    out: list[dict] = []
    for r in rows or []:
        shares = _num(r.get("shares"))
        pr = str(r.get("priceRange", "") or "").strip()
        val = _num(r.get("marketCap"))
        if val is None and shares and pr:                  # valorisation ≈ actions × prix haut de fourchette
            hi = re.findall(r"[\d.]+", pr)
            if hi:
                val = shares * float(hi[-1])
        out.append({
            "date": str(r.get("date", ""))[:10], "ticker": str(r.get("symbol", "")).upper(),
            "name": r.get("company", "") or "", "exchange": r.get("exchange", "") or "",
            "industry": r.get("sector", "") or r.get("industry", "") or "",
            "price_range": pr, "valuation": val, "shares": shares,
            "status": r.get("actions", "") or "prévue", "link": "", "source": "FMP",
        })
    return out


def _edgar_ipos(forms: tuple[str, ...] = ("S-1", "S-1/A")) -> list[dict]:
    out: list[dict] = []
    for form in forms:
        try:
            req = urllib.request.Request(_EDGAR.format(form=form.replace("/", "%2F")), headers=_UA)
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — URL SEC contrôlée
                out += parse_edgar_atom(r.read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            continue
    return out


def _fmp_ipos(days_back: int, days_fwd: int) -> list[dict]:
    key = os.environ.get("FMP_API_KEY", "")
    if not key:
        return []
    today = datetime.now(timezone.utc).date()
    frm = (today - timedelta(days=days_back)).isoformat()
    to = (today + timedelta(days=days_fwd)).isoformat()
    url = f"{_FMP_BASE}/ipo_calendar?from={frm}&to={to}&apikey={key}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 — URL FMP contrôlée
            rows = json.loads(r.read().decode())
        return parse_fmp_ipos(rows if isinstance(rows, list) else [])
    except Exception:  # noqa: BLE001
        return []


def _merge(fmp: list[dict], edgar: list[dict]) -> list[dict]:
    """Fusionne FMP (riche : ticker/prix/valo) et EDGAR (autorité), en dédupliquant par nom de société."""
    def _key(n: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (n or "").lower())[:18]
    by = {}
    for r in fmp:                                          # FMP d'abord (plus d'infos)
        by[_key(r["name"])] = r
    for r in edgar:
        k = _key(r["name"])
        if k in by:
            by[k].setdefault("link", r.get("link", ""))    # garde le lien SEC si FMP n'en a pas
            if not by[k].get("link"):
                by[k]["link"] = r.get("link", "")
            by[k]["sec_form"] = r.get("form", "")
        else:
            by[k] = r
    rows = list(by.values())
    rows.sort(key=lambda r: (r.get("date") or "9999", r.get("name", "")))
    return rows


def upcoming_ipos(days_back: int = 21, days_fwd: int = 60, limit: int = 60) -> list[dict]:
    """Prochaines IPOs US (dépôts S-1/S-1/A SEC + calendrier FMP si clé). Triées par date."""
    rows = _merge(_fmp_ipos(days_back, days_fwd), _edgar_ipos())
    return rows[:limit]
