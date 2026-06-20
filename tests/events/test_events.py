"""Parsing PUR du calendrier d'événements (réseau encapsulé ailleurs) : earnings FMP/yfinance + IPOs SEC/FMP."""

from packages.events.earnings import parse_fmp_earnings, parse_yf_calendar
from packages.events.ipos import parse_edgar_atom, parse_fmp_ipos, upcoming_ipos


def test_parse_fmp_earnings_filters_and_maps():
    rows = [
        {"symbol": "AAPL", "date": "2026-07-30", "time": "amc",
         "epsEstimated": 1.42, "eps": 1.50, "revenueEstimated": 9.4e10, "revenue": 9.6e10},
        {"symbol": "ZZZZ", "date": "2026-07-31", "epsEstimated": 0.1},     # hors univers → filtré
    ]
    out = parse_fmp_earnings(rows, {"AAPL"})
    assert len(out) == 1
    e = out[0]
    assert e["symbol"] == "AAPL" and e["eps_estimate"] == 1.42 and e["eps_actual"] == 1.50
    assert e["revenue_estimate"] == 9.4e10 and e["revenue_actual"] == 9.6e10 and e["source"] == "FMP"


def test_parse_fmp_earnings_handles_missing():
    out = parse_fmp_earnings([{"symbol": "MU", "date": "2026-09-25", "epsEstimated": "", "eps": None}], set())
    assert out[0]["eps_estimate"] is None and out[0]["eps_actual"] is None


def test_num_rejects_nan():
    from packages.events.earnings import _num
    assert _num(float("nan")) is None        # NaN pandas → None (pas de "réel" fantôme)
    assert _num("") is None and _num(None) is None
    assert _num("1.5") == 1.5 and _num(3) == 3.0


def test_parse_yf_calendar():
    import datetime as _d
    cal = {"Earnings Date": [_d.date(2026, 7, 29)], "Earnings Average": 1.1, "Revenue Average": 5.0e9}
    ev = parse_yf_calendar("MU", cal, last_eps_actual=0.95)
    assert ev["symbol"] == "MU" and ev["date"] == "2026-07-29"
    assert ev["eps_estimate"] == 1.1 and ev["revenue_estimate"] == 5.0e9 and ev["eps_actual"] == 0.95
    assert parse_yf_calendar("X", None) is None


def test_parse_edgar_atom():
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>S-1 - ACME ROBOTICS INC (0001999999) (Filer)</title>
        <updated>2026-06-15T10:00:00-04:00</updated>
        <link href="https://www.sec.gov/Archives/edgar/data/1999999/abc.htm"/>
      </entry>
      <entry>
        <title>S-1/A - NEON AI CORP (0001888888) (Filer)</title>
        <updated>2026-06-14T09:00:00-04:00</updated>
        <link href="https://www.sec.gov/x.htm"/>
      </entry>
    </feed>"""
    out = parse_edgar_atom(xml)
    assert len(out) == 2
    assert out[0]["name"] == "ACME ROBOTICS INC" and out[0]["form"] == "S-1"
    assert out[0]["date"] == "2026-06-15" and out[0]["source"] == "SEC EDGAR"
    assert out[1]["form"] == "S-1/A" and out[1]["name"] == "NEON AI CORP"


def test_parse_edgar_atom_bad_xml_is_safe():
    assert parse_edgar_atom("not xml") == []


def test_parse_fmp_ipos_valuation_from_pricerange():
    rows = [{"date": "2026-07-01", "symbol": "newco", "company": "NewCo Inc", "exchange": "NASDAQ",
             "priceRange": "18-20", "shares": 10_000_000}]
    out = parse_fmp_ipos(rows)
    assert out[0]["ticker"] == "NEWCO" and out[0]["price_range"] == "18-20"
    assert out[0]["valuation"] == 10_000_000 * 20         # actions × haut de fourchette


def test_upcoming_ipos_offline_returns_list():
    # réseau isolé → ne lève pas, renvoie une liste (vide ou non)
    assert isinstance(upcoming_ipos(), list)
