"""Le nom du modèle est une DONNÉE de la mesure, pas un réglage d'affichage.

Ce qui est vérifié ici tient en une phrase : aucun identifiant de modèle n'est inventé.
Il est demandé au fournisseur, ou il est explicitement demandé par l'utilisateur — et
quand il y a ambiguïté, PERSONNE ne tranche en silence.

POURQUOI ÇA COMPTE ICI PLUS QU'AILLEURS. `alpha_nlp_lab` inscrit ce nom dans la mesure qui
décidera du poids donné au NLP. Un signal estampillé d'un modèle qui ne l'a pas produit
n'est pas un détail cosmétique : c'est une mesure qu'on ne pourra plus refaire.
"""

import asyncio

from packages.nlp.config import MODELE_DEFAUT, ConfigNLP
from packages.nlp.moteur import MoteurNLP
from packages.nlp.pilotes import resoudre_modele
from packages.nlp.sante import EN_LIGNE, _verdict

BON = {"ticker": "AAPL", "sentiment": "BULLISH", "confidence_score": 0.7,
       "impact_horizon": "SWING", "catalyst_summary": "Résultats."}


class Fournisseur:
    """Expose une liste et rien d'autre — c'est tout ce que la résolution consulte."""

    nom = "factice"

    def __init__(self, charges, lever=False, modele=""):
        self._charges, self._lever, self.modele = charges, lever, modele

    def modeles(self):
        if self._lever:
            raise RuntimeError("fournisseur muet")
        return list(self._charges)

    def disponible(self, timeout=3.0):
        return True

    def classer(self, systeme, utilisateur, timeout):
        return BON


# ─── Le nom demandé ────────────────────────────────────────────────────────────────────

def test_un_modele_demande_et_expose_revient_tel_quel():
    m, motif = resoudre_modele(Fournisseur(["qwen3-9b", "gemma-2-2b"]), "qwen3-9b")
    assert m == "qwen3-9b" and "exposé" in motif


def test_un_nom_approximatif_est_CANONISE_vers_l_identifiant_du_fournisseur():
    """« qwen3.5 » n'existe nulle part ; l'identifiant exact, si. C'est lui qui part dans
    la requête, et c'est lui qui doit être estampillé."""
    m, motif = resoudre_modele(Fournisseur(["qwen3.5-9b-instruct-mlx", "gemma-2-2b"]),
                               "qwen3.5")
    assert m == "qwen3.5-9b-instruct-mlx"
    assert "identifiant exact" in motif


def test_un_nom_AMBIGU_ne_choisit_RIEN():
    """Deux correspondances, c'est une question, pas un défaut de configuration. Choisir
    le premier reviendrait à décider à la place de l'utilisateur, en silence."""
    charges = ["qwen3-9b-instruct", "qwen3-9b-thinking"]
    m, motif = resoudre_modele(Fournisseur(charges), "qwen3-9b")
    assert m == "qwen3-9b"                     # inchangé : aucun choix fait
    assert "AUCUN choix" in motif and "2 modèles" in motif


def test_un_nom_absent_est_signale_comme_absent_pas_remplace():
    m, motif = resoudre_modele(Fournisseur(["gemma-2-2b"]), "qwen3-9b")
    assert m == "qwen3-9b" and "ABSENT" in motif


# ─── Aucun nom demandé ─────────────────────────────────────────────────────────────────

def test_un_seul_modele_expose_ne_laisse_aucune_ambiguite():
    m, motif = resoudre_modele(Fournisseur(["gemma-2-2b"]), "")
    assert m == "gemma-2-2b" and "aucune ambiguïté" in motif


def test_plusieurs_exposes_sans_demande_nomme_le_remede():
    m, motif = resoudre_modele(Fournisseur(["a", "b", "c"]), "")
    assert m == "a"
    assert "LOCAL_TRADING_MODEL" in motif and "3 modèles" in motif


def test_aucun_fournisseur_rend_le_vide_et_le_DIT():
    """Le vide doit se distinguer d'un modèle nommé « » : c'est le motif qui le dit."""
    m, motif = resoudre_modele(None, "")
    assert m == "" and "éteint" in motif


def test_un_fournisseur_qui_LEVE_ne_fait_pas_tomber_la_resolution():
    m, motif = resoudre_modele(Fournisseur([], lever=True), "")
    assert m == "" and motif


# ─── Ce que le signal porte VRAIMENT ───────────────────────────────────────────────────

def test_le_signal_est_estampille_du_modele_SERVI_pas_du_souhait_vide():
    """Le cœur du correctif. `cfg.modele` vide + un fournisseur qui expose un modèle :
    le signal doit porter l'identifiant du fournisseur, jamais une chaîne vide."""
    p = Fournisseur(["qwen3.5-9b-instruct-mlx"])
    m = MoteurNLP(cfg=ConfigNLP(modele=""), pilote=None)
    m._pilote_resolu = False          # la résolution paresseuse n'a pas encore eu lieu

    # `choisir()` est court-circuité : ce test porte sur la RÉSOLUTION DU NOM, pas sur la
    # découverte du fournisseur, et aucun test ne doit dépendre d'un port ouvert.
    import packages.nlp.moteur as mod
    ancien = mod.choisir
    mod.choisir = lambda *a, **k: p
    try:
        s = asyncio.run(m.classer("AAPL", "texte"))
    finally:
        mod.choisir = ancien
    assert s.modele == "qwen3.5-9b-instruct-mlx"
    assert m.motif_modele and "seul modèle" in m.motif_modele


def test_un_modele_demande_explicitement_n_est_PAS_ecrase_par_la_decouverte():
    p = Fournisseur(["autre-chose"], modele="demande")
    m = MoteurNLP(cfg=ConfigNLP(modele="demande"), pilote=p)
    s = asyncio.run(m.classer("AAPL", "texte"))
    assert s.modele == "demande"


# ─── La régression qu'on ne veut plus jamais revoir ────────────────────────────────────

def test_AUCUN_identifiant_de_modele_n_est_ecrit_en_dur_dans_la_config():
    """Un nom plausible par défaut est le pire des deux mondes : il fonctionne chez celui
    qui l'a écrit et ment chez tous les autres, sans jamais lever."""
    assert MODELE_DEFAUT == ""
    assert ConfigNLP().modele == ""


def test_le_resume_dit_qu_il_ne_sait_pas_encore():
    assert "à découvrir" in ConfigNLP().resume()


# ─── Le voyant de santé ────────────────────────────────────────────────────────────────

def test_sans_modele_demande_le_voyant_NOMME_celui_qui_serait_servi():
    """`"" in m` est vrai pour TOUT m : sans traitement explicite, le voyant passait au
    vert sans désigner personne."""
    v = _verdict("", ["qwen3.5-9b-instruct-mlx", "gemma-2-2b"], None)
    assert v["etat"] == EN_LIGNE
    assert v["modele_servi"] == "qwen3.5-9b-instruct-mlx"
    assert "qwen3.5-9b-instruct-mlx" in v["motif"]
