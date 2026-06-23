"""Tests de l'isolation des fautes par section (antifragilité du snapshot)."""

from packages.common.safe_section import safe_section


def test_safe_section_passes_through_on_success():
    out = safe_section("ok", lambda x: {"available": True, "x": x}, 42)
    assert out == {"available": True, "x": 42}


def test_safe_section_catches_and_returns_fallback():
    def boom():
        raise ValueError("explosion")

    out = safe_section("macro", boom)
    assert out["available"] is False
    assert out["section"] == "macro"
    assert "ValueError" in out["error"] and "explosion" in out["error"]


def test_safe_section_isolates_one_failure_among_many():
    """Une section qui plante n'empêche pas les autres de produire (cas snapshot)."""
    sections = {
        "a": safe_section("a", lambda: {"available": True, "v": 1}),
        "b": safe_section("b", lambda: (_ for _ in ()).throw(RuntimeError("KO"))),
        "c": safe_section("c", lambda: {"available": True, "v": 3}),
    }
    assert sections["a"]["available"] and sections["c"]["available"]
    assert sections["b"]["available"] is False        # isolée, pas propagée
    assert len(sections) == 3                          # toutes les sections présentes
