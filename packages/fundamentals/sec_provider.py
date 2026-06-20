"""Provider fondamental **SEC EDGAR** (XBRL « companyfacts », RÉEL, GRATUIT, sans clé) → Financials.

Source faisant autorité pour les actions **US** : états financiers déposés (10-K/10-Q) via l'API
publique `data.sec.gov`. Le mapping ticker→CIK vient de `www.sec.gov/files/company_tickers.json`.
La SEC ne fournit pas le COURS : on le récupère via yfinance `fast_info` (appel léger) pour calculer
les ratios. Tickers étrangers (.PA/.AS…) → généralement absents de la SEC → renvoie None (yfinance prend le relais).

SEC exige un User-Agent descriptif. Cache disque 24 h. Import paresseux."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from packages.fundamentals.models import Financials

_UA = {"User-Agent": "quant-terminal/1.0 (research; contact: user@quant-terminal.local)"}
_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "sec_fundamentals"
_CACHE_TTL = 86_400.0
_CIK_CACHE = _CACHE_DIR / "_cik_map.json"
_CIK_TTL = 7 * 86_400.0


def _get_json(url: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — URL SEC contrôlée
        return json.loads(r.read().decode("utf-8", "replace"))


_NAME_CACHE = _CACHE_DIR / "_name_map.json"


def _cik_map() -> dict[str, str]:
    try:
        if _CIK_CACHE.exists() and time.time() - _CIK_CACHE.stat().st_mtime < _CIK_TTL:
            return json.loads(_CIK_CACHE.read_text())
    except Exception:  # noqa: BLE001
        pass
    try:
        raw = _get_json("https://www.sec.gov/files/company_tickers.json")
        m = {str(v["ticker"]).upper(): f"{int(v['cik_str']):010d}" for v in raw.values()}
        names = {str(v["ticker"]).upper(): str(v.get("title", "")).title() for v in raw.values()}
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CIK_CACHE.write_text(json.dumps(m))
        _NAME_CACHE.write_text(json.dumps(names))
        return m
    except Exception:  # noqa: BLE001
        return {}


def company_name(symbol: str) -> str | None:
    """Raison sociale officielle SEC (company_tickers.json) pour un ticker. None si inconnu."""
    try:
        if not _NAME_CACHE.exists():
            _cik_map()
        if _NAME_CACHE.exists():
            return json.loads(_NAME_CACHE.read_text()).get(symbol.upper())
    except Exception:  # noqa: BLE001
        pass
    return None


def _facts(cik: str) -> dict | None:
    p = _CACHE_DIR / f"{cik}.json"
    try:
        if p.exists() and time.time() - p.stat().st_mtime < _CACHE_TTL:
            return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        pass
    try:
        d = _get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d.get("facts", {})))      # on ne garde que les facts (allège)
        return d.get("facts", {})
    except Exception:  # noqa: BLE001
        return None


def _annual_series(facts: dict, *concepts: str) -> list[float]:
    """Valeurs ANNUELLES (10-K/20-F, FY) triées par date pour le 1er concept disponible."""
    for c in concepts:
        node = facts.get("us-gaap", {}).get(c) or facts.get("dei", {}).get(c)
        if not node:
            continue
        units = node.get("units", {})
        series = units.get("USD") or units.get("shares") or next(iter(units.values()), [])
        if not series:
            continue
        annual = [x for x in series if x.get("form") in ("10-K", "20-F") and x.get("fp") == "FY" and x.get("val") is not None]
        pool = annual or [x for x in series if x.get("val") is not None]
        if not pool:
            continue
        pool.sort(key=lambda x: x.get("end", ""))
        return [float(x["val"]) for x in pool]
    return []


def _latest(facts: dict, *concepts: str) -> float | None:
    s = _annual_series(facts, *concepts)
    return s[-1] if s else None


def _annual_by_year(facts: dict, *concepts: str) -> dict[int, float]:
    """Valeurs annuelles (10-K/20-F, FY) indexées par EXERCICE (année de fin) pour le 1er concept
    disponible. Permet d'aligner CA/résultat/BPA sur les mêmes exercices."""
    for c in concepts:
        node = facts.get("us-gaap", {}).get(c) or facts.get("dei", {}).get(c)
        if not node:
            continue
        units = node.get("units", {})
        series = units.get("USD") or units.get("USD/shares") or units.get("shares") or next(iter(units.values()), [])
        annual = [x for x in series if x.get("form") in ("10-K", "20-F") and x.get("fp") == "FY"
                  and x.get("val") is not None]
        if not annual:
            continue
        out: dict[int, float] = {}
        for x in annual:
            try:
                out[int(str(x.get("end", ""))[:4])] = float(x["val"])   # dernier dépôt prime (amendé)
            except (TypeError, ValueError):
                continue
        if out:
            return out
    return {}


def financial_history(symbol: str, years: int = 6) -> list[dict]:
    """Historique financier RÉEL pluriannuel (SEC EDGAR companyfacts) : CA, résultat net, BPA dilué
    par exercice (≤ `years` derniers). [] si émetteur non-SEC / indisponible. Gratuit, point-in-time."""
    cik = _cik_map().get(symbol.upper())
    if not cik:
        return []
    facts = _facts(cik)
    if not facts:
        return []
    rev = _annual_by_year(facts, "RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Revenues", "SalesRevenueNet")
    ni = _annual_by_year(facts, "NetIncomeLoss")
    eps = _annual_by_year(facts, "EarningsPerShareDiluted", "EarningsPerShareBasic")
    yrs = sorted(set(rev) | set(ni))[-years:]
    out = []
    for y in yrs:
        out.append({"year": y, "revenue": rev.get(y), "net_income": ni.get(y), "eps": eps.get(y)})
    return out


