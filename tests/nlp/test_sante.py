"""L'état de la chaîne IA — et le seul état qu'on peut avoir sans s'en apercevoir.

`DEGRADE` : le fournisseur répond, tout a l'air de marcher, et les signaux sont pourtant des
replis. C'est celui-là qu'il faut rendre visible.
"""

import pathlib

from packages.nlp.config import ConfigNLP
from packages.nlp.disjoncteur import Disjoncteur
from packages.nlp.moteur import MoteurNLP
from packages.nlp.sante import DEGRADE, EN_LIGNE, HORS_LIGNE, etat_chaine, etat_modeles

RACINE = pathlib.Path(__file__).resolve().parents[2]


class PiloteAvec:
    nom = "factice"

    def __init__(self, charges):
        self.charges = charges

    def disponible(self, timeout=3.0):
        return True

    def modeles(self, timeout=3.0):
        return self.charges

    def classer(self, systeme, utilisateur, timeout):
        return None


def _moteur(charges, modele="qwen2.5-7b-instruct", disjoncteur=None):
    cfg = ConfigNLP(modele=modele)
    return MoteurNLP(cfg=cfg, pilote=PiloteAvec(charges), disjoncteur=disjoncteur)


# ─── Les trois états ───────────────────────────────────────────────────────────────────

def test_modele_charge_donne_EN_LIGNE():
    e = etat_chaine(_moteur(["qwen2.5-7b-instruct"]))
    assert e["etat"] == EN_LIGNE and e["motif"] == ""


def test_aucun_fournisseur_donne_HORS_LIGNE_avec_les_ports():
    """Sans NLP le reste du système fonctionne : c'est un choix d'architecture, pas une
    panne — mais le motif doit dire où regarder."""
    import packages.nlp.sante as S
    cfg = ConfigNLP(modele="x")
    m = MoteurNLP(cfg=cfg, pilote=None)
    m._pilote_resolu = True
    e = S.etat_chaine(m)
    assert e["etat"] == HORS_LIGNE
    assert "1234" in e["motif"] and "11434" in e["motif"]


def test_le_MAUVAIS_modele_charge_donne_DEGRADE():
    """Le voyant doit tester ce que fera le BOUTON, pas seulement le port. Leçon du 25/08 :
    « connecté » puis 404 dès qu'on génère, parce que le modèle n'était pas celui du
    fournisseur de l'URL."""
    e = etat_chaine(_moteur(["llama3.2:3b", "phi4-mini"], modele="qwen2.5-7b-instruct"))
    assert e["etat"] == DEGRADE
    assert "qwen2.5-7b-instruct" in e["motif"] and "llama3.2:3b" in e["motif"]


def test_aucun_modele_charge_donne_DEGRADE():
    e = etat_chaine(_moteur([]))
    assert e["etat"] == DEGRADE and "aucun modèle" in e["motif"]


def test_le_DISJONCTEUR_OUVERT_donne_DEGRADE_meme_si_tout_repond():
    """L'état le plus trompeur : le fournisseur va bien, le modèle est chargé, et pourtant
    aucun appel ne part."""
    d = Disjoncteur(seuil=1, refroidissement_s=60.0)
    d.echec()
    e = etat_chaine(_moteur(["qwen2.5-7b-instruct"], disjoncteur=d))
    assert e["etat"] == DEGRADE and "disjoncteur OUVERT" in e["motif"]
    assert "réouverture" in e["motif"]


def test_un_nom_de_modele_PARTIEL_est_accepte():
    """LM Studio renvoie parfois un identifiant plus long que celui qu'on demande."""
    e = etat_chaine(_moteur(["lmstudio-community/qwen2.5-7b-instruct-GGUF"],
                            modele="qwen2.5-7b-instruct"))
    assert e["etat"] == EN_LIGNE


# ─── Ne pas sonder ─────────────────────────────────────────────────────────────────────

def test_sonder_False_n_ouvre_AUCUNE_connexion():
    """Une page qui rafraîchit ses métriques toutes les cinq secondes sonderait le
    fournisseur autant de fois : une latence de voyant se prendrait pour une latence de
    modèle."""
    class PiloteQuiRefuseDEtreSonde(PiloteAvec):
        def modeles(self, timeout=3.0):
            raise AssertionError("le fournisseur a été sondé alors que sonder=False")

    m = MoteurNLP(cfg=ConfigNLP(modele="x"), pilote=PiloteQuiRefuseDEtreSonde([]))
    e = etat_chaine(m, sonder=False)
    assert e["etat"] == HORS_LIGNE and "non sondé" in e["motif"]


def test_les_metriques_du_moteur_sont_exposees():
    e = etat_chaine(_moteur(["qwen2.5-7b-instruct"]), sonder=False)
    assert e["metriques"] is not None and "taux_repli" in e["metriques"]
    assert e["disjoncteur"]["etat"] == "CLOSED"


# ─── Versions : elles viennent du REGISTRE ─────────────────────────────────────────────

def test_l_etat_des_modeles_vient_du_registre_pas_d_une_constante():
    """Un numéro de version écrit en dur se détache de ce qu'il désigne — leçon des
    chiffres de la landing (ADR-0154)."""
    src = (RACINE / "packages" / "nlp" / "sante.py").read_text(encoding="utf-8")
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


# ─── Les routes ────────────────────────────────────────────────────────────────────────

def test_les_routes_ai_existent_et_ont_ete_ETENDUES_pas_remplacees():
    """L'audit demandait d'inspecter avant de créer : les quatre routes d'origine restent."""
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    for route in ("/api/ai/status", "/api/ai/diagnostic", "/api/ai/commentary",
                  "/api/ai/metrics", "/api/ai/modeles", "/api/ai/chaine"):
        assert f'@app.get("{route}")' in src


def test_la_route_metrics_NE_SONDE_PAS_le_fournisseur():
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    bloc = src.split('def ai_metrics()', 1)[1].split("@app.get", 1)[0]
    assert "sonder=False" in bloc


def test_l_observabilite_ne_fait_jamais_tomber_la_route():
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    bloc = src.split('def ai_metrics()', 1)[1].split("@app.get", 1)[0]
    assert "except Exception" in bloc
