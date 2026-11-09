"""CHANGELOG généré et banc de vitesse : la mécanique, pas les chiffres.

Barres SYNTHÉTIQUES ici seulement : le mandat les autorise dans tests/ pour valider la
mécanique ; le banc lui-même ne lit que la base de prix réelle.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.data import data_providers
from scripts import changelog
from scripts.bench_moteur import MOTEURS, charge, chronometrer, main


def test_squash_et_merge_classique_donnent_le_titre_et_le_numero(monkeypatch):
    brut = ("2026-10-31\x1fCI : mypy bloquant (#455)\x1f\x1e"
            "2026-10-29\x1fMerge pull request #453 from x/feat\x1fFeat/vector rag\n\x1e"
            "2026-10-01\x1fchore: keepalive mensuel\x1f\x1e"
            "2026-09-30\x1fcommit direct sans PR\x1f\x1e")
    monkeypatch.setattr(changelog, "_git", lambda *a: brut)
    assert changelog.entrees("main") == [("2026-10-31", "CI : mypy bloquant", 455),
                                         ("2026-10-29", "Feat/vector rag", 453)]


def test_le_rendu_groupe_par_mois_dans_l_ordre_de_l_historique():
    texte = changelog.rendre([("2026-10-31", "B", 2), ("2026-09-30", "A", 1)], "0.1.0",
                             "2026-10-31")
    assert "## [0.1.0] — 2026-10-31" in texte
    assert texte.index("### 2026-10") < texte.index("### 2026-09")
    assert "- B (#2)" in texte and "- A (#1)" in texte


def _base_synthetique(chemin: Path, n: int, jours: int) -> None:
    f = data_providers.create("synthetic", seed=7, annual_vol=0.28, drift=0.08)
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with sqlite3.connect(chemin) as conn:
        conn.execute("CREATE TABLE prices (symbol TEXT, date TEXT, open REAL, high REAL, "
                     "low REAL, close REAL, adj_close REAL, volume REAL)")
        for i in range(n):
            for b in f.fetch_ohlcv(f"S{i}", "1d", t0, t0 + timedelta(days=jours)):
                conn.execute("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)",
                             (f"S{i}", b.ts.date().isoformat(), b.open, b.high, b.low,
                              b.close, b.close, b.volume))


def test_le_banc_lit_la_base_et_mesure_les_deux_moteurs(tmp_path):
    _base_synthetique(tmp_path / "market.db", 2, 400)
    data = charge(tmp_path / "market.db", 2, 1)
    assert data is not None and set(data) == {"S0", "S1"} and len(data["S0"]) >= 240
    for fn in MOTEURS.values():
        assert chronometrer(fn, data, 1) > 0


def test_sans_base_suffisante_le_banc_dit_uncalibrated(tmp_path, capsys):
    """Pas de base, ou trop peu de symboles : on ne mesure rien et on le dit."""
    assert charge(tmp_path / "absente.db", 2, 1) is None
    _base_synthetique(tmp_path / "market.db", 1, 400)
    assert charge(tmp_path / "market.db", 2, 1) is None
    main(["--db", str(tmp_path / "market.db"), "--actifs", "2", "--ans", "1"])
    assert "UNCALIBRATED" in capsys.readouterr().out
