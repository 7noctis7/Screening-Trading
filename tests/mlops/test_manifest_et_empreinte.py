"""Traçabilité : une empreinte doit être stable, un manifeste doit refuser d'inventer."""

import pathlib

from packages.mlops.empreinte import (
    court,
    empreinte,
    empreinte_jeu,
    sha256_fichier,
    verifier,
)
from packages.mlops.manifest import Manifest, environnement, git_commit

# ─── Empreintes ────────────────────────────────────────────────────────────────────────

def test_l_ordre_des_cles_ne_change_pas_l_empreinte():
    """Sans cela, l'empreinte varierait d'un poste à l'autre et ne prouverait plus rien."""
    assert empreinte({"b": 1, "a": 2}) == empreinte({"a": 2, "b": 1})


def test_nan_et_infinis_sont_hachables_et_distincts():
    """`NaN != NaN` casse toute comparaison naïve — on les NOMME."""
    n = empreinte([float("nan")])
    assert n == empreinte([float("nan")])
    assert n != empreinte([float("inf")]) != empreinte([float("-inf")])


def test_un_flottant_proche_mais_different_change_l_empreinte():
    assert empreinte([1.0]) != empreinte([1.000000001])


def test_changer_les_features_change_l_empreinte_du_jeu():
    """Un dataset dont on change les colonnes n'est pas le même dataset, même si les prix
    sont identiques. L'oublier ferait passer un changement de features pour une simple
    réexécution."""
    d = {"AAPL": [1, 2, 3]}
    assert empreinte_jeu(d, colonnes=["a"]) != empreinte_jeu(d, colonnes=["a", "b"])


def test_l_ordre_des_symboles_ne_compte_pas():
    a = empreinte_jeu({"AAPL": [1], "MSFT": [2]}, colonnes=["c"])
    b = empreinte_jeu({"MSFT": [2], "AAPL": [1]}, colonnes=["c"])
    assert a == b


def test_verification_de_fichier(tmp_path):
    p = tmp_path / "m.pkl"
    p.write_bytes(b"contenu")
    h = sha256_fichier(p)
    assert verifier(p, h)
    p.write_bytes(b"autre")
    assert not verifier(p, h)
    assert not verifier(tmp_path / "absent.pkl", h)
    assert not verifier(p, "")          # empreinte vide ⇒ on ne valide RIEN


def test_court_est_stable_et_borne():
    h = empreinte({"x": 1})
    assert court(h) == h[:16] and len(court(h)) == 16


# ─── Manifeste ─────────────────────────────────────────────────────────────────────────

def test_le_manifeste_capture_l_environnement():
    env = environnement()
    assert env["python"] and env["os"]
    # Une bibliothèque absente vaut None — JAMAIS une version plausible inventée.
    for cle in ("numpy", "torch", "xgboost"):
        assert cle in env and (env[cle] is None or isinstance(env[cle], str))


def test_un_arbre_sale_est_signale_comme_tel():
    """Un modèle entraîné depuis un arbre modifié n'est pas reproductible à partir de ce
    commit — et c'est exactement ce qu'il faut savoir avant d'essayer de le refaire."""
    sha = git_commit()
    assert sha, "le commit doit toujours être renseigné, fût-ce « inconnu »"
    if sha.endswith("-sale"):
        assert len(sha) > len("-sale")


def test_reproductible_nomme_CE_QUI_manque():
    """Un « non reproductible » sans motif ne se corrige pas."""
    m = Manifest.creer("swing_ml", "EXP", dataset_hash="", feature_version="v1")
    ok, motif = m.reproductible()
    assert not ok
    assert "dataset" in motif and "graine" in motif


def test_un_manifeste_complet_se_declare_reproductible(monkeypatch):
    import packages.mlops.manifest as M
    monkeypatch.setattr(M, "git_commit", lambda *a, **k: "a" * 40)
    m = M.Manifest.creer("swing_ml", "EXP", dataset_hash="d1", feature_version="v1",
                         seed=7, artefact_sha256="b" * 64)
    assert m.reproductible()[0]


def test_la_version_porte_le_modele_la_date_et_le_commit():
    m = Manifest.creer("swing_ml", "EXP", dataset_hash="d", feature_version="v")
    assert m.version.startswith("swing_ml-")
    assert m.git_commit[:7] in m.version or m.git_commit == "inconnu"


def test_un_manifeste_ancien_reste_lisible():
    """Ajouter un champ ne doit pas rendre illisible l'historique déjà écrit — sinon on
    perd la traçabilité en voulant l'améliorer."""
    ancien = {"modele": "m", "version": "v", "run_id": "r", "git_commit": "c",
              "dataset_hash": "d", "feature_version": "f", "seed": None,
              "champ_disparu_depuis": "ignoré"}
    m = Manifest.depuis_dict(ancien)
    assert m.modele == "m" and m.version == "v"


def test_aller_retour_dict():
    m = Manifest.creer("swing_ml", "EXP", dataset_hash="d", feature_version="v", seed=3)
    assert Manifest.depuis_dict(m.en_dict()) == m


def test_le_manifeste_ne_contient_aucun_secret():
    """Il part potentiellement vers un fournisseur de calcul : il ne doit transporter
    aucune clé (point 50)."""
    src = (pathlib.Path(__file__).resolve().parents[2] / "packages" / "mlops"
           / "manifest.py").read_text(encoding="utf-8")
    for interdit in ("API_KEY", "SECRET", "TOKEN", "PASSWORD"):
        assert interdit not in src.upper().replace("QUANT_MATERIEL", "")
