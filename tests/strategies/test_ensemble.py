from packages.strategies.ensemble import combine_signals, discretize


def test_combine_weighted():
    c = combine_signals({"a": [1.0, -1.0], "b": [0.0, -1.0]}, {"a": 1, "b": 1})
    assert c == [0.5, -1.0]


def test_discretize_deadband():
    assert discretize([0.5, -0.5, 0.1], threshold=0.2) == [1, -1, 0]


def test_empty():
    assert combine_signals({}) == []
