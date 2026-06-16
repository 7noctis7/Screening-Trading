from packages.regime.fred_provider import parse_observations


def test_parser_maps_vintages_and_skips_missing():
    payload = {"observations": [
        {"date": "2024-01-01", "value": "3.0", "realtime_start": "2024-02-13"},
        {"date": "2024-02-01", "value": ".", "realtime_start": "2024-03-13"},  # manquant
        {"date": "2024-02-01", "value": "3.1", "realtime_start": "2024-03-13"},
    ]}
    obs = parse_observations(payload, "CPIAUCSL")
    assert len(obs) == 2  # la valeur '.' est ignorée
    assert obs[0].value == 3.0 and obs[0].realtime_start.year == 2024


def test_synthetic_has_publication_lag():
    from datetime import datetime, timezone
    from packages.regime import synthetic_macro
    obs = synthetic_macro(datetime(2023, 1, 1, tzinfo=timezone.utc), months=3)
    assert all(o.realtime_start > o.obs_date for o in obs)  # publié après la période
