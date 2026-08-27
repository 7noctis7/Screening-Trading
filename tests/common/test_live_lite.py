"""Mode léger d'exécution (QUANT_LIVE_LITE) : les sections coûteuses sont coupées,
mais uniquement quand le flag est actif, et jamais les sections essentielles au live."""

from packages.common.safe_section import safe_section


def _boom():
    raise RuntimeError("ne doit pas être appelé en lite")


def _ok():
    return {"available": True, "value": 42}


def test_lite_skips_heavy_section(monkeypatch):
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    r = safe_section("ml", _boom)                    # _boom PAS appelé → court-circuit
    assert r == {"available": False, "section": "ml", "skipped": "live-lite"}


def test_lite_keeps_essential_section(monkeypatch):
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    assert safe_section("screen", _ok)["value"] == 42     # screen = essentiel → exécuté
    assert safe_section("live", _ok)["value"] == 42


def test_no_lite_runs_everything(monkeypatch):
    monkeypatch.delenv("QUANT_LIVE_LITE", raising=False)
    assert safe_section("ml", _ok)["value"] == 42          # sans flag → exécuté


# ---------------------------------------------------------------------------
# `fundamentals` N'EST PLUS COUPÉE (27/08). Ce n'était pas une section
# « non essentielle » : elle DÉCIDE de l'univers.
#
# Mesuré en production, même capital, même minute :
#   mode léger   → « 0 scoré → repli MOMENTUM », régime 0.000, satellite VIDE
#   mode complet → 12 actions réelles (THC, UNP, TGT, TMO, T…), 75 720 $ alloués
#
# Sans score qualité, le repli prend le top-12 du momentum à 12 mois — par construction
# les douze titres les plus extrêmes de l'univers. L'indice de ce panier est presque
# toujours à plus de 15 % sous son pic, ce qui met la porte de RÉGIME à zéro. Le
# satellite actions était donc structurellement vide, sans rapport avec le marché.
# ---------------------------------------------------------------------------
def test_fundamentals_TOURNE_meme_en_mode_leger(monkeypatch):
    """Le correctif : la section qui décide de l'univers n'est plus court-circuitée."""
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    monkeypatch.delenv("QUANT_LIVE_LITE_SKIP_FUNDAMENTALS", raising=False)
    assert safe_section("fundamentals", _ok)["value"] == 42


def test_l_echappatoire_restaure_l_ancien_comportement(monkeypatch):
    """Retour arrière sans toucher au code, si la durée devenait inacceptable."""
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    monkeypatch.setenv("QUANT_LIVE_LITE_SKIP_FUNDAMENTALS", "1")
    r = safe_section("fundamentals", _boom)
    assert r["skipped"] == "live-lite"


def test_l_echappatoire_ne_fait_rien_hors_mode_leger(monkeypatch):
    """Une variable de repli ne doit pas couper une section quand le mode léger est
    OFF — sinon un réglage oublié désactiverait le score qualité en mode complet,
    en silence."""
    monkeypatch.delenv("QUANT_LIVE_LITE", raising=False)
    monkeypatch.setenv("QUANT_LIVE_LITE_SKIP_FUNDAMENTALS", "1")
    assert safe_section("fundamentals", _ok)["value"] == 42


def test_la_degradation_reste_gracieuse(monkeypatch):
    """L'argument qui rend le correctif sûr : si `fundamentals` ÉCHOUE (réseau, quota),
    `safe_section` l'isole et la sélection retombe sur le momentum — c'est-à-dire le
    comportement d'avant. Le pire cas du correctif est l'état antérieur."""
    monkeypatch.setenv("QUANT_LIVE_LITE", "1")
    r = safe_section("fundamentals", _boom)          # _boom EST appelé, et lève
    assert r["available"] is False
    assert "error" in r
