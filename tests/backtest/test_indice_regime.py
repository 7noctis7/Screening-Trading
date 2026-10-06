"""QML-009(a) : la porte de régime peut lire un indice de MARCHÉ, pas son panier.

Ce qui est épinglé :
  1. sans drapeau, la production est inchangée au chiffre près (et rien n'est noté) ;
  2. avec drapeau, un marché en krach coupe l'exposition même si le panier monte ;
  3. l'indice est point-in-time : report du dernier cours connu, jamais vers l'arrière ;
  4. une série absente ou trouée retombe sur le panier, et le diagnostic le dit.
"""

import numpy as np
import pytest

from packages.backtest import indice_regime as ir
from packages.backtest.preset_diag import Diag
from packages.backtest.preset_weights import preset_latest_weights_explique
from tests.backtest.test_preset_diag import Bar, _panier


def _indice(data: dict, fin: float) -> list:
    """Indice au calendrier du panier : plat, puis `fin` (relatif) sur 10 barres."""
    ref = data["S00"]
    n = len(ref)
    px = np.ones(n) * 100.0
    px[-10:] = 100.0 * (1 + fin)
    return [Bar(b.ts, *(4 * [float(px[i])]), 1e6) for i, b in enumerate(ref)]


@pytest.fixture(autouse=True)
def _sans_drapeau(monkeypatch):
    monkeypatch.delenv(ir.ENV, raising=False)


def _poids(data, monkeypatch, drapeau=None):
    if drapeau:
        monkeypatch.setenv(ir.ENV, drapeau)
    else:
        monkeypatch.delenv(ir.ENV, raising=False)
    return preset_latest_weights_explique(data, {}, top_k=12)


def test_sans_drapeau_la_production_est_inchangee(monkeypatch):
    data = _panier(seed=1)
    data["IDX"] = _indice(data, fin=-0.30)
    p0, d0 = _poids(data, monkeypatch)
    p1, _ = preset_latest_weights_explique(data, {}, top_k=12)
    assert p0 == p1 and p0
    assert not any(e == "indice de régime" for e, _ in d0.etapes)


def test_avec_drapeau_un_krach_de_marche_coupe_l_exposition(monkeypatch):
    data = _panier(seed=1)
    data["IDX"] = _indice(data, fin=-0.30)          # marché −30 % : sous le seuil dur
    sans, _ = _poids(data, monkeypatch)
    avec, d = _poids(data, monkeypatch, drapeau="idx")
    assert sum(sans.values()) > 0
    assert avec == {} and d.gross["régime"] == 0.0
    assert any("IDX (exogène" in det for _, det in d.etapes)


def test_marche_sain_exposition_preservee(monkeypatch):
    data = _panier(seed=1)
    data["IDX"] = _indice(data, fin=0.05)
    avec, d = _poids(data, monkeypatch, drapeau="IDX")
    assert sum(avec.values()) > 0 and d.gross["régime"] > 0


def test_point_in_time_report_du_dernier_cours_jamais_vers_l_arriere():
    data = _panier(n_titres=1, n_barres=40)
    barres = data["S00"]
    dates = [b.ts.date().isoformat() for b in barres]
    idx = [Bar(b.ts, 10.0 + i, 10.0 + i, 10.0 + i, 10.0 + i, 1.0)
           for i, b in enumerate(barres) if i != 20]          # un jour manquant
    out = ir.indice_exogene({"X": idx}, dates, "X")
    assert out[20] == out[19] == 29.0                          # report du 19, pas du 21
    tardif = [Bar(b.ts, 5.0, 5.0, 5.0, 5.0, 1.0) for b in barres[5:]]
    assert ir.indice_exogene({"X": tardif}, dates, "X") is None   # commence trop tard


def test_serie_absente_ou_trouee_retombe_sur_le_panier_et_le_dit():
    data = _panier(n_titres=3, n_barres=60)
    dates = [b.ts.date().isoformat() for b in data["S00"]]
    A = np.array([[b.close for b in data[s]] for s in sorted(data)])
    d = Diag()
    trouee = [b for i, b in enumerate(data["S00"]) if i % 10]   # 10 % de trous
    data["T"] = [Bar(b.ts, *(4 * [1.0]), 1.0) for b in trouee]
    mkt = ir.choisir_indice(data, dates, A, d, symbole="T")
    from packages.backtest.preset_helpers import indice_marche
    assert np.allclose(mkt, indice_marche(A))
    assert any("panier équipondéré" in det for _, det in d.etapes)
    assert ir.choisir_indice(data, dates, A, Diag(), symbole="ABSENT") is not None
