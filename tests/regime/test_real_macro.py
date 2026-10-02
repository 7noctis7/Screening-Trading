"""`real_macro_store` : ce que la porte de régime lit (0 % de couverture au 02/10).

Le module alimente `MacroRegimeClassifier`, donc l'exposition brute du portefeuille.
Ces tests épinglent :
  1. le VIX réel et le proxy d'activité (ISM ← momentum 6 mois du S&P) sont stockés ;
  2. le proxy est POINT-IN-TIME : la valeur datée `t` n'utilise que des clôtures ≤ `t` ;
  3. il est borné [35, 65] et linéaire au centre (+10 % sur 6 mois → 60) ;
  4. une clôture NaN est ignorée au lieu de faire planter le snapshot (CI 15/07) ;
  5. valeurs et dates de longueurs inégales s'alignent par la fin (sans IndexError) ;
  6. sans aucune donnée, `is_real` est False — l'appelant retombe sur le synthétique ;
  7. FRED : une série en panne n'empêche pas l'autre d'être chargée.
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.models import MacroObservation
from packages.regime import real_macro
from packages.regime.real_macro import real_macro_store

J0 = datetime(2025, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _store_jetable(monkeypatch):
    monkeypatch.setenv("QUANT_MACRO_DB", ":memory:")


def _dates(n: int) -> list[datetime]:
    return [J0 + timedelta(days=i) for i in range(n)]


def _ism(store, t: datetime) -> float | None:
    v = store.as_of("ISM", t)
    return None if v is None else v[1]


def test_vix_et_proxy_d_activite_sont_stockes():
    d = _dates(130)
    store, sources, reel = real_macro_store([20.0] * 130, d, [100.0] * 130, d)
    assert reel is True
    assert set(sources) == {"VIXCLS", "ISM"}
    assert store.as_of("VIXCLS", d[-1])[1] == 20.0
    assert _ism(store, d[-1]) == pytest.approx(50.0)       # S&P plat → neutre


def test_le_proxy_est_point_in_time_et_lineaire_au_centre():
    d = _dates(127)
    sp = [100.0] * 126 + [110.0]                            # +10 % sur 126 barres
    store, _, _ = real_macro_store([], [], sp, d)
    assert _ism(store, d[125]) is None                      # rien avant 126 barres
    assert _ism(store, d[126]) == pytest.approx(60.0)
    assert _ism(store, d[126] - timedelta(seconds=1)) is None   # inconnu avant


@pytest.mark.parametrize("fin, attendu", [(200.0, 65.0), (10.0, 35.0)])
def test_le_proxy_est_borne(fin, attendu):
    d = _dates(127)
    store, _, _ = real_macro_store([], [], [100.0] * 126 + [fin], d)
    assert _ism(store, d[126]) == pytest.approx(attendu)


def test_une_cloture_nan_est_ignoree_sans_planter():
    d = _dates(128)
    sp = [100.0] * 126 + [float("nan"), 105.0]
    store, _, reel = real_macro_store([], [], sp, d)
    assert reel is True
    assert _ism(store, d[127]) == pytest.approx(55.0)
    hist = store.history_as_of("ISM", d[-1])
    assert len(hist) == 1                                    # la barre NaN n'existe pas


def test_valeurs_et_dates_de_longueurs_differentes_s_alignent_par_la_fin():
    d = _dates(127)
    sp = [999.0] * 5 + [100.0] * 126 + [110.0]               # 5 de trop, en tête
    store, _, _ = real_macro_store([15.0] * 200, d[-3:], sp, d)
    assert _ism(store, d[126]) == pytest.approx(60.0)
    assert len(store.history_as_of("VIXCLS", d[-1])) == 3


def test_sans_aucune_donnee_rien_n_est_reel():
    store, sources, reel = real_macro_store([], [], [], [])
    assert reel is False and sources == {} and store.count() == 0


def test_fred_une_serie_en_panne_n_empeche_pas_l_autre(monkeypatch):
    class FredFactice:
        def __init__(self, cle):
            assert cle == "cle-test"

        def fetch(self, sid, vintages=True):
            if sid == "T10Y3M":
                raise ConnectionError("FRED muet")
            return [MacroObservation("UNRATE", J0, 4.1, J0 + timedelta(days=7))]

    monkeypatch.setattr("packages.regime.fred_provider.FredProvider", FredFactice)
    store, sources, _ = real_macro_store([], [], [], [], fred_key="cle-test")
    assert "UNRATE" in sources and "T10Y3M" not in sources
    assert store.as_of("UNRATE", J0 + timedelta(days=6)) is None   # publié le J+7
    assert store.as_of("UNRATE", J0 + timedelta(days=7))[1] == 4.1


def test_sans_cle_fred_aucun_appel_reseau(monkeypatch):
    def interdit(*a, **k):
        raise AssertionError("FRED appelé sans clé")
    monkeypatch.setattr("packages.regime.fred_provider.FredProvider", interdit)
    _, sources, _ = real_macro_store([], [], [], [], fred_key=None)
    assert sources == {}
    assert real_macro.__name__ == "packages.regime.real_macro"
