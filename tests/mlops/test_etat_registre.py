"""L'état des modèles vient du REGISTRE, et survit au retrait de la chaîne NLP.

Ce test vivait dans `tests/nlp/`. Il n'y avait pas sa place : il décrit le registre ML,
pas un fournisseur de LLM. Le voisinage aurait fait disparaître la version du modèle
affichée sur le site le jour où la chaîne NLP a été retirée.
"""

import pathlib

from packages.mlops.etat import etat_modeles

RACINE = pathlib.Path(__file__).resolve().parents[2]


def test_l_etat_des_modeles_vient_du_registre_pas_d_une_constante():
    """Un numéro de version écrit en dur se détache de ce qu'il désigne (ADR-0154)."""
    src = (RACINE / "packages" / "mlops" / "etat.py").read_text(encoding="utf-8")
    assert "from packages.mlops.registre import Registre" in src
    e = etat_modeles()
    assert e["disponible"] is True
    for cle in ("production", "dataset_hash", "git_commit", "candidats", "archives",
                "reproductible", "incoherences"):
        assert cle in e


def test_un_registre_indisponible_ne_fait_PAS_tomber_l_etat_IA():
    import packages.mlops.registre as R
    original = R.Registre
    R.Registre = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disque"))
    try:
        e = etat_modeles()
        assert e["disponible"] is False and "disque" in e["motif"]
    finally:
        R.Registre = original


def test_les_routes_IA_ENCORE_UTILISEES_survivent_aux_retraits():
    """Ce test garde les routes contre un retrait COLLATÉRAL, pas contre un retrait
    voulu. Il en gardait cinq ; deux sont parties le 18/09 avec le « Commentaire IA »
    de l'accueil, qui ne servait plus personne et commentait le portefeuille de DÉMO.
    Les trois qui restent ont chacune un appelant vivant : `diagnostic` (panneau de
    réglages), `chat` (copilote), `metrics` et `modeles`.

    LA DIFFÉRENCE COMPTE. Une route retirée par accident casse une page en silence ;
    une route retirée exprès doit disparaître d'ici AUSSI, sinon le test devient un
    obstacle au ménage plutôt qu'un garde-fou."""
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    for route in ("/api/ai/diagnostic", "/api/ai/chat", "/api/ai/metrics",
                  "/api/ai/modeles"):
        assert route in src, route
    for partie in ("/api/ai/status", "/api/ai/commentary"):
        assert partie not in src, f"{partie} n'a plus d'appelant : à retirer"
    assert "packages.nlp" not in src, "plus aucune trace de la chaîne NLP locale"


# ─── Un artefact qui SERT sans être tracé
# ──────────────────────────────────────────────

def test_un_artefact_non_trace_est_SIGNALE(tmp_path):
    """LE CAS RÉEL DU 16/09. Le registre annonçait « vide » pendant que l'artefact à
    AUC 0,504 servait en production. Les deux affirmations étaient vraies, et rien ne
    les confrontait : `incoherences()` n'inspectait que les entrées déjà inscrites, donc
    un modèle jamais inscrit lui restait invisible — précisément le cas qui compte."""
    from packages.mlops.registre import Registre

    (tmp_path / "ml_swing.pkl").write_bytes(b"artefact")
    reg = Registre(tmp_path)
    assert not reg.entrees
    soucis = reg.orphelins()
    assert len(soucis) == 1 and "ml_swing.pkl" in soucis[0]
    assert "NON TRACÉ" in soucis[0]
    assert soucis == reg.incoherences(), "l'orphelin remonte dans les incohérences"


def test_un_artefact_TRACÉ_n_est_pas_signale(tmp_path):
    from packages.mlops.manifest import Manifest
    from packages.mlops.registre import Registre

    art = tmp_path / "ml_swing.pkl"
    art.write_bytes(b"artefact")
    reg = Registre(tmp_path)
    reg.enregistrer(Manifest.creer(modele="m", run_id="r", dataset_hash="h",
                                   feature_version="1-feat", seed=7,
                                   artefact_sha256="", metriques={}, config={}),
                    art, "test")
    assert reg.orphelins() == []


