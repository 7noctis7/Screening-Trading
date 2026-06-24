"""Tests du retry avec backoff (robustesse réseau broker)."""

import pytest

from packages.common.retry import retry


def test_success_first_try_no_sleep():
    calls = []
    out = retry(lambda: 42, sleep=lambda d: calls.append(d))
    assert out == 42 and calls == []


def test_succeeds_after_failures():
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise ConnectionError("timeout")
        return "ok"

    delays = []
    out = retry(flaky, attempts=3, base_delay=1.0, sleep=lambda d: delays.append(d))
    assert out == "ok" and state["n"] == 3
    assert delays == [1.0, 2.0]            # backoff exponentiel sur les 2 échecs


def test_raises_after_exhaustion():
    def always_fail():
        raise TimeoutError("nope")

    with pytest.raises(TimeoutError):
        retry(always_fail, attempts=3, sleep=lambda d: None)


def test_backoff_is_capped():
    delays = []
    state = {"n": 0}

    def fail4():
        state["n"] += 1
        if state["n"] < 5:
            raise ValueError("x")
        return 1

    retry(fail4, attempts=5, base_delay=10.0, max_delay=16.0,
          sleep=lambda d: delays.append(d))
    assert delays == [10.0, 16.0, 16.0, 16.0]   # borné à max_delay


def test_only_catches_declared_exceptions():
    with pytest.raises(KeyError):
        retry(lambda: (_ for _ in ()).throw(KeyError("k")),
              exceptions=(ValueError,), sleep=lambda d: None)
