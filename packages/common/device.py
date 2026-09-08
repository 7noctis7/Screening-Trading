"""Choix du matériel de calcul — écrit une fois, valable partout.

Le projet se développe sur Mac (Apple Silicon, backend MPS) et doit migrer sur une
machine NVIDIA (CUDA) sans qu'une seule ligne change. Tout ce qui touche au matériel
est donc ici, et nulle part ailleurs : un `.to("mps")` écrit en dur dans un module de
calcul est une ligne qui marche sur un poste et casse sur l'autre, silencieusement,
des semaines plus tard.

DEUX RÈGLES QUI TIENNENT CE FICHIER

1. **Aucun import lourd au niveau module.** Le cœur du dépôt ne déclare AUCUNE
   dépendance (`pyproject.toml`) : `torch`, `xgboost` et `cudf` sont optionnels et
   absents de la plupart des environnements, CI comprise. Tout est importé à
   l'intérieur des fonctions, dans un `try`. Importer ce module ne doit jamais
   pouvoir échouer.

2. **Le repli est un résultat, pas un échec.** Sans GPU, on rend `"cpu"` et on le
   DIT. Un repli silencieux ferait tourner un entraînement des heures sur processeur
   en laissant croire au contraire — c'est la panne la plus coûteuse de la série,
   parce qu'elle ne ressemble pas à une panne.

Échappatoire : `QUANT_DEVICE=cpu|mps|cuda` force le choix. Indispensable pour
comparer deux matériels sur la même machine, ou contourner un pilote défaillant sans
toucher au code.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache

DEVICES = ("cuda", "mps", "cpu")

# La bannière s'imprime une fois par processus. Un entraînement qui appelle le
# détecteur dans une boucle noierait la sortie sous des centaines de lignes.
_BANNIERE_FAITE = False


def _torch():
    """`torch` s'il est importable, sinon `None`. Jamais d'exception."""
    try:
        import torch
        return torch
    except Exception:  # noqa: BLE001 — absence de torch = cas nominal sur CI/Mac nu
        return None


@lru_cache(maxsize=1)
def get_optimal_device() -> str:
    """Le meilleur matériel disponible : `"cuda"`, `"mps"` ou `"cpu"`.

    Ordre voulu : CUDA d'abord (la machine cible), MPS ensuite (le poste de
    développement), processeur en dernier recours. Le résultat est mis en cache :
    l'interrogation des pilotes coûte quelques millisecondes, et la réponse ne change
    pas en cours de processus.
    """
    forced = os.environ.get("QUANT_DEVICE", "").strip().lower()
    if forced in DEVICES:
        return forced

    t = _torch()
    if t is None:
        return "cpu"
    try:
        if t.cuda.is_available():
            return "cuda"
    except Exception:  # noqa: BLE001 — pilote cassé : on continue, on ne plante pas
        pass
    try:
        # `backends.mps` n'existe qu'à partir de torch 1.12 : `getattr` plutôt qu'un
        # accès direct, sinon une version ancienne lève AttributeError ici même.
        mps = getattr(getattr(t, "backends", None), "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def torch_device():
    """Le `torch.device` correspondant, à passer à `.to(...)`.

    Lève `RuntimeError` si `torch` n'est pas installé : appeler cette fonction
    signifie qu'on s'apprête à manipuler des tenseurs, et un objet muet rendu à la
    place produirait une erreur bien plus loin, bien plus obscure.
    """
    t = _torch()
    if t is None:
        raise RuntimeError(
            "torch n'est pas installé : `pip install -e '.[sentiment]'`. "
            "Pour la détection seule, `get_optimal_device()` suffit et rend « cpu »."
        )
    return t.device(get_optimal_device())


def device_index() -> int:
    """Index de matériel attendu par `transformers.pipeline` : 0 = GPU, -1 = CPU.

    L'API des pipelines HuggingFace ne prend pas une chaîne mais un entier, et c'est
    exactement le genre de détail qu'on recopie de travers d'un appel à l'autre.
    """
    return 0 if get_optimal_device() in ("cuda", "mps") else -1


def banniere(flux=None, force: bool = False) -> str:
    """Imprime « Exécution sur : … » une fois, et rend la ligne.

    Le nom du matériel est le premier chiffre à vérifier quand un entraînement met
    trois heures au lieu de vingt minutes.
    """
    global _BANNIERE_FAITE
    dev = get_optimal_device()
    ligne = f"Exécution sur : {dev.upper()}"
    if os.environ.get("QUANT_DEVICE", "").strip().lower() in DEVICES:
        ligne += "  (forcé par QUANT_DEVICE)"
    elif dev == "cpu":
        ligne += "  (aucun GPU détecté — les calculs lourds seront lents)"
    if force or not _BANNIERE_FAITE:
        print(ligne, file=flux or sys.stderr)
        _BANNIERE_FAITE = True
    return ligne


def _version_majeure(module) -> int:
    """Numéro de version majeur d'un module, 0 si illisible."""
    brut = str(getattr(module, "__version__", "") or "").split(".")[0]
    return int(brut) if brut.isdigit() else 0


