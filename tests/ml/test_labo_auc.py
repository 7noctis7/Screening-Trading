"""Banc des variantes pré-enregistrées : la mathématique sur synthétique (AGENTS.md,
règle 3). Aucun chiffre réel ici — le banc tourne sur le VPS (`make labo-auc`)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar
from packages.ml import labo_auc as lab
from packages.ml import variantes_auc as va
from packages.ml.edge_transversal import NOMS
from packages.ml.model import LogitModel

T0 = datetime(2018, 1, 1, tzinfo=UTC)


def _univers(n_titres=40, n_barres=900, persistance=0.0, graine=0):
    rng = np.random.default_rng(graine)
    data, secteurs = {}, {}
    for k in range(n_titres):
        r = rng.normal(persistance * rng.normal(), 0.02, n_barres)
        px = 100 * np.cumprod(1 + r)
        data[f"S{k:02d}"] = [Bar(f"S{k:02d}", "1d", T0 + timedelta(days=j), px[j],
                                 px[j] * 1.01, px[j] * 0.99, px[j], 1e6)
                             for j in range(n_barres)]
        secteurs[f"S{k:02d}"] = "tech" if k % 2 else "sante"
    return data, secteurs


@pytest.fixture(scope="module")
def jeu_plante():
    return va.construire(*_univers(persistance=0.002, graine=1))


def test_les_quatre_variantes_partagent_les_memes_lignes(jeu_plante):
    n = len(jeu_plante["R"])
    for v in va.VARIANTES:
        X, y = va.variante(v, jeu_plante)
        assert X.shape == (n, len(NOMS)) and y.shape == (n,)
        assert set(np.unique(y)) <= {0.0, 1.0}
    assert (np.diff(jeu_plante["T0"]) >= 0).all()


def test_rangs_bornes_dans_la_semaine(jeu_plante):
    Xr, _ = va.variante("V1_rangs", jeu_plante)
    assert np.nanmin(Xr) > 0 and np.nanmax(Xr) <= 1


def test_triple_barriere_haute_basse_et_echeance():
    c = np.array([100, 100, 103, 99, 98, 97], float)
    assert va.label_triple_barriere(c, 1, 4, 0.01, 0.0) == 1.0     # +3 % ≥ 2 %
    c2 = np.array([100, 100, 97, 103], float)
    assert va.label_triple_barriere(c2, 1, 2, 0.01, 0.0) == 0.0    # −3 % d'abord
    c3 = np.array([100, 100, 100.5, 100.4], float)
    assert va.label_triple_barriere(c3, 1, 2, 0.05, 0.001) == 1.0  # échéance > coût
    assert va.label_triple_barriere(c3, 1, 2, 0.05, 0.01) == 0.0


def test_le_t_se_calcule_sur_des_semaines_disjointes():
    ics = {w: 0.05 + 0.01 * (w % 2) for w in range(40)}
    r = lab.resume_ic(ics, pas=5)
    assert r["n_semaines"] == 40 and r["n_disjointes"] == 8


def test_decoupage_purge_la_frontiere(jeu_plante):
    dev, ecart = lab.decouper(jeu_plante)
    assert not (dev & ecart).any()
    frontiere = jeu_plante["T0"][ecart].min()
    assert (jeu_plante["T1"][dev] < frontiere).all()


def test_signal_plante_les_rangs_le_voient_hors_echantillon(jeu_plante):
    r = lab.evaluer_variante("V1_rangs", jeu_plante, lambda: LogitModel(epochs=200),
                             NOMS)
    assert r["auc_cv"] > 0.55 and r["ic_cv"]["ic"] > 0.05
    assert r["ic_ecart"]["ic"] > 0.05 and r["mda"][0]["mda"] > 0


def test_bruit_pur_aucune_variante_retenue():
    jeu = va.construire(*_univers(persistance=0.0, graine=2))
    res = lab.banc(jeu, lambda: LogitModel(epochs=150), NOMS)
    assert res["n_essais"] == 4 and res["retenues"] == []
    assert res["variantes"][0]["ecart_vs_v0_ic95"] is None


def test_le_script_ne_consigne_rien_en_synthetique_et_quatre_essais_en_reel(
        tmp_path, monkeypatch):
    from packages.research import ledger
    from scripts import labo_auc as script
    chemin = tmp_path / "h.jsonl"
    monkeypatch.setattr(ledger.append_record, "__defaults__", (chemin,))
    res = {"variantes": [{"variante": v, "retenue": False, "auc_cv": 0.51,
                          "ic_ecart": {"ic": 0.01, "t": 0.5},
                          "ecart_vs_v0_ic95": None} for v in va.VARIANTES]}
    assert script._consigner(res, "synthetic") == 0 and not chemin.exists()
    assert script._consigner(res, "réel") == 4
    recs = ledger.read_records(chemin)
    assert {r["facteur"] for r in recs} == {f"ml_edge:variante:{v}"
                                           for v in va.VARIANTES}
