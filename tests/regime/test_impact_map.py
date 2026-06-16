from datetime import datetime, timezone
from packages.core.models import CyclePhase, RegimeState, RiskMode
from packages.common import load_yaml
from packages.regime import MacroImpactMap


def _imp(): return MacroImpactMap(load_yaml("config/macro_impact.yaml"))


def _rs(cycle, risk):
    return RegimeState(datetime.now(timezone.utc), cycle, risk)


def test_exposure_lower_in_recession_riskoff():
    imp = _imp()
    bull = imp.exposure_multiplier(_rs(CyclePhase.EXPANSION, RiskMode.RISK_ON))
    bear = imp.exposure_multiplier(_rs(CyclePhase.RECESSION, RiskMode.RISK_OFF))
    assert bull == 1.0 and bear < bull


def test_factor_tilts_riskoff_favours_quality():
    tilts = _imp().factor_tilts(_rs(CyclePhase.RECESSION, RiskMode.RISK_OFF))
    assert tilts.get("quality", 0) > 0 and tilts.get("momentum", 0) < 0


def test_class_tilts_on_inflation_surprise():
    tilts = _imp().class_tilts({"inflation": 1.5, "growth": 0.0})
    assert tilts.get("commodity", 0) > 0
