from datetime import datetime, timezone
from packages.core.models import EconomicRelease
from packages.regime import surprise_index


def _d(s): return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def test_themes_and_sign():
    rel = [EconomicRelease("CPIAUCSL", _d("2024-06-01"), 3.4, 3.1, 0.2),  # +1.5
           EconomicRelease("ISM", _d("2024-06-03"), 48, 50, 1.0)]          # -2.0
    s = surprise_index(rel, _d("2024-06-15"))
    assert s["inflation"] > 0 and s["growth"] < 0


def test_point_in_time_window():
    rel = [EconomicRelease("CPIAUCSL", _d("2024-06-01"), 3.4, 3.1, 0.2)]
    # release future non vue
    assert surprise_index(rel, _d("2024-05-15")) == {"overall": 0.0}
