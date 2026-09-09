"""Cohérence entre le STATUT déclaré d'un module et sa place réelle (hors-ligne)."""

from pathlib import Path

from packages.common.certification import (
    atteignables,
    declarés_shadow,
    incoherences,
    inventaire,
)

RACINE = Path(__file__).resolve().parents[2]


def _faux_depot(tmp_path, *, shadow_en_prod: bool):
    """Dépôt minimal : une entrée de prod, un module intermédiaire, un module SHADOW."""
    (tmp_path / "packages" / "risk").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "packages" / "__init__.py").write_text("")
    (tmp_path / "packages" / "risk" / "__init__.py").write_text("")
    (tmp_path / "packages" / "risk" / "moteur.py").write_text(
        "from packages.risk.fantome import x\n" if shadow_en_prod else "x = 1\n")
    (tmp_path / "packages" / "risk" / "fantome.py").write_text(
        '"""Doc."""\nSTATUT = "SHADOW_UNCALIBRATED"\n')
    (tmp_path / "scripts" / "run_live.py").write_text(
        "from packages.risk.moteur import x\n")
    return tmp_path


def test_un_module_SHADOW_atteignable_depuis_la_prod_est_signale(tmp_path):
    """LE cas bloquant. Le statut « aucun appelant en production » était vrai le jour où
    il a été écrit ; un import ajouté plus tard le rend faux, et rien ne le revérifiait.
    L'atteignabilité est TRANSITIVE : ici run_live → moteur → fantôme, deux sauts."""
    v = _faux_depot(tmp_path, shadow_en_prod=True)
    assert incoherences(v) == ["packages.risk.fantome"]
    assert inventaire(v)["ok"] is False


def test_un_module_SHADOW_inatteignable_n_est_PAS_une_incoherence(tmp_path):
    """C'est de la dette, pas un défaut : on la COMPTE, on ne bloque pas dessus.
    Confondre les deux ferait d'un inventaire à trancher une alarme permanente."""
    v = _faux_depot(tmp_path, shadow_en_prod=False)
    assert incoherences(v) == []
    inv = inventaire(v)
    assert inv["ok"] is True and inv["n_shadow"] == 1 and inv["dette_lignes"] == 2


def test_un_import_DANS_une_fonction_compte_autant(tmp_path):
    """Le dépôt importe massivement à l'intérieur des fonctions pour alléger les
    démarrages. Ne lire que les imports de tête raterait la majorité des liens réels."""
    v = _faux_depot(tmp_path, shadow_en_prod=False)
    (v / "packages" / "risk" / "moteur.py").write_text(
        "def f():\n    from packages.risk.fantome import x\n    return x\n")
    assert incoherences(v) == ["packages.risk.fantome"]


def test_le_depot_REEL_ne_porte_aucune_incoherence():
    """Contrôle sur le vrai dépôt : aucun module ne doit mentir sur son statut."""
    assert incoherences(RACINE) == []


def test_le_depot_REEL_declare_bien_ses_modules_SHADOW():
    """Verrou d'inventaire : la liste est connue et suivie au TODO. Si elle change sans
    qu'on le veuille — un STATUT ajouté ou retiré à la légère — ce test le dit."""
    attendus = {
        "packages.execution.frictions", "packages.indicators.liquidite_ict",
        "packages.ml.caracteristiques_swing",
        "packages.risk.ddm", "packages.risk.garde_swing",
        "packages.strategies.moteur_sortie", "packages.strategies.moteur_swing",
    }
    assert set(declarés_shadow(RACINE)) == attendus


def test_les_points_d_entree_de_prod_atteignent_bien_le_coeur():
    """Contrôle NÉGATIF du calcul lui-même : si `atteignables` renvoyait un ensemble
    vide ou minuscule, `incoherences` serait vide POUR UNE MAUVAISE RAISON et le test
    du dépôt réel passerait au vert en ne mesurant rien."""
    joignables = atteignables(RACINE)
    assert len(joignables) > 50, len(joignables)
    assert "packages.risk.limits" in joignables
    assert "packages.execution.market_calendar" in joignables