def test_l_empreinte_sha256_a_cote_n_est_PAS_prise_pour_un_modele(tmp_path):
    """`ml_*.pkl` ne doit pas matcher `ml_*.pkl.sha256` : compter l'empreinte comme un
    second artefact ferait apparaître un orphelin permanent, et un avertissement
    permanent cesse d'être lu."""
    from packages.mlops.registre import Registre

    (tmp_path / "ml_swing.pkl.sha256").write_text("abc")
    assert Registre(tmp_path).orphelins() == []


def test_six_orphelins_ne_produisent_pas_six_avertissements(tmp_path):
    """UN AVERTISSEMENT PERMANENT CESSE D'ÊTRE LU. `ml_<signature>.pkl` est un cache par
    configuration : six fichiers, c'est six signatures, pas six champions rivaux. On
    nomme le plus récent — le seul susceptible de servir — et on compte les autres."""
    import os

    from packages.mlops.registre import Registre

    for i, nom in enumerate(["ml_vieux.pkl", "ml_moyen.pkl", "ml_frais.pkl"]):
        f = tmp_path / nom
        f.write_bytes(b"x")
        os.utime(f, (1000 + i * 100, 1000 + i * 100))
    soucis = Registre(tmp_path).orphelins()
    assert len(soucis) == 2, soucis
    assert "ml_frais.pkl" in soucis[0] and "plus récent" in soucis[0]
    assert "2 autre(s)" in soucis[1]


# ─── Le marqueur « -sale » ne doit pas être permanent ────────────────────────────────

def test_les_donnees_REGENEREES_ne_salissent_pas_l_arbre(tmp_path):
    """MESURÉ LE 17/09. Le premier modèle jamais tracé portait déjà « entraîné depuis
    un arbre GIT MODIFIÉ — non reproductible », à cause de deux fichiers que
    `cron_daily.sh` réécrit quelques minutes avant l'entraînement. Aucun run n'aurait
    JAMAIS pu être déclaré reproductible, et l'avertissement aurait cessé d'être lu.

    Le commit fige le CODE ; les données d'entrée changent tous les jours par nature —
    c'est `dataset_hash` qui les capture."""
    import subprocess

    from packages.mlops.manifest import fichiers_salissants, git_commit

    def sh(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a],
                       capture_output=True, check=False)

    sh("init", "-q")
    sh("config", "user.email", "t@t")
    sh("config", "user.name", "t")
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "mobile_universe.csv").write_text("a\n")
    (tmp_path / "data" / "delisted.csv").write_text("b\n")
    (tmp_path / "code.py").write_text("x = 1\n")
    sh("add", "-A")
    sh("commit", "-qm", "initial")
    assert fichiers_salissants(tmp_path) == []
    propre = git_commit(tmp_path)
    assert not propre.endswith("-sale")

    # Les DEUX fichiers régénérés bougent : l'arbre reste propre au sens du manifeste.
    (tmp_path / "config" / "mobile_universe.csv").write_text("a2\n")
    (tmp_path / "data" / "delisted.csv").write_text("b2\n")
    assert fichiers_salissants(tmp_path) == []
    assert git_commit(tmp_path) == propre

    # Du CODE bouge : là, le run n'est plus reproductible, et on le dit.
    (tmp_path / "code.py").write_text("x = 2\n")
    assert fichiers_salissants(tmp_path) == ["code.py"]
    assert git_commit(tmp_path).endswith("-sale")


