"""Biais du survivant : dérivation point-in-time des délistés + écriture/fusion CSV."""
from datetime import date

from packages.data.survivorship import (
    derive_delisted,
    load_delisted,
    survivorship_audit,
    write_delisted,
)


def test_derive_flags_stale_symbols():
    asof = date(2026, 6, 20)
    last = {"AAPL": "2026-06-19", "DEAD": "2026-01-01", "OLD": "2025-12-01"}
    rows = derive_delisted(last, asof=asof, stale_days=60)
    syms = {r["symbol"] for r in rows}
    assert "DEAD" in syms and "OLD" in syms and "AAPL" not in syms   # AAPL récent → coté


def test_derive_ignores_future_dates():
    asof = date(2026, 6, 20)
    rows = derive_delisted({"FUT": "2999-01-01"}, asof=asof, stale_days=30)
    assert rows == []                                                # pas de fuite future


def test_derive_attaches_name_sector():
    rows = derive_delisted({"X": "2020-01-01"}, asof=date(2026, 1, 1),
                           names={"X": "Xco"}, sectors={"X": "Tech"})
    assert rows[0]["name"] == "Xco" and rows[0]["sector"] == "Tech"


def test_write_and_merge_delisted(tmp_path):
    p = tmp_path / "delisted.csv"
    n1 = write_delisted([{"symbol": "A", "name": "Aco", "sector": "Fin", "delisted_on": "2020-01-01"}], p)
    assert n1 == 1
    n2 = write_delisted([{"symbol": "B", "name": "", "sector": "", "delisted_on": "2021-01-01"}], p)
    assert n2 == 2                                                   # fusion : A conservé + B ajouté
    loaded = {r["symbol"] for r in load_delisted(p)}
    assert loaded == {"A", "B"}


def test_audit_reports_corrected_after_write(tmp_path):
    p = tmp_path / "delisted.csv"
    write_delisted([{"symbol": "Z", "name": "", "sector": "", "delisted_on": "2019-01-01"}], p)
    a = survivorship_audit(["AAPL", "MSFT"], delisted=load_delisted(p))
    assert a["corrected"] and a["n_delisted"] == 1
