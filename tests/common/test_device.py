"""Le matériel se détecte, il ne se code pas en dur.

Le projet se développe sur Mac (MPS) et migre sur NVIDIA (CUDA). Un `.to("mps")` écrit
dans un module de calcul marche sur un poste et casse sur l'autre — des semaines
plus tard, loin de la ligne fautive. Toute la logique matérielle vit donc dans
`packages/common/device.py`, et ce fichier la garde.

Ni `torch` ni `xgboost` ne sont installés là où cette suite tourne : c'est une
CONTRAINTE UTILE, pas une gêne. Elle force à vérifier ce qui compte — qu'une
bibliothèque optionnelle absente ne casse rien, et que le repli est explicite.
Les cas GPU sont joués avec de faux modules : on ne peut pas invoquer une carte
NVIDIA en CI, mais on peut vérifier qu'on lui parlerait correctement.
"""

from __future__ import annotations

import sys
import types

import pytest

from packages.common import device as dev


@pytest.fixture(autouse=True)
def _cache_propre(monkeypatch):
    """`get_optimal_device` est mis en cache : sans purge, le premier test fige tous
    les suivants et ils passeraient au vert sans rien vérifier."""
    dev.get_optimal_device.cache_clear()
    monkeypatch.delenv("QUANT_DEVICE", raising=False)
    yield
    dev.get_optimal_device.cache_clear()


def _faux_torch(cuda: bool, mps: bool | None):
    """Un `torch` minimal. `mps=None` simule torch < 1.12, où `backends.mps`
    n'existe pas."""
    t = types.ModuleType("torch")
    t.cuda = types.SimpleNamespace(is_available=lambda: cuda)
    t.backends = types.SimpleNamespace()
    if mps is not None:
        t.backends.mps = types.SimpleNamespace(is_available=lambda: mps)
    t.device = lambda nom: f"device({nom})"
    return t


def _avec_torch(monkeypatch, t):
    monkeypatch.setattr(dev, "_torch", lambda: t)


# --------------------------------------------------------------------------- détection

def test_sans_torch_on_tombe_sur_le_processeur(monkeypatch):
    """Cas de la CI et d'un Mac nu. Doit rendre « cpu », jamais lever."""
    _avec_torch(monkeypatch, None)
    assert dev.get_optimal_device() == "cpu"


def test_cuda_est_prioritaire_sur_mps(monkeypatch):
    """La machine cible d'abord : si les deux répondent, on prend CUDA."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=True))
    assert dev.get_optimal_device() == "cuda"


def test_mps_quand_il_n_y_a_pas_de_cuda(monkeypatch):
    """Le poste de développement Apple Silicon."""
    _avec_torch(monkeypatch, _faux_torch(cuda=False, mps=True))
    assert dev.get_optimal_device() == "mps"


def test_torch_ancien_sans_backends_mps(monkeypatch):
    """torch < 1.12 n'a pas `backends.mps` : un accès direct lèverait AttributeError."""
    _avec_torch(monkeypatch, _faux_torch(cuda=False, mps=None))
    assert dev.get_optimal_device() == "cpu"


def test_un_pilote_cassé_ne_fait_pas_planter(monkeypatch):
    """`is_available()` peut lever quand le pilote NVIDIA est mal installé. On veut un
    repli, pas une pile d'appels au milieu d'un entraînement de nuit."""
    t = _faux_torch(cuda=False, mps=False)

    def _casse():
        raise RuntimeError("pilote CUDA introuvable")

    t.cuda = types.SimpleNamespace(is_available=_casse)
    _avec_torch(monkeypatch, t)
    assert dev.get_optimal_device() == "cpu"


def test_la_variable_d_environnement_force_le_choix(monkeypatch):
    """Indispensable pour comparer deux matériels sur la même machine."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=True))
    monkeypatch.setenv("QUANT_DEVICE", "cpu")
    assert dev.get_optimal_device() == "cpu"


def test_une_valeur_d_environnement_absurde_est_ignoree(monkeypatch):
    """`QUANT_DEVICE=tpu` ne doit pas se propager jusqu'à `torch.device("tpu")`."""
    _avec_torch(monkeypatch, _faux_torch(cuda=False, mps=True))
    monkeypatch.setenv("QUANT_DEVICE", "tpu")
    assert dev.get_optimal_device() == "mps"


# ------------------------------------------------------------------------------ torch

def test_torch_device_explique_l_absence_de_torch(monkeypatch):
    """Message actionnable plutôt qu'un `NoneType` deux fonctions plus loin."""
    _avec_torch(monkeypatch, None)
    with pytest.raises(RuntimeError, match="torch n'est pas installé"):
        dev.torch_device()


def test_index_pour_les_pipelines_huggingface(monkeypatch):
    """`transformers.pipeline` attend un entier : 0 = accélérateur, -1 = processeur."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    assert dev.device_index() == 0
    dev.get_optimal_device.cache_clear()
    _avec_torch(monkeypatch, None)
    assert dev.device_index() == -1


# ------------------------------------------------------------------------ arbres (GPU)

def test_xgboost_sur_processeur_ne_demande_aucun_gpu(monkeypatch):
    _avec_torch(monkeypatch, None)
    assert dev.params_arbres("xgboost") == {"tree_method": "hist"}


def test_xgboost_2_utilise_device_cuda(monkeypatch):
    """XGBoost 2.0 a remplacé `gpu_hist` par `tree_method=hist` + `device=cuda`."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    faux = types.ModuleType("xgboost")
    faux.__version__ = "2.1.3"
    monkeypatch.setitem(sys.modules, "xgboost", faux)
    assert dev.params_arbres("xgboost") == {"tree_method": "hist", "device": "cuda"}