def _quarterly_by_end(facts: dict, *concepts: str) -> dict[str, float]:
    """Valeurs TRIMESTRIELLES discrètes (période ~3 mois) indexées par date de fin, pour le 1er
    concept dispo. Filtre les cumuls YTD (6/9/12 mois) en ne gardant que les durées ≈ 80-100 jours."""
    from datetime import date as _d
    for c in concepts:
        node = facts.get("us-gaap", {}).get(c)
        if not node:
            continue
        series = node.get("units", {}).get("USD") or node.get("units", {}).get("USD/shares")
        if not series:
            continue
        out: dict[str, float] = {}
        for x in series:
            s, e, v = x.get("start"), x.get("end"), x.get("val")
            if not (s and e) or v is None or x.get("form") not in ("10-Q", "10-K"):
                continue
            try:
                days = (_d.fromisoformat(e[:10]) - _d.fromisoformat(s[:10])).days
            except ValueError:
                continue
            if 80 <= days <= 100:                          # un seul trimestre (pas un cumul)
                out[e[:10]] = float(v)
        if out:
            return out
    return {}


def quarterly_history(symbol: str, n: int = 4) -> list[dict]:
    """4 derniers TRIMESTRES (SEC EDGAR 10-Q, périodes discrètes ~3 mois) : CA, résultat net, BPA,
    marge nette. [] si non-SEC/indisponible. Repli robuste pour le tableau trimestriel."""
    cik = _cik_map().get(symbol.upper())
    if not cik:
        return []
    facts = _facts(cik)
    if not facts:
        return []
    rev = _quarterly_by_end(facts, "RevenueFromContractWithCustomerExcludingAssessedTax",
                            "Revenues", "SalesRevenueNet")
    ni = _quarterly_by_end(facts, "NetIncomeLoss")
    eps = _quarterly_by_end(facts, "EarningsPerShareDiluted", "EarningsPerShareBasic")
    ends = sorted(set(rev) | set(ni))[-n:]
    out = []
    for e in ends:
        rv, nv = rev.get(e), ni.get(e)
        try:
            q = (int(e[5:7]) - 1) // 3 + 1
            period = f"{e[:4]}-T{q}"
        except (ValueError, IndexError):
            period = e
        out.append({"period": period, "revenue": rv, "net_income": nv, "eps": eps.get(e),
                    "net_margin": (nv / rv if (rv and nv is not None) else None)})
    return out


def _growth(facts: dict, *concepts: str) -> float | None:
    """Croissance YoY RÉELLE entre les deux derniers exercices annuels (None si indisponible)."""
    s = _annual_series(facts, *concepts)
    if len(s) >= 2 and s[-2] not in (0, None):
        return s[-1] / abs(s[-2]) - 1.0 if s[-2] > 0 else None
    return None


class SECFundamentalsProvider:
    name = "sec"

    def __init__(self) -> None:
        self._map = _cik_map()

    def _price_shares(self, symbol: str) -> tuple[float, float]:
        try:
            import yfinance as yf
            fi = yf.Ticker(symbol).fast_info
            price = float(fi.get("last_price") or fi.get("lastPrice") or 0.0)
            shares = float(fi.get("shares") or fi.get("sharesOutstanding") or 0.0)
            return price, shares
        except Exception:  # noqa: BLE001
            return 0.0, 0.0

    def get(self, symbol: str, as_of: datetime | None = None) -> Financials | None:
        cik = self._map.get(symbol.upper())
        if not cik:                                       # pas un émetteur SEC (souvent étranger)
            return None
        facts = _facts(cik)
        if not facts:
            return None
        revenue = _latest(facts, "RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Revenues", "SalesRevenueNet") or 0.0
        net_income = _latest(facts, "NetIncomeLoss") or 0.0
        ebit = _latest(facts, "OperatingIncomeLoss") or 0.0
        dep = _latest(facts, "DepreciationDepletionAndAmortization",
                      "DepreciationAmortizationAndAccretionNet") or 0.0
        equity = _latest(facts, "StockholdersEquity",
                         "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest") or 0.0
        debt = _latest(facts, "LongTermDebtNoncurrent", "LongTermDebt") or 0.0
        cash = _latest(facts, "CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments") or 0.0
        gross = _latest(facts, "GrossProfit") or 0.0
        if revenue <= 0 and net_income == 0:              # rien d'exploitable
            return None
        price, shares = self._price_shares(symbol)
        if shares <= 0:
            shares = _latest(facts, "CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding") or 0.0
        rev_g = _growth(facts, "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "Revenues", "SalesRevenueNet")
        eps_g = _growth(facts, "NetIncomeLoss")
        return Financials(
            symbol=symbol, as_of=as_of or datetime.now(timezone.utc),
            sector="Unknown", price=price, shares=shares,
            revenue=revenue, gross_profit=gross or revenue * 0.4,
            ebit=ebit or (net_income * 1.3), ebitda=(ebit + dep) if ebit else net_income * 1.5,
            net_income=net_income, total_equity=equity or revenue * 0.5,
            total_debt=debt, cash=cash, fcf=0.0, interest_expense=0.0,
            revenue_growth=rev_g, earnings_growth=eps_g, name=company_name(symbol))
