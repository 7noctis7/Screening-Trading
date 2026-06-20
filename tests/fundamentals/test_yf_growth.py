"""Croissance YoY calculée depuis les états financiers réels (formule (N−N-1)/N-1)."""

import pandas as pd

from packages.fundamentals.yfinance_provider import _yoy_row


def test_yoy_annual():
    df = pd.DataFrame({"2024": [125, 20], "2023": [100, 16]}, index=["Total Revenue", "Net Income"])[["2024", "2023"]]
    assert abs(_yoy_row(df, "Total Revenue") - 0.25) < 1e-9
    assert abs(_yoy_row(df, "Net Income") - 0.25) < 1e-9


def test_yoy_quarterly_lag4():
    # colonnes = 5 trimestres (plus récent d'abord) → compare T0 vs T-4 (même trimestre N-1)
    cols = ["Q4-24", "Q3-24", "Q2-24", "Q1-24", "Q4-23"]
    df = pd.DataFrame({c: [v] for c, v in zip(cols, [110, 90, 95, 80, 100])}, index=["Total Revenue"])[cols]
    assert abs(_yoy_row(df, "Total Revenue", lag=4) - 0.10) < 1e-9    # (110-100)/100


def test_yoy_guards():
    assert _yoy_row(None, "Total Revenue") is None
    df = pd.DataFrame({"a": [10]}, index=["Total Revenue"])
    assert _yoy_row(df, "Total Revenue") is None                      # une seule colonne
    assert _yoy_row(df, "Absent") is None
