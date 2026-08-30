from apps.api.snapshot import _account_compare


def test_benchmarks_sont_alignes_sur_leurs_dates_reelles():
    account = [
        {"t": "2026-08-25", "v": 100.0},
        {"t": "2026-08-26", "v": 101.0},
        {"t": "2026-08-27", "v": 102.0},
        {"t": "2026-08-28", "v": 103.0},
    ]
    dates = ["2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    out = _account_compare(
        account, [], [100, 102, 101, 104], [200, 204, 202, 208], dates, dates
    )
    sp = out["series"]["S&P 500"]
    ndx = out["series"]["Nasdaq 100"]
    assert [p["v"] for p in sp] == [100.0, 102.0, 101.0, 104.0]
    assert [p["v"] for p in ndx] == [100.0, 102.0, 101.0, 104.0]
    assert out["kpis"][1]["return"] == 0.04
