from datetime import datetime, timezone
from packages.core.models import CyclePhase, MacroObservation as MO, RiskMode
from packages.storage import MacroStore
from packages.regime import MacroRegimeClassifier


def _d(s): return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_recession_when_inverted_and_contracting():
    ms = MacroStore(":memory:")
    rt = _d("2024-01-05")
    ms.upsert([MO("T10Y3M", _d("2024-01-01"), -0.5, rt),
               MO("ISM", _d("2024-01-01"), 47, rt),
               MO("VIXCLS", _d("2024-01-01"), 18, rt)])
    rs = MacroRegimeClassifier(ms).classify(_d("2024-02-01"))
    assert rs.cycle is CyclePhase.RECESSION


def test_expansion_when_healthy():
    ms = MacroStore(":memory:")
    rt = _d("2024-01-05")
    ms.upsert([MO("T10Y3M", _d("2024-01-01"), 0.8, rt),
               MO("ISM", _d("2024-01-01"), 55, rt),
               MO("VIXCLS", _d("2024-01-01"), 14, rt)])
    rs = MacroRegimeClassifier(ms).classify(_d("2024-02-01"))
    assert rs.cycle is CyclePhase.EXPANSION and rs.risk_mode is RiskMode.RISK_ON


def test_high_vix_forces_risk_off():
    ms = MacroStore(":memory:")
    rt = _d("2024-01-05")
    ms.upsert([MO("T10Y3M", _d("2024-01-01"), 0.8, rt),
               MO("ISM", _d("2024-01-01"), 55, rt),
               MO("VIXCLS", _d("2024-01-01"), 40, rt)])
    assert MacroRegimeClassifier(ms).classify(_d("2024-02-01")).risk_mode is RiskMode.RISK_OFF
