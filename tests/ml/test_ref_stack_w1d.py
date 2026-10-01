"""Smoke: ref_stack_w1d calendrier ISO + 0 claim."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from packages.ml.ref_stack_w1d import (
    assert_campaign_constants,
    horizon_bars_to_htf_w,
    iso_week_end,
    last_completed_htf_w_idx,
)


def test_iso_week_end_sunday():
    # 2026-09-30 = mercredi → fin semaine ISO = 2026-10-04
    assert iso_week_end(datetime(2026, 9, 30)).date().isoformat() == "2026-10-04"


def test_horizon_bars_to_week_end():
    start = datetime(2026, 9, 28)  # lundi
    bars = [SimpleNamespace(ts=start + timedelta(days=i)) for i in range(7)]
    assert horizon_bars_to_htf_w(bars, 0) == 6


def test_last_completed_htf_pit():
    start = datetime(2026, 9, 21)  # lundi
    bars = [SimpleNamespace(ts=start + timedelta(days=i)) for i in range(14)]
    # signal mercredi semaine 2 (30 sep, index 9) → cutoff prev week end 27 sep
    idx = last_completed_htf_w_idx(bars, 9)
    assert idx is not None
    assert bars[idx].ts.date().isoformat() <= "2026-09-27"


def test_zero_claim_guard():
    with pytest.raises(AssertionError, match="0 claim"):
        assert_campaign_constants(claim=True)
