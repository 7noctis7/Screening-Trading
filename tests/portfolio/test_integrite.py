"""Un NaN est un INCIDENT DE DONNÉES, jamais une valeur.

Constaté le 31/08 : la CI est passée du vert au rouge sur un code IDENTIQUE, avec
`assert nan <= nan` et `assert nan > 0`. Un téléchargement réseau incomplet avait
laissé un point non fini dans une courbe d'equity, et ce point s'est propagé en
silence jusqu'aux métriques publiées.

Aujourd'hui ça casse un test, donc on le voit. Demain ça peut publier un Sharpe à `nan`
que le front affiche « — » sans que personne ne sache qu'une donnée manquait. Une
métrique absente est un problème visible ; une métrique fausse ne l'est pas.
"""

import math

import pytest

from apps.api.payloads import benchmark_comparison, metrics_payload
from packages.portfolio.integrite import (
    diagnostiquer,
    exploitable,
    filtrer_finis,
    prefixe_fini,
    verdict,
)
from packages.portfolio.stress import mc_projection


def _serie(n=200):
    return [100.0 + k for k in range(n)]


# --------------------------------------------------------------- diagnostic
def test_serie_saine_est_declaree_saine():
    d = diagnostiquer(_serie())
    assert d["saine"] and d["n_non_finis"] == 0 and d["part_valide"] == 1.0


@pytest.mark.parametrize("mauvais", [float("nan"), float("inf"), float("-inf")])
def test_les_trois_formes_de_NON_FINI_sont_vues(mauvais):
    """`inf` est aussi destructeur qu'un `nan` : il traverse cumprod sans erreur."""
    d = diagnostiquer([1.0, mauvais, 3.0])
    assert d["n_non_finis"] == 1 and d["premier_non_fini"] == 1


def test_une_valeur_non_numerique_est_non_finie():
    assert diagnostiquer([1.0, None, "x"])["n_non_finis"] == 2


def test_serie_vide_ne_plante_pas():
    assert diagnostiquer([])["n"] == 0


# --------------------------------------------------------------- equity : TRONQUER
def test_une_courbe_d_equity_est_TRONQUEE_pas_filtree():
    """Après un trou la capitalisation est rompue. Recoller les deux morceaux
    fabriquerait un rendement qui n'a jamais existé — celui qui enjambe le trou."""
    g, d = prefixe_fini([100.0, 101.0, float("nan"), 103.0, 104.0])
    assert g == [100.0, 101.0] and d["tronquee"]


def test_courbe_saine_non_tronquee():
    g, d = prefixe_fini(_serie())
    assert len(g) == 200 and not d["tronquee"]


# --------------------------------------------------------------- rendements : FILTRER
def test_un_vivier_de_rendements_est_FILTRE_pas_tronque():
    """Un rendement inobservable n'appartient pas à l'échantillon dans lequel on tire.
    Une courbe est une séquence ; un vivier est un ensemble."""
    g, d = filtrer_finis([0.01, float("nan"), -0.02, float("inf"), 0.005])
    assert g == [0.01, -0.02, 0.005] and d["n_non_finis"] == 2


# --------------------------------------------------------------- exploitabilité
def test_beaucoup_de_points_mais_troues_nest_PAS_exploitable():
    d = diagnostiquer([1.0] * 800 + [float("nan")] * 200)
    d["n_conserves"] = 800
    assert not exploitable(d)


def test_peu_de_points_meme_parfaits_nest_PAS_exploitable():
    """Une part de 100 % sur dix points ne vaut rien : les deux conditions sont
    nécessaires, chacune rate le cas de l'autre."""
    d = diagnostiquer([1.0] * 10)
    d["n_conserves"] = 10
    assert not exploitable(d)


def test_le_verdict_explique_le_refus():
    d = diagnostiquer([1.0, float("nan")])
    d["n_conserves"] = 1
    assert "trop trouée" in verdict(d)["motif"]


# --------------------------------------------------------------- amplification MC
def test_UN_SEUL_NaN_ne_pollue_plus_toute_la_projection():
    """LE test. Le tirage se fait AVEC REMISE : un point sur 2000 apparaissait dans la
    quasi-totalité des trajectoires, et cumprod le propageait — les cinq percentiles
    sortaient à `nan`."""
    bons = [0.001 * ((-1) ** k) + 0.0004 for k in range(2000)]
    pollue = list(bons)
    pollue[137] = float("nan")
    r = mc_projection(pollue, horizon=60, n_sims=200, seed=1)
    assert not math.isnan(r["final_p50"])
    assert r["integrite"]["n_non_finis"] == 1