def test_le_statut_porcelain_est_lu_SANS_perdre_sa_premiere_colonne():
    """LE DÉFAUT DANS MON PROPRE CORRECTIF. `git status --porcelain` aligne son statut
    sur deux colonnes : « M fichier » (modifié non indexé) commence par une ESPACE. Un
    `.strip()` global la supprime, tout décale d'un caractère, et
    `config/mobile_universe.csv` devient `onfig/mobile_universe.csv` — qui ne correspond
    à aucune exclusion. Le filtre aurait semblé posé tout en ne filtrant rien."""
    from packages.mlops.manifest import _chemin_porcelain
    attendu = "config/mobile_universe.csv"
    assert _chemin_porcelain(f" M {attendu}") == attendu
    assert _chemin_porcelain("M  data/delisted.csv") == "data/delisted.csv"
    assert _chemin_porcelain("?? nouveau.txt") == "nouveau.txt"


def test_un_renommage_rend_la_DESTINATION():
    from packages.mlops.manifest import _chemin_porcelain
    assert _chemin_porcelain("R  vieux.py -> neuf.py") == "neuf.py"


# ─── Le registre doit s'EXPLIQUER, pas seulement classer
# ───────────────────────────────

def _registre_avec_rejet(tmp_path):
    from packages.mlops.manifest import Manifest
    from packages.mlops.registre import Registre

    art = tmp_path / "ml_x.pkl"
    art.write_bytes(b"a")
    reg = Registre(tmp_path)
    m = Manifest.creer(modele="gb", run_id="r", dataset_hash="h",
                       feature_version="1-feat", seed=7, artefact_sha256="",
                       metriques={"auc": 0.532}, config={})
    reg.enregistrer(m, art, "candidat du jour")
    reg.rejeter(m.version, "DSR challenger 0.000 ≤ seuil 0.000 (pas d'edge OOS)")
    return reg, m.version


def test_le_MOTIF_d_une_decision_est_lisible(tmp_path):
    """Il était STOCKÉ depuis toujours, jamais montré. « rejected » sans le pourquoi ne
    répond pas à la seule question qu'on pose à un registre."""
    reg, version = _registre_avec_rejet(tmp_path)
    assert "pas d'edge OOS" in reg.entrees[version].dernier_motif()


def test_une_PRODUCTION_VIDE_dit_pourquoi(tmp_path):
    """« PRODUCTION : (aucune) » se lit comme un trou à combler. Ce n'en est pas
    forcément un : un modèle sans edge DOIT être refusé, et l'absence de production est
    alors le bon résultat du gate — encore faut-il le dire."""
    reg, version = _registre_avec_rejet(tmp_path)
    pourquoi = reg.pourquoi_pas_de_production()
    assert version in pourquoi and "pas d'edge OOS" in pourquoi


def test_un_registre_VIERGE_se_distingue_d_un_candidat_refuse(tmp_path):
    """Deux silences différents : « rien n'a jamais été soumis » et « ce qui l'a été
    a été refusé ». Le premier est un trou, le second une décision."""
    from packages.mlops.registre import Registre
    assert "n'a encore été soumis" in Registre(tmp_path).pourquoi_pas_de_production()


def test_avec_une_production_le_motif_se_TAIT(tmp_path):
    from packages.mlops.manifest import Manifest
    from packages.mlops.registre import Registre

    art = tmp_path / "ml_y.pkl"
    art.write_bytes(b"a")
    reg = Registre(tmp_path)
    m = Manifest.creer(modele="gb", run_id="r", dataset_hash="h",
                       feature_version="1-feat", seed=7, artefact_sha256="",
                       metriques={}, config={})
    reg.enregistrer(m, art, "candidat")
    reg.promouvoir(m.version, "adoption")
    assert reg.pourquoi_pas_de_production() == ""


def test_le_site_expose_ce_motif(tmp_path, monkeypatch):
    """Sans ce champ, la page affiche un trou là où il y a une décision fondée."""
    import packages.mlops.registre as R
    from packages.mlops.etat import etat_modeles

    _registre_avec_rejet(tmp_path)
    original = R.Registre
    monkeypatch.setattr(R, "Registre", lambda *a, **k: original(tmp_path))
    e = etat_modeles()
    assert e["production"] is None
    assert e["production_motif"] and "pas d'edge OOS" in e["production_motif"]
