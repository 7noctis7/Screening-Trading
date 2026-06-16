import numpy as np
from datetime import datetime, timezone
from packages.ml import frac_diff, fracdiff_weights, FeatureBuilder


def test_fracdiff_d0_is_identity():
    assert np.allclose(fracdiff_weights(0.0), [1.0])
    x = np.arange(10.0)
    out = frac_diff(x, d=0.0)
    assert np.allclose(out, x)


def test_fracdiff_d1_is_difference():
    x = np.array([1.0, 3.0, 6.0, 10.0])
    out = frac_diff(x, d=1.0, thresh=1e-6)
    assert np.allclose(out[1:], np.diff(x))   # d=1 → diff entière


def test_feature_builder_is_point_in_time():
    from packages.storage import FeatureStore, MacroStore
    from packages.core.models import MacroObservation as MO
    fs = FeatureStore(":memory:")
    t1 = datetime(2024, 1, 10, tzinfo=timezone.utc)
    t2 = datetime(2024, 2, 10, tzinfo=timezone.utc)
    fs.write("AAPL", "1d", "rsi", [(t1, 30.0), (t2, 70.0)])
    ms = MacroStore(":memory:")
    ms.upsert([MO("VIXCLS", datetime(2023, 12, 1, tzinfo=timezone.utc), 15.0,
                  datetime(2024, 1, 5, tzinfo=timezone.utc)),
               MO("VIXCLS", datetime(2024, 1, 1, tzinfo=timezone.utc), 25.0,
                  datetime(2024, 2, 5, tzinfo=timezone.utc))])
    X, names = FeatureBuilder(fs, ms, macro_series=("VIXCLS",)).build("AAPL", "1d", [t1, t2])
    assert names == ["rsi", "macro_VIXCLS"]
    assert X[0, 0] == 30.0 and X[0, 1] == 15.0   # à t1, VIX connu = 15 (pas 25 futur)
    assert X[1, 1] == 25.0                        # à t2, VIX révélé = 25
