"""Le verrou d'environnement — détecter plutôt qu'imposer.

MESURÉ LE 16/09 : `constraints.txt` est généré pour les extras `api`, `data`, `quant`. Il
épingle numpy, pandas et scipy, et laisse LIBRES scikit-learn, xgboost, lightgbm et torch —
c'est-à-dire précisément ce qui entraîne. Un modèle sérialisé sous une version et rechargé
sous une autre peut se charger ET PRÉDIRE DIFFÉREMMENT, sans lever d'erreur.
"""

import pathlib

from packages.mlops.environnement import (
    ABSENT,
    GRAVE,
    MINEUR,
    commande_regeneration,
    comparer_versions,
    ecarts,
    non_verrouillees,
    resume,
    verrou,
)

RACINE = pathlib.Path(__file__).resolve().parents[2]


# ─── Lecture du verrou ─────────────────────────────────────────────────────────────────

def test_le_verrou_du_depot_est_lisible():
    fige = verrou()
    assert len(fige) > 50
    assert "numpy" in fige and "pandas" in fige


def test_les_bibliotheques_d_entrainement_sont_bien_le_trou(tmp_path):
    """Le constat qui justifie ce module. S'il devient faux — tant mieux — ce test le dira."""
    libres = non_verrouillees()
    assert "scikit-learn" in libres, (
        "scikit-learn est maintenant épinglé : mettre à jour le constat de "
        "docs/AI_ARCHITECTURE_AUDIT.md plutôt que ce test")


def test_non_verrouillees_est_CALCULE_pas_ecrit(tmp_path):
    """Ajouter une dépendance d'entraînement sans l'épingler doit se voir tout seul."""
    (tmp_path / "c.txt").write_text("numpy==1.0\nscikit-learn==1.5\nxgboost==2.0\n"
                                    "lightgbm==4.0\ntorch==2.5\npandas==2.0\nscipy==1.0\n",
                                    encoding="utf-8")
    assert non_verrouillees(tmp_path / "c.txt") == []


def test_verrou_absent_ne_casse_rien(tmp_path):
    assert verrou(tmp_path / "inexistant.txt") == {}


def test_les_noms_sont_normalises(tmp_path):
    """`scikit_learn` et `scikit-learn` désignent le même paquet ; l'oublier ferait croire
    à un trou qui n'existe pas."""
    (tmp_path / "c.txt").write_text("scikit_learn==1.5\n", encoding="utf-8")
    assert "scikit-learn" in verrou(tmp_path / "c.txt")


# ─── Gravité des écarts ────────────────────────────────────────────────────────────────

def test_versions_identiques_ne_sont_pas_un_ecart():
    assert comparer_versions("2.1.3", "2.1.3") is None


def test_un_changement_majeur_est_grave():
    assert comparer_versions("1.26.4", "2.4.6") == GRAVE


def test_un_changement_mineur_est_grave_aussi_sur_le_second_niveau():
    """1.5 → 1.7 de scikit-learn a déjà changé des comportements de sérialisation."""
    assert comparer_versions("1.5.0", "1.7.0") == GRAVE


def test_un_patch_est_mineur():
    assert comparer_versions("3.0.3", "3.0.5") == MINEUR


def test_une_bibliotheque_apparue_ou_disparue_est_signalee():
    assert comparer_versions(None, "2.5.0") == ABSENT
    assert comparer_versions("2.5.0", None) == ABSENT
    assert comparer_versions(None, None) is None


# ─── Comparaison d'environnements ──────────────────────────────────────────────────────

def test_ecarts_classe_le_plus_grave_en_premier():
    """Une liste de vingt lignes dont la première est un patch ne se lit pas jusqu'au bout."""
    es = ecarts({"python": "3.11.9", "pandas": "3.0.3", "numpy": "1.26.4"},
                {"python": "3.11.9", "pandas": "3.0.5", "numpy": "2.4.6"})
    assert [e["cle"] for e in es] == ["numpy", "pandas"]
    assert es[0]["gravite"] == GRAVE and es[1]["gravite"] == MINEUR


