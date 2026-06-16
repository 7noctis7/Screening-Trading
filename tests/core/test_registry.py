"""Le test de validation de l'architecture : ajouter un plugin = un fichier,
sans toucher au cœur."""

import pytest

from packages.core.registry import Registry


class _Strategy:  # stand-in pour l'interface Strategy
    pass


def test_register_and_create():
    reg: Registry[_Strategy] = Registry("strategy")

    @reg.register("dummy")
    class Dummy(_Strategy):
        def __init__(self, fast: int = 10):
            self.fast = fast

    assert "dummy" in reg
    obj = reg.create("dummy", fast=42)
    assert isinstance(obj, Dummy)
    assert obj.fast == 42


def test_unknown_raises():
    reg: Registry[_Strategy] = Registry("strategy")
    with pytest.raises(KeyError):
        reg.get("nope")


def test_duplicate_raises():
    reg: Registry[_Strategy] = Registry("strategy")

    @reg.register("a")
    class A(_Strategy):
        pass

    with pytest.raises(ValueError):
        @reg.register("a")
        class B(_Strategy):
            pass
