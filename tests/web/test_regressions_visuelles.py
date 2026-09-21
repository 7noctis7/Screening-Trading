"""Contrats source des trois éléments visuels réclamés sur le terminal."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_l_intro_rejoue_quand_on_revient_a_l_accueil():
    config = (ROOT / "apps/web/components/intro/introConfig.ts").read_text()
    assert 'INTRO_SESSION_POLICY: "session" | "day" | "always" | "never" = "always"' in config


def test_le_dashboard_publie_le_cac40_reel():
    snapshot = (ROOT / "apps/api/snapshot.py").read_text()
    assert '"CAC 40": (cac, _cac_dates if _cac_real else [])' in snapshot


def test_positions_affiche_le_pnl_realise():
    page = (ROOT / "apps/web/app/positions/page.tsx").read_text()
    api = (ROOT / "apps/api/main.py").read_text()
    assert 'label="Gain / perte réalisé"' in page
    assert '"realized": realized' in api
