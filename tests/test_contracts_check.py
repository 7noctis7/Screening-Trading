from scripts.contracts_check import validate_rows


def test_valid_rows_pass():
    rows = [{"symbol": "AAPL", "date": "2026-06-20", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100}]
    assert validate_rows(rows) == []


def test_detects_integrity_violations():
    rows = [
        {"symbol": "X", "date": "2026-06-20", "open": 10, "high": 8, "low": 9, "close": 10, "volume": 1},   # high<low
        {"symbol": "Y", "date": "2026-06-20", "close": 0},                                                  # close<=0
        {"symbol": "Z", "date": "2026-06-20", "open": 5, "high": 6, "low": 4, "close": 5, "volume": -3},    # vol<0
        {"symbol": None, "date": None},                                                                      # clés manquantes
    ]
    v = validate_rows(rows)
    assert len(v) >= 4


def test_tolerates_missing_ohlc_fields():
    # seules les colonnes présentes sont contrôlées (close valide ici) → pas de violation
    rows = [{"symbol": "A", "ts": "2026-06-20", "close": 12.0}]
    assert validate_rows(rows) == []
