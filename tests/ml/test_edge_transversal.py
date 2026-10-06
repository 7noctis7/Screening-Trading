"""Modèle d'edge transversal : le label, la clé d'artefact et l'extraction du snapshot.

Ce qui est épinglé (revue E[Gain] du 06/10) :
  1. le label est RELATIF : une semaine où tout monte ne fabrique pas de gagnants, une
     semaine où tout baisse n'en supprime pas — le bêta du marché n'est plus appris ;
  2. il est NET DE FRAIS : battre la médiane de moins que l'aller-retour ne compte pas ;
  3. la clé de l'artefact change avec la définition des features ou du label ;
  4. les features à la date t ne lisent aucune clôture postérieure à t ;
  5. la section publiée garde ses clés et déclare `frais_inclus: True`.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.ml import artifact
from packages.ml import edge_transversal as et
from tests.backtest.test_preset_diag import Bar

LUNDI = datetime(2024, 1, 1).toordinal()          # 1er janvier 2024 : un lundi


def test_tout_monte_ou_tout_baisse_meme_proportion_de_gagnants():
    rng = np.random.default_rng(0)
    idio = rng.normal(0, 0.03, 200)
    R = np.concatenate([0.10 + idio, -0.10 + idio])     # semaine en hausse puis baisse
    T0 = np.array([LUNDI] * 200 + [LUNDI + 7] * 200)
    y = et.labels_relatifs(R, T0, cout=0.0)
    assert y[:200].mean() == pytest.approx(y[200:].mean())
    assert 0.4 < y.mean() < 0.6                    # ≈ la moitié bat la médiane


def test_net_de_frais_battre_la_mediane_de_peu_ne_compte_pas():
    R = np.array([0.000, 0.001, 0.002, 0.050])
    T0 = np.array([LUNDI, LUNDI + 1, LUNDI + 2, LUNDI + 4])    # même semaine
    med = np.median(R)
    assert list(et.labels_relatifs(R, T0, cout=0.0)) == [0, 0, 1, 1]
    assert list(et.labels_relatifs(R, T0, cout=0.01)) == [0, 0, 0, 1]
    assert med == pytest.approx(0.0015)


def test_le_cout_vient_du_bareme_unique():
    from packages.execution.costs import CostModel
    attendu = CostModel.for_asset_class("equity").round_trip_bps / 1e4
    assert et.cout_aller_retour() == pytest.approx(attendu) and attendu > 0


def test_la_cle_d_artefact_suit_la_definition(monkeypatch):
    X, T1 = np.zeros((10, len(et.NOMS))), np.arange(10)
    avant = et.signature(X, T1, {"A": []})
    monkeypatch.setattr(et, "VERSION_FEATURES", "autre-definition")
    assert et.signature(X, T1, {"A": []}) != avant


def _barres(n: int, seed: int, drift: float = 0.0004) -> list:
    rng = np.random.default_rng(seed)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    px = 100 * np.cumprod(1 + rng.normal(drift, 0.015, n))
    return [Bar(t0 + timedelta(days=j), px[j], px[j] * 1.01, px[j] * 0.99, px[j], 1e6)
            for j in range(n)]


def test_features_point_in_time():
    b = _barres(400, seed=3)
    futur = b[:300] + _barres(100, seed=99, drift=0.05)        # futur réécrit
    lignes_a, _ = et._serie(b, et.H)
    lignes_b, _ = et._serie(futur, et.H)
    t_max = 300 - 1                                            # dernière date commune
    dates = range(60, 400, et.PAS)
    fa = [r[0] for r, t in zip(lignes_a, dates, strict=False) if t <= t_max]
    fb = [r[0] for r, t in zip(lignes_b, dates, strict=False) if t <= t_max]
    assert fa == fb


@pytest.fixture
def univers(monkeypatch, tmp_path):
    monkeypatch.setattr(artifact, "_DIR", tmp_path)
    return {f"S{i:02d}": _barres(320, seed=i, drift=0.0002 * (i % 5))
            for i in range(25)}


def test_section_publiee_garde_ses_cles_et_declare_les_frais(univers):
    out = et.section_ml(univers, {}, {})
    assert out["available"] is True
    assert out["contrat"]["frais_inclus"] is True
    assert {"auc", "edge_ok", "scores", "calibration", "walk_forward", "meta_labeling",
            "drift", "training_history", "artifact_metrics"} <= set(out)
    assert len(out["scores"]) == 25
    assert out["edge_ok"] is False          # sans distribution nulle : jamais « edge »


def test_le_snapshot_et_make_train_appellent_le_meme_code():
    from apps.api import snapshot
    assert snapshot._ml_section is et.section_ml


def test_trop_peu_de_donnees_indisponible():
    assert et.section_ml({"A": _barres(100, seed=1)}, {}, {}) == {"available": False}


def test_le_label_part_du_prix_d_execution():
    b = _barres(300, seed=5)
    lignes, _ = et._serie(b, et.H)
    c = [x.close for x in b]
    r0 = lignes[0][1]                                   # premier échantillon : t = 60
    assert r0 == pytest.approx(c[61 + et.H] / c[61] - 1)
    assert r0 != pytest.approx(c[60 + et.H] / c[60] - 1)
