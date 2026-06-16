from datetime import datetime, timezone
from packages.common import due_for_rebuild

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_no_snapshot_is_due():
    assert due_for_rebuild(None, 30, NOW) is True


def test_recent_not_due():
    assert due_for_rebuild("2026-02-19", 30, NOW) is False  # 10 jours


def test_old_is_due():
    assert due_for_rebuild("2026-01-25", 30, NOW) is True   # 35 jours


def test_bad_date_is_due():
    assert due_for_rebuild("not-a-date", 30, NOW) is True