def test_aucun_ecart_rend_une_chaine_VIDE():
    """Un rapport qui parle toujours n'alerte jamais."""
    env = {"python": "3.11.9", "numpy": "2.4.6"}
    assert resume(env, env) == ""


def test_le_resume_compte_les_ecarts_majeurs():
    dit = resume({"python": "3.11.9", "numpy": "1.26.4"},
                 {"python": "3.12.1", "numpy": "2.4.6"})
    assert "2 MAJEUR" in dit and "numpy" in dit


def test_le_resume_est_borne():
    """Quatre écarts nommés, puis « … » : au-delà c'est un mur, pas une alerte."""
    a = {k: "1.0.0" for k in ("python", "numpy", "pandas", "scipy", "torch",
                              "scikit-learn", "xgboost")}
    b = {k: "2.0.0" for k in a}
    dit = resume(a, b)
    assert dit.endswith("…") and dit.count("→") == 4


# ─── La commande de régénération ───────────────────────────────────────────────────────

def test_le_script_de_rapport_sort_en_erreur_si_des_libs_sont_libres():
    """Fail-loud : un rapport qui sort 0 quoi qu'il arrive ne bloque aucune chaîne."""
    src = (RACINE / "scripts" / "verrou_env.py").read_text(encoding="utf-8")
    assert "return 1" in src and "return 0" in src