def test_xgboost_1_garde_gpu_hist(monkeypatch):
    """Sur XGBoost 1.x, `device=` est ignoré EN SILENCE : la machine à 10 000 €
    tournerait sur processeur sans un message. On lit la version au lieu de parier."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    faux = types.ModuleType("xgboost")
    faux.__version__ = "1.7.6"
    monkeypatch.setitem(sys.modules, "xgboost", faux)
    assert dev.params_arbres("xgboost")["tree_method"] == "gpu_hist"


def test_catboost_bascule_de_cpu_a_gpu(monkeypatch):
    _avec_torch(monkeypatch, None)
    assert dev.params_arbres("catboost") == {"task_type": "CPU"}
    dev.get_optimal_device.cache_clear()
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    assert dev.params_arbres("catboost") == {"task_type": "GPU"}


def test_lightgbm_ne_demande_le_gpu_que_si_le_binaire_le_sait(monkeypatch):
    """`pip install lightgbm` livre une version SANS GPU. Demander `device_type=gpu`
    dessus lève à l'entraînement — on sonde donc le binaire avant de le réclamer."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    monkeypatch.setattr(dev, "_lightgbm_gpu", lambda: False)
    assert dev.params_arbres("lightgbm") == {}
    monkeypatch.setattr(dev, "_lightgbm_gpu", lambda: True)
    assert dev.params_arbres("lightgbm") == {"device_type": "gpu"}


def test_bibliotheque_inconnue_leve(monkeypatch):
    _avec_torch(monkeypatch, None)
    with pytest.raises(ValueError, match="inconnue"):
        dev.params_arbres("random_forest")


# ------------------------------------------------------------------------------ pandas

@pytest.fixture(autouse=True)
def _crochet_cudf_vierge():
    """`activer_cudf` mémorise sa tentative : le crochet ne se pose utilement qu'une
    fois. Cette mémoire est un état de MODULE — sans remise à zéro, le premier test à
    l'appeler rendrait tous les suivants muets, et leur résultat dépendrait de l'ordre
    d'exécution. Constaté : la suite entière passait, sauf lancée en bloc."""
    dev._CUDF_TENTE, dev._CUDF_ACTIF = False, False
    yield
    dev._CUDF_TENTE, dev._CUDF_ACTIF = False, False


def test_cudf_refuse_de_s_activer_trop_tard(monkeypatch, capsys):
    """LE piège de RAPIDS : `cudf.pandas` est un crochet d'importation, pas un module de
    remplacement. Posé après l'entrée de pandas en mémoire, il ne fait plus rien ET ne
    lève rien — on se croit sur GPU en tournant sur processeur. Il faut donc le DIRE."""
    monkeypatch.setitem(sys.modules, "pandas", types.ModuleType("pandas"))
    assert dev.activer_cudf() is False
    assert "pandas est déjà importé" in capsys.readouterr().err


def test_cudf_absent_se_replie_en_silence(monkeypatch):
    """Cas du Mac : pas de cudf, pandas reste pandas, aucun bruit."""
    monkeypatch.delitem(sys.modules, "pandas", raising=False)
    monkeypatch.setitem(sys.modules, "cudf", None)   # import lèvera
    assert dev.activer_cudf() is False


# ---------------------------------------------------------------------------- bannière

def test_la_banniere_annonce_le_materiel(monkeypatch):
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    assert dev.banniere(force=True).startswith("Exécution sur : CUDA")


def test_la_banniere_dit_qu_un_choix_est_force(monkeypatch):
    """Sinon on cherche pendant une heure pourquoi le GPU « n'est pas détecté »."""
    _avec_torch(monkeypatch, _faux_torch(cuda=True, mps=False))
    monkeypatch.setenv("QUANT_DEVICE", "cpu")
    assert "forcé par QUANT_DEVICE" in dev.banniere(force=True)


def test_la_banniere_previent_que_le_processeur_sera_lent(monkeypatch):
    _avec_torch(monkeypatch, None)
    assert "aucun GPU détecté" in dev.banniere(force=True)


def test_activer_cudf_ne_se_plaint_que_du_premier_appel() -> None:
    """Le crochet d'importation ne peut agir qu'une fois : le reste est du bruit.

    Un script d'entrée pose le crochet, puis importe un module qui le pose à son tour.
    Le second appel arrive forcément trop tard — mais l'avertissement qu'il produisait
    accusait un code correct, et un avertissement qu'on apprend à ignorer finit par
    couvrir celui qui compte.
    """
    import io
    from contextlib import redirect_stderr

    import pandas  # noqa: F401 — l'important est qu'il soit en mémoire

    sorties = []
    for _ in range(3):
        tampon = io.StringIO()
        with redirect_stderr(tampon):
            dev.activer_cudf()
        sorties.append(tampon.getvalue())

    assert sorties[0], "le premier appel doit signaler qu'il est trop tard"
    assert not any(sorties[1:]), f"appels suivants bavards : {sorties[1:]}"
