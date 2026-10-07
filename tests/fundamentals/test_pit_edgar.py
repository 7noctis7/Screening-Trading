"""Un 10-K déposé en 2026 n'existe pas pour un backtest arrêté en 2018."""

from datetime import UTC, datetime

from packages.fundamentals.pit_edgar import choisir, horodatage, mesures


def _facts(filed="2026-02-15", acceptance=None):
    fait = {"end": "2025-12-31", "val": 1000.0, "form": "10-K", "fp": "FY",
            "filed": filed, "accn": "0001-26"}
    if acceptance:
        fait["acceptanceDateTime"] = acceptance
    return {"us-gaap": {"Revenues": {"units": {"USD": [fait]}}}}


def test_acceptance_prime_sur_la_date_de_depot():
    kt, q = horodatage(_facts(acceptance="2026-02-14T21:07:00Z")["us-gaap"]
                       ["Revenues"]["units"]["USD"][0])
    assert q == "EXACT" and kt.startswith("2026-02-14T21:07")


def test_filed_seul_est_un_decalage_inferé():
    kt, q = horodatage(_facts()["us-gaap"]["Revenues"]["units"]["USD"][0])
    assert (kt, q) == ("2026-02-15", "INFERRED_LAG")


def test_2018_ne_voit_pas_le_depot_de_2026():
    val, kt, q = choisir(_facts(), ("Revenues",), as_of="2018-06-01")
    assert val is None and q == "UNKNOWN" and kt is None


def test_apres_le_depot_la_valeur_est_visible():
    val, kt, q = choisir(_facts(), ("Revenues",), as_of="2026-03-01")
    assert val == 1000.0 and kt == "2026-02-15" and q == "INFERRED_LAG"


def test_get_sec_respecte_as_of(monkeypatch):
    from packages.fundamentals import sec_provider as sec
    monkeypatch.setattr(sec, "_cik_map", lambda: {"XYZ": "0000000001"})
    monkeypatch.setattr(sec, "_facts", lambda cik: _facts())
    p = sec.SECFundamentalsProvider()
    monkeypatch.setattr(p, "_price_shares", lambda s: (10.0, 50.0))
    ancien = datetime(2018, 6, 1, tzinfo=UTC)
    assert p.get("XYZ", as_of=ancien) is None
    recent = p.get("XYZ")
    assert recent is not None and recent.revenue == 1000.0
    assert recent.kt_quality == "INFERRED_LAG"
    assert recent.knowledge_time == "2026-02-15"
    assert mesures(_facts(), "2018-01-01")["revenue"] is None
