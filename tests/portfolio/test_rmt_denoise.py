"""RMT : séparer les vrais facteurs du bruit, et le prouver sur une structure connue."""
import numpy as np

from packages.portfolio.rmt_denoise import (denoise_corr, denoise_covariance, detone,
                                            effective_rank, mp_edges,
                                            n_signal_eigenvalues)


def _factor_model(n=60, t=250, k=3, seed=0, load=0.6, positive=False):
    """n actifs = k facteurs communs + bruit idiosyncratique. Synthétique = tests SEULEMENT.

    `positive` : loadings tous positifs → un vrai « facteur marché » (corrélation moyenne > 0).
    Sinon les loadings changent de signe et la corrélation moyenne reste nulle.
    """
    rng = np.random.default_rng(seed)
    F = rng.normal(size=(k, t))
    B = rng.normal(scale=load, size=(n, k))
    if positive:
        B = np.abs(B)
    return B @ F + rng.normal(size=(n, t))


def test_bornes_marcenko_pastur():
    lo, hi = mp_edges(n=100, t=100)                 # q = 1 → support [0, 4]
    assert abs(lo) < 1e-12 and abs(hi - 4.0) < 1e-12
    lo2, hi2 = mp_edges(n=25, t=100)                # q = 0,25 → [0,25 ; 2,25]
    assert abs(lo2 - 0.25) < 1e-12 and abs(hi2 - 2.25) < 1e-12
    assert mp_edges(10, 1000)[1] < hi2              # plus d'observations → bulk plus étroit


def test_bruit_pur_ne_produit_aucun_facteur():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(50, 500))
    d = n_signal_eigenvalues(np.linalg.eigvalsh(np.corrcoef(X)), 50, 500)
    assert d["k_mp"] <= 1                           # aucune v.p. hors du support MP


def test_nombre_de_facteurs_retrouve():
    for k in (1, 3, 5):
        X = _factor_model(n=60, t=400, k=k, seed=k)
        d = n_signal_eigenvalues(np.linalg.eigvalsh(np.corrcoef(X)), 60, 400)
        assert d["k"] == k                          # l'écart spectral retrouve k exactement
        assert d["k_mp"] >= k                       # le seuil MP seul est une borne SUPÉRIEURE


def test_le_seuil_mp_seul_surdetecte_quand_les_facteurs_dominent():
    """Cinq facteurs forts absorbent la trace → bulk hétérogène → MP sur-détecte."""
    X = _factor_model(n=60, t=400, k=5, seed=5)
    d = n_signal_eigenvalues(np.linalg.eigvalsh(np.corrcoef(X)), 60, 400)
    assert d["k_mp"] > 5 and d["k"] == 5            # exactement le piège documenté


def test_debruitage_preserve_la_trace_et_ameliore_le_conditionnement():
    X = _factor_model(n=50, t=120, seed=7)          # q ≈ 0,42 : régime réellement bruité
    C = np.corrcoef(X)
    d = denoise_corr(C, t=120)
    assert d["available"]
    assert abs(np.trace(d["corr"]) - 50) < 1e-6     # trace préservée = variance conservée
    assert d["cond_after"] < d["cond_before"] / 2   # conditionnement franchement meilleur
    assert np.all(np.linalg.eigvalsh(d["corr"]) > -1e-9)   # reste semi-définie positive


def test_chaine_complete_et_verdict_honnete():
    ok = denoise_covariance(_factor_model(n=40, t=500, k=3, seed=3))
    assert ok["available"] and ok["verdict"] == "OK"
    assert ok["cond_after"] < ok["cond_before"]
    fragile = denoise_covariance(_factor_model(n=40, t=45, k=3, seed=4))
    assert fragile["q"] > 0.5 and fragile["verdict"].startswith("FRAGILE")


def test_detonage_retire_le_facteur_marche():
    X = _factor_model(n=40, t=400, k=1, load=1.2, seed=5, positive=True)
    C = np.corrcoef(X)
    hors_diag = lambda M: M[~np.eye(M.shape[0], dtype=bool)].mean()  # noqa: E731
    assert hors_diag(C) > 0.3
    assert hors_diag(detone(C, 1)) < hors_diag(C) / 2


def test_rang_effectif():
    assert abs(effective_rank([1.0] * 10) - 10.0) < 1e-9        # spectre plat = 10 directions
    assert effective_rank([100.0] + [0.01] * 9) < 1.5           # une seule direction portée
