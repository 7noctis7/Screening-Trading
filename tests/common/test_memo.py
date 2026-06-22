import os

from packages.common import memo
from packages.common.memo import cached_stage, fingerprint


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(memo, "_DIR", tmp_path / "stages")
    monkeypatch.delenv("QUANT_STAGE_CACHE", raising=False)


def test_cache_hit_skips_recompute(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"v": 42}

    a = cached_stage("stage", [1.0, 2.0, 3.0], compute)
    b = cached_stage("stage", [1.0, 2.0, 3.0], compute)   # mêmes entrées → cache
    assert a == b == {"v": 42}
    assert calls["n"] == 1                                # compute appelé UNE seule fois


def test_input_change_recomputes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    cached_stage("s", [1, 2], compute)
    cached_stage("s", [1, 2, 3], compute)                 # entrée différente → recalcul
    assert calls["n"] == 2


def test_version_bump_invalidates(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return calls["n"]

    cached_stage("s", [1], compute, version="1")
    cached_stage("s", [1], compute, version="2")
    assert calls["n"] == 2


def test_disabled_always_computes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("QUANT_STAGE_CACHE", "0")
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return 1

    cached_stage("s", [1], compute)
    cached_stage("s", [1], compute)
    assert calls["n"] == 2                                # cache off → recompute à chaque fois


def test_only_latest_file_kept(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    cached_stage("uniq", [1], lambda: 1)
    cached_stage("uniq", [2], lambda: 2)                  # nouvelle empreinte
    files = list((tmp_path / "stages").glob("uniq-*.pkl"))
    assert len(files) == 1                                # un seul fichier conservé (disque borné)


def test_fingerprint_stable_and_distinct():
    assert fingerprint([1.0, 2.0]) == fingerprint([1.0, 2.0])
    assert fingerprint([1.0, 2.0]) != fingerprint([1.0, 2.1])
