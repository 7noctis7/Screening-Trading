from scripts.kpi_to_supabase import build_row


def test_build_row_keeps_present_numeric_fields():
    row = build_row({"total_return": 1.21, "sharpe": 0.51, "max_drawdown": -0.25, "n": 0},
                    {"p_ruin": 0.03}, date="2026-06-22")
    assert row["date"] == "2026-06-22"
    assert row["total_return"] == 1.21 and row["sharpe"] == 0.51
    assert row["max_drawdown"] == -0.25 and row["p_ruin"] == 0.03
    assert "n" not in row              # champ hors whitelist ignoré


def test_build_row_drops_none_and_nan():
    row = build_row({"sharpe": None, "sortino": float("nan"), "calmar": 0.2}, date="2026-06-22")
    assert "sharpe" not in row and "sortino" not in row
    assert row["calmar"] == 0.2


def test_build_row_defaults_date():
    row = build_row({"sharpe": 1.0})
    assert "date" in row and len(row["date"]) == 10