def test_le_module_ne_regenere_rien_lui_meme():
    """`pip-compile` télécharge des dépendances : il doit tourner sur la machine qui
    entraîne, pas être déclenché par un module d'analyse.

    VÉRIFIÉ PAR L'AST, plus par sous-chaîne. La version d'avant interdisait le TEXTE
    « pip install » n'importe où dans le fichier — elle est tombée le jour où le
    module a
    eu besoin de CHERCHER cette chaîne dans le Makefile pour vérifier que le verrou y
    est
    appliqué. Chercher un texte et l'exécuter sont deux choses opposées ; un test qui
    les
    confond interdit la mesure en croyant interdire l'action."""
    import ast

    src = (RACINE / "packages" / "mlops" / "environnement.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)

    importes = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            importes.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            importes.add(n.module.split(".")[0])
    for interdit in ("subprocess", "os", "shutil", "pip"):
        assert interdit not in importes, f"ce module d'analyse importe « {interdit} »"

    appels = {n.func.attr for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    for interdit in ("system", "run", "Popen", "check_call", "check_output", "main"):
        assert interdit not in appels, f"ce module d'analyse appelle « {interdit}() »"


# ─── Une consigne qui nomme un outil absent est pire qu'un silence ────────────────────

def _recette(cible: str) -> list[str]:
    """Les COMMANDES d'une cible Make, continuations jointes.

    Une recette s'arrête à la première ligne SANS tabulation — il n'y a pas forcément de
    ligne vide entre deux cibles. Découper sur « \\n\\n » débordait sur la cible
    suivante
    et faisait échouer le test sur `bash scripts/setup_local.sh`, qui appartient à
    `setup`.
    """
    texte = (RACINE / "Makefile").read_text(encoding="utf-8").replace("\\\n", " ")
    apres = texte.split(f"\n{cible}:", 1)[1].splitlines()[1:]
    lignes = []
    for ligne in apres:
        if not ligne.startswith("\t"):
            break
        nu = ligne.strip()
        if not nu.startswith(("@#", "@echo")):
            lignes.append(nu)
    return lignes


def test_la_commande_annoncee_EXISTE_forcement_sur_la_machine():
    """DEUX FOIS DE SUITE, le message a nommé un binaire absent de la machine visée :
    `pip-compile` le 17/09 au matin (pip-tools n'est pas une dépendance du projet), puis
    `uv` le soir (présent sur le poste de développement, ABSENT du VPS). Les deux fois,
    l'utilisateur a lu « No such file or directory » et cherché du côté de son
    environnement, alors que c'était la CONSIGNE qui était fausse.

    Un nom d'outil est une HYPOTHÈSE sur une machine qu'on ne voit pas. Une cible `make`
    n'en est pas une : elle vit dans le Makefile que l'utilisateur vient d'exécuter pour
    lire le message."""
    from packages.mlops.environnement import commande_regeneration

    commande = commande_regeneration()
    assert commande.startswith("make "), (
        "annoncer un binaire, c'est parier qu'il est installé là-bas ; une cible "
        f"`make` ne parie rien. Reçu : {commande!r}")
    cible = commande.split(maxsplit=1)[1].strip()
    makefile = (RACINE / "Makefile").read_text(encoding="utf-8")
    assert f"\n{cible}:" in makefile, f"la cible « {cible} » manque au Makefile"


def test_la_recette_passe_par_L_INTERPRETEUR_DU_PROJET():
    """Le venv est la seule chose dont l'existence est garantie partout où ce projet
    tourne. Un binaire du PATH ne l'est pas — c'est exactement ce qui a échoué deux
    fois."""
    lignes = _recette("verrou-regen")
    assert lignes, "la cible doit avoir des commandes"
    for ligne in lignes:
        assert ligne.startswith("$(PYTHON)"), (
            f"cette ligne dépend d'un binaire du PATH : {ligne!r}")


def test_la_recette_s_installe_son_outil_si_besoin():
    """Sans cette ligne, la cible rejouerait le même échec sur toute machine où l'outil
    manque — et il manquait sur celle qui entraîne."""
    recette = " ".join(_recette("verrou-regen"))
    assert "pip install" in recette and "uv" in recette


def test_la_recette_demande_TOUS_les_extras_d_entrainement():
    """En oublier un rend le verrou muet sur la bibliothèque qui produit le modèle."""
    from packages.mlops.environnement import EXTRAS_ENTRAINEMENT

    recette = " ".join(_recette("verrou-regen"))
    for extra in EXTRAS_ENTRAINEMENT:
        assert f"--extra {extra}" in recette, extra
    assert "constraints.txt" in recette




# ─── AUCUNE cible d'installation ne doit dépendre d'un binaire du PATH
# ─────────────────

def test_aucune_cible_d_installation_ne_suppose_un_binaire_du_PATH():
    """TROISIÈME OCCURRENCE EN UNE JOURNÉE. `verrou-regen` a nommé `pip-compile`, puis
    `uv` ; corrigé, il ne dépendait plus du PATH — mais `install` faisait encore
    `uv venv && uv pip install`, et le VPS n'a pas `uv`. J'avais corrigé UNE cible
    sur deux.

    Et `install` est la pire de toutes : c'est celle qu'on lance quand rien ne marche
    encore. Ce test couvre les deux, pour qu'il n'y ait pas de quatrième fois."""
    for cible in ("install", "verrou-regen"):
        for ligne in _recette(cible):
            premier = ligne.lstrip("@").split()[0]
            assert premier in ("[", "python3", ".venv/bin/python", "$(PYTHON)"), (
                f"la cible « {cible} » lance « {premier} », un binaire du PATH : "
                f"{ligne!r}")


def test_le_detecteur_ne_se_declenche_PAS_sur_l_amorcage_d_un_OUTIL():
    """MON PROPRE FAUX POSITIF, vu le soir même. `verrou-regen` amorce `uv` par un
    `pip install uv` sans contrainte — et c'est normal : le verrou décrit les
    dépendances du PROJET, pas l'outil qui les résout. Mon détecteur lisait les lignes
    contenant « pip install » et criait « installation SANS verrou » sur la ligne
    d'amorçage que je venais d'écrire.

    Un détecteur qui se déclenche sur son propre correctif fait exactement le bruit
    qu'il devait supprimer."""
    from packages.mlops.environnement import applique

    ok, motif = applique()
    assert ok, motif
    recette = " ".join(_recette("verrou-regen"))
    assert "pip install --quiet uv" in recette, (
        "l'amorçage doit exister — c'est lui que le détecteur doit savoir ignorer")
