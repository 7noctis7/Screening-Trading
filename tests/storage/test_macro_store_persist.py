"""P1-3 — MacroStore PERSISTANT : les vintages survivent à la fermeture (fichier, pas :memory:)."""
from datetime import datetime, timezone

from packages.core.models import MacroObservation
from packages.storage import MacroStore


def _o(sid, obs_d, val, pub_d):
    dt = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731
    return MacroObservation(sid, dt(obs_d), val, dt(pub_d))


def test_persist_and_pit_across_reopen(tmp_path):
    db = tmp_path / "macro.db"
    s1 = MacroStore(db)
    # CPI de mars : 1re publication en avril (300.0), RÉVISÉ en juin (301.5)
    s1.upsert([_o("CPIAUCSL", "2026-03-01", 300.0, "2026-04-10"),
               _o("CPIAUCSL", "2026-03-01", 301.5, "2026-06-10")])
    s1.close()
    s2 = MacroStore(db)                                  # ré-ouverture = persistance prouvée
    dt = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)  # noqa: E731
    # en mai, seule la 1re publication existe (PIT : la révision de juin est invisible)
    assert s2.as_of("CPIAUCSL", dt("2026-05-01"))[1] == 300.0
    # en juillet, la révision est publique
    assert s2.as_of("CPIAUCSL", dt("2026-07-01"))[1] == 301.5
    # en mars (avant toute publication), la donnée N'EXISTE PAS
    assert s2.as_of("CPIAUCSL", dt("2026-03-15")) is None


def test_upsert_skips_non_finite_values(tmp_path):
    """CI 15/07 : NaN yfinance → NULL sqlite → IntegrityError. Non-fini = ignoré, pas crashé."""
    s = MacroStore(tmp_path / "m.db")
    dt = lambda d: datetime.fromisoformat(d).replace(tzinfo=timezone.utc)  # noqa: E731
    s.upsert([_o("ISM", "2026-07-01", float("nan"), "2026-07-01"),
              _o("ISM", "2026-07-02", float("inf"), "2026-07-02"),
              _o("ISM", "2026-07-03", 52.0, "2026-07-03")])
    assert s.as_of("ISM", dt("2026-07-10"))[1] == 52.0     # seule la valeur réelle survit
    assert s.as_of("ISM", dt("2026-07-01"))is None or s.as_of("ISM", dt("2026-07-01"))[1] == 52.0