def test_la_projection_reste_IDENTIQUE_au_cas_sain():
    """Retirer un point sur 2000 ne doit pas déplacer le résultat de façon visible."""
    bons = [0.001 * ((-1) ** k) + 0.0004 for k in range(2000)]
    pollue = list(bons)
    pollue[137] = float("nan")
    a = mc_projection(bons, horizon=60, n_sims=200, seed=1)["final_p50"]
    b = mc_projection(pollue, horizon=60, n_sims=200, seed=1)["final_p50"]
    assert abs(a - b) / a < 0.02


def test_vivier_entierement_pollue_rend_la_structure_VIDE():
    """Plutôt qu'un `nan` déguisé en chiffre."""
    r = mc_projection([float("nan")] * 500, horizon=60, n_sims=50, seed=1)
    assert r["p50"] == [] and r["integrite"]["n_non_finis"] == 500


# --------------------------------------------------------------- payloads
def test_les_metriques_ne_sortent_plus_a_NaN():
    eq = _serie() + [float("nan"), 400.0]
    m = metrics_payload(eq)
    assert not math.isnan(m["sharpe"])
    assert m["integrite"]["tronquee"]


def test_les_benchmarks_restent_ALIGNES_apres_troncature():
    """Tronquer la seule série fautive désalignerait le graphe : les points ne
    correspondraient plus aux mêmes dates, et la comparaison deviendrait fausse tout en
    restant lisible — le pire des cas."""
    eq = _serie() + [float("nan"), 400.0]
    b = benchmark_comparison(eq, {"Indice": [50.0 + k for k in range(202)]})
    assert len(b["portfolio"]) == len(b["Indice"]) == 200
    assert all(math.isfinite(v) for v in b["portfolio"])


def test_les_benchmarks_ne_recoivent_AUCUNE_cle_non_serie():
    """Le front type ce dictionnaire en Record<string, Point[]> et itère dessus : une
    clé de diagnostic y casserait le graphe."""
    b = benchmark_comparison(_serie(), {"Indice": _serie()})
    assert all(isinstance(v, list) for v in b.values())


def test_une_serie_saine_traverse_sans_modification():
    """Non-régression : le garde ne doit rien changer quand tout va bien."""
    b = benchmark_comparison(_serie(), {"Indice": _serie()})
    assert len(b["portfolio"]) == 200
    assert not metrics_payload(_serie())["integrite"]["tronquee"]


# ------------------------------------------- le type RÉEL passé par les appelants
# `x or []` teste la vérité de l'objet. Sur un `np.ndarray` de plus d'un élément,
# Python lève « truth value of an array is ambiguous » AVANT toute analyse. Or
# `returns_from_equity` renvoie un ndarray, et `snapshot.py` le passe directement à
# `mc_projection` : le garde d'intégrité tombait donc sur EXACTEMENT le chemin qu'il
# était censé protéger. Le coût en CI était double — 9 tests rouges, et la suite passée
# de 7 à 38 minutes parce que `lru_cache` ne mémorise pas une exception : chaque test
# reconstruisait le snapshot entier.
def test_un_ndarray_traverse_le_diagnostic():
    np = pytest.importorskip("numpy")
    d = diagnostiquer(np.array([1.0, 2.0, float("nan"), 4.0]))
    assert d["n"] == 4 and d["n_non_finis"] == 1 and d["premier_non_fini"] == 2


def test_un_ndarray_traverse_troncature_et_filtrage():
    np = pytest.importorskip("numpy")
    a = np.array([1.0, 2.0, float("nan"), 4.0])
    assert prefixe_fini(a)[0] == [1.0, 2.0]
    assert filtrer_finis(a)[0] == [1.0, 2.0, 4.0]


def test_mc_projection_accepte_le_ndarray_de_returns_from_equity():
    """Le chemin exact de `snapshot.py` : equity -> returns_from_equity -> mc."""
    np = pytest.importorskip("numpy")
    from packages.portfolio.metrics import returns_from_equity
    rets = returns_from_equity(np.asarray(_serie(300), float))
    assert isinstance(rets, np.ndarray)
    out = mc_projection(rets, horizon=20, n_sims=50, seed=1)
    assert out["p50"] and math.isfinite(out["final_p50"])


def test_les_payloads_acceptent_le_ndarray():
    np = pytest.importorskip("numpy")
    eq = np.asarray(_serie(), float)
    assert not math.isnan(metrics_payload(eq)["sharpe"])
    b = benchmark_comparison(eq, {"Indice": np.asarray(_serie(), float)})
    assert len(b["Indice"]) == 200


def test_une_serie_vide_ou_absente_ne_leve_pas():
    """`None` et le tableau vide sont des séries légitimes, pas des erreurs."""
    np = pytest.importorskip("numpy")
    for vide in (None, [], np.array([])):
        assert diagnostiquer(vide)["n"] == 0
        assert prefixe_fini(vide)[0] == [] and filtrer_finis(vide)[0] == []
