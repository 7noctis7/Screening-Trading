from datetime import datetime, timezone
from packages.core.models import MacroObservation as MO
from packages.storage import MacroStore


def _d(s): return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _store():
    ms = MacroStore(":memory:")
    ms.upsert([
        MO("CPI", _d("2023-12-01"), 3.1, _d("2024-01-11")),
        MO("CPI", _d("2024-01-01"), 3.0, _d("2024-02-13")),   # 1er vintage
        MO("CPI", _d("2024-01-01"), 2.9, _d("2024-03-15")),   # révision
    ])
    return ms


def test_publication_lag_respected():
    # avant publication de janvier → on ne voit que décembre
    assert _store().as_of("CPI", _d("2024-02-05"))[1] == 3.1


def test_first_vintage():
    assert _store().as_of("CPI", _d("2024-02-20"))[1] == 3.0


def test_revision_applied_later():
    assert _store().as_of("CPI", _d("2024-04-01"))[1] == 2.9


def test_history_as_of_is_point_in_time():
    hist = _store().history_as_of("CPI", _d("2024-02-20"))
    vals = [v for _, v in hist]
    assert vals == [3.1, 3.0]   # janvier au 1er vintage, pas la révision future
