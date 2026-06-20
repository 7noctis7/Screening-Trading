"""Régression CI/CD — intégrité des données (cadre d'audit PwC). Doit ÉCHOUER si la logique
d'audit ou de parsing est corrompue par une mise à jour."""

from datetime import date

import pytest

from packages.data.audit import (
    AuditReport,
    DataIntegrityError,
    assert_integrity,
    audit_dataset,
    audit_series,
    survivorship_check,
)


def _good(n=120, start=date(2026, 1, 1)):
    from datetime import timedelta
    out, px = [], 100.0
    d = start
    i = 0
    while len(out) < n:
        if d.weekday() < 5:                                # jours ouvrés seulement
            px *= 1.002
            out.append({"ts": d.isoformat(), "o": px, "h": px * 1.01, "l": px * 0.99, "c": px, "v": 1000})
            i += 1
        d = d + timedelta(days=1)
    return out


def test_clean_series_has_no_critical():
    rep = audit_dataset({"AAA": _good()}, now=date(2026, 7, 1))
    assert rep.ok and not rep.critical


def test_negative_price_is_critical():
    bars = _good(); bars[10]["c"] = -5.0
    a = audit_series("AAA", bars, now=date(2026, 7, 1))
    assert any(x.severity == "critical" and x.kind == "accuracy" for x in a)


def test_high_below_low_is_critical():
    bars = _good(); bars[5]["h"], bars[5]["l"] = 90.0, 110.0
    assert any(x.severity == "critical" for x in audit_series("AAA", bars, now=date(2026, 7, 1)))


def test_future_bar_is_pit_leak_critical():
    bars = _good(); bars[-1]["ts"] = "2999-01-01"
    a = audit_series("AAA", bars, now=date(2026, 7, 1))
    assert any(x.kind == "point_in_time" and x.severity == "critical" for x in a)


def test_split_jump_is_warning():
    bars = _good(); bars[60]["c"] = bars[60]["c"] * 2          # +100 % en 1 j
    a = audit_series("AAA", bars, now=date(2026, 7, 1))
    assert any(x.kind == "accuracy" and x.severity == "warning" for x in a)


def test_gaps_flagged_major():
    bars = _good(20)                                          # 20 barres mais étalées → trous
    bars = [bars[0], bars[-1]]                                # 2 barres sur ~1 mois → énorme trou
    a = audit_series("AAA", bars, now=date(2026, 7, 1), min_bars=2)
    assert any(x.kind == "completeness" for x in a)


def test_survivorship_warns_when_no_delisted(tmp_path):
    an = survivorship_check(["AAPL"], tmp_path / "absent.csv")
    assert an is not None and an.kind == "survivorship" and an.severity == "warning"


def test_assert_integrity_raises_on_critical():
    rep = AuditReport()
    from packages.data.audit import Anomaly
    rep.anomalies.append(Anomaly("X", "accuracy", "critical", "prix négatif"))
    with pytest.raises(DataIntegrityError):
        assert_integrity(rep)


def test_assert_integrity_passes_when_clean():
    assert_integrity(audit_dataset({"AAA": _good()}, now=date(2026, 7, 1)))   # ne lève pas


class _Bar:                                                  # objet type Bar (attributs, pas dict)
    __slots__ = ("ts", "open", "high", "low", "close", "volume")

    def __init__(self, d):
        self.ts, self.open, self.high = d["ts"], d["o"], d["h"]
        self.low, self.close, self.volume = d["l"], d["c"], d["v"]


def test_gate_accepts_bar_objects():
    # la gate du snapshot passe des objets Bar (attributs) — l'audit doit les lire comme les dicts.
    bars = [_Bar(d) for d in _good()]
    rep = audit_dataset({"AAA": bars}, now=date(2026, 7, 1))
    assert rep.ok and not rep.critical


def test_gate_catches_critical_on_bar_objects():
    bars = [_Bar(d) for d in _good()]
    bars[10].close = -1.0                                     # prix négatif → critique
    a = audit_series("AAA", bars, now=date(2026, 7, 1))
    assert any(x.severity == "critical" for x in a)
