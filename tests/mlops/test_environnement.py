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

def test_la_commande_couvre_les_extras_d_entrainement():
    """Le verrou actuel a été généré SANS `ml` ni `sentiment` — c'est toute l'origine du
    trou. La commande rendue doit les inclure, sinon on régénère le même défaut.

    L'assertion porte sur le NOM de l'extra, pas sur la ponctuation du résolveur : elle
    exigeait `--extra=ml` et serait tombée au passage de `pip-compile` à `uv`, qui écrit
    `--extra ml`. Un test qui fige une syntaxe d'outil ne teste plus l'intention."""
    c = commande_regeneration()
    for extra in ("ml", "sentiment", "quant", "data", "api"):
        assert f"--extra={extra}" in c or f"--extra {extra}" in c, extra
    assert "constraints.txt" in c


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

def test_la_commande_annoncee_est_CELLE_QUE_LE_MAKEFILE_LANCE():
    """MESURÉ LE 17/09. `make verrou` imprimait « pip-compile … » et `make verrou-regen`
    lançait la même chose — sauf que `pip-compile` appartient à `pip-tools`, qui n'est
    nulle part dans les dépendances de ce projet. Résultat sur le VPS :
    « pip-compile: No such file or directory ».

    Le pire n'est pas l'échec, c'est le message : il faisait croire à un environnement
    cassé là où c'était la CONSIGNE qui l'était. Ce test lie les deux, pour que le
    message et l'outil ne puissent plus diverger."""
    from packages.mlops.environnement import commande_regeneration

    commande = commande_regeneration()
    makefile = (RACINE / "Makefile").read_text(encoding="utf-8")
    cible = makefile.split("verrou-regen:")[1].split("\n\n")[0]
    assert commande in cible, (
        "la commande annoncée par `make verrou` doit être EXACTEMENT celle que "
        f"`make verrou-regen` exécute.\n  annoncée : {commande}\n  cible    : {cible}")


def test_la_commande_utilise_uv_l_outil_du_projet():
    """`make install` utilise `uv`. Régénérer le verrou avec un autre résolveur
    produirait un fichier que l'installateur du projet n'a jamais vu résoudre."""
    from packages.mlops.environnement import commande_regeneration

    commande = commande_regeneration()
    assert commande.startswith("uv pip compile")
    assert "pip-compile" not in commande
    makefile = (RACINE / "Makefile").read_text(encoding="utf-8")
    assert "uv venv && uv pip install" in makefile, "l'installateur reste uv"