def params_arbres(lib: str = "xgboost") -> dict:
    """Paramètres matériels pour un modèle à arbres — et RIEN d'autre.

    Ne rend que ce qui concerne le matériel : profondeur, nombre d'arbres et
    régularisation restent définis là où ils l'ont toujours été. Un dictionnaire qui
    mélangerait les deux ferait dériver les hyperparamètres du modèle à chaque
    changement de machine, et les résultats avec.

    XGBoost a changé d'API en 2.0 : `tree_method="gpu_hist"` a laissé place à
    `tree_method="hist"` + `device="cuda"`. On lit la version installée plutôt que de
    parier — l'ancienne forme est ignorée en silence par la nouvelle, ce qui ferait
    tourner sur processeur une machine à 10 000 € sans le moindre message.
    """
    cuda = get_optimal_device() == "cuda"
    lib = lib.strip().lower()

    if lib == "xgboost":
        if not cuda:
            return {"tree_method": "hist"}
        try:
            import xgboost
            majeure = _version_majeure(xgboost)
        except Exception:  # noqa: BLE001
            majeure = 2      # absent ici : on vise l'API courante
        if majeure >= 2:
            return {"tree_method": "hist", "device": "cuda"}
        return {"tree_method": "gpu_hist", "predictor": "gpu_predictor"}

    if lib == "lightgbm":
        # LightGBM n'est PAS compilé avec le support GPU par défaut (`pip install
        # lightgbm` donne une version processeur). Demander `device_type="gpu"` sur
        # une telle installation lève à l'entraînement. On ne l'active donc que si le
        # binaire présent sait le faire.
        return {"device_type": "gpu"} if (cuda and _lightgbm_gpu()) else {}

    if lib == "catboost":
        return {"task_type": "GPU"} if cuda else {"task_type": "CPU"}

    raise ValueError(f"bibliothèque d'arbres inconnue : {lib!r}")


def _lightgbm_gpu() -> bool:
    """True si le binaire LightGBM installé accepte réellement le GPU."""
    try:
        import lightgbm as lgb
        # Aucune introspection fiable des capacités de compilation : on entraîne UN
        # arbre sur deux points. Si le binaire n'a pas le GPU, ça lève ici — à
        # l'endroit où on peut encore choisir, pas au milieu d'un entraînement long.
        lgb.train({"device_type": "gpu", "verbose": -1, "num_iterations": 1},
                  lgb.Dataset([[0.0], [1.0]], label=[0, 1]))
        return True
    except Exception:  # noqa: BLE001 — binaire sans GPU : cas nominal
        return False


_CUDF_TENTE = False      # le crochet d'importation ne se pose qu'une fois, utilement
_CUDF_ACTIF = False


def activer_cudf() -> bool:
    """Active l'accélération NVIDIA RAPIDS pour pandas. Rend True si elle est active.

    ATTENTION, ce n'est PAS un import de repli. `cudf.pandas` ne se substitue pas à
    pandas par un `import cudf.pandas as pd` : c'est un CROCHET D'IMPORTATION qui doit
    être posé AVANT que pandas n'entre en mémoire. Une fois `pandas` importé, poser le
    crochet ne fait plus rien — et comme aucune erreur n'est levée, on croit tourner
    sur GPU en tournant sur processeur.

    D'où l'appel en TÊTE des points d'entrée, avant tout autre import, et le
    diagnostic explicite quand il est trop tard.

    Sur Mac, `cudf` est absent : on rend False sans bruit et pandas reste pandas.

    IDEMPOTENT. Un script d'entrée pose le crochet, puis importe un module qui le pose à
    son tour : le second appel arrive forcément trop tard et affichait un avertissement
    qui accusait un code correct. On ne se plaint que du PREMIER appel — le seul qui
    pouvait encore agir.
    """
    global _CUDF_TENTE, _CUDF_ACTIF
    if _CUDF_TENTE:
        return _CUDF_ACTIF
    _CUDF_TENTE = True
    if "pandas" in sys.modules:
        print("cudf.pandas non activé : pandas est déjà importé. Déplacez l'appel à "
              "activer_cudf() AVANT les autres imports.", file=sys.stderr)
        return False
    try:
        import cudf.pandas
        cudf.pandas.install()
        _CUDF_ACTIF = True
    except Exception:  # noqa: BLE001 — absence de cudf = cas nominal hors NVIDIA
        _CUDF_ACTIF = False
    return _CUDF_ACTIF


def resume() -> dict:
    """État matériel complet, pour journaliser une exécution sans la relancer."""
    return {
        "device": get_optimal_device(),
        "force_par_env": os.environ.get("QUANT_DEVICE", "") or None,
        "torch": _torch() is not None,
        "cudf_actif": "cudf" in sys.modules,
    }
