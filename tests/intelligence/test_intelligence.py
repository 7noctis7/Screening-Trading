"""Couche Market Intelligence — les invariants qui empêchent une rumeur de devenir une donnée.

Ces tests fixent des règles de conception, pas des valeurs numériques : chacun correspond à une
façon connue dont un pipeline d'intelligence de marché se trompe.
"""

import pathlib

from packages.intelligence.classify import (EXPLOITABLES, Information, Nature, Statut, classer)
from packages.intelligence.corroboration import Rapport, croiser
from packages.intelligence.pipeline import qualifier
from packages.intelligence.relevance import Categorie, evaluer as pertinence
from packages.intelligence.sources import (Niveau, PLAFOND_NON_VERIFIE, Source, score_source,
                                           utilisable_seule)
from packages.intelligence.watchlist import WATCHLIST, a_verifier, en_source, resume

EXPERT = Source("analyste", Niveau.B_EXPERT, verifie=True, domaines=("macro",))
PRIMAIRE = Source("bce", Niveau.A_PRIMAIRE, verifie=True, domaines=("macro",))
ANON = Source("anon", Niveau.E_FAIBLE, abonnes=5_000_000)


# --- LE NOMBRE D'ABONNÉS N'EST PAS UNE PREUVE -----------------------------------------------

def test_cinq_millions_d_abonnes_ne_battent_pas_une_source_officielle():
    assert score_source(ANON, "macro").valeur < score_source(PRIMAIRE, "macro").valeur / 4


def test_la_contribution_des_abonnes_est_bornee():
    petit = Source("x", Niveau.B_EXPERT, verifie=True, abonnes=100_000)
    enorme = Source("y", Niveau.B_EXPERT, verifie=True, abonnes=50_000_000)
    assert score_source(enorme).valeur - score_source(petit).valeur <= 0.09


def test_abonnes_inconnus_ne_valent_pas_zero_abonne_mais_ne_rapportent_rien():
    a = Source("a", Niveau.B_EXPERT, verifie=True, abonnes=None)
    b = Source("b", Niveau.B_EXPERT, verifie=True, abonnes=1_000)
    assert score_source(a).valeur == score_source(b).valeur


def test_compte_non_authentifie_est_plafonne():
    fort = Source("z", Niveau.A_PRIMAIRE, verifie=False, abonnes=20_000_000,
                  domaines=("macro",), exactitude_passee=1.0)
    assert score_source(fort, "macro").valeur == PLAFOND_NON_VERIFIE


def test_hors_de_son_domaine_un_expert_perd_du_credit():
    assert score_source(EXPERT, "crypto").valeur < score_source(EXPERT, "macro").valeur


def test_seule_une_source_primaire_authentifiee_suffit_seule():
    assert utilisable_seule(PRIMAIRE)
    assert not utilisable_seule(EXPERT)
    assert not utilisable_seule(Source("x", Niveau.A_PRIMAIRE, verifie=False))


def test_le_score_est_decomposable():
    """« Pourquoi 0,90 et pas 0,45 ? » doit avoir une réponse écrite, pas un nombre nu."""
    sc = score_source(PRIMAIRE, "macro")
    assert len(sc.detail) >= 4 and "TOTAL" in sc.explication()


# --- UNE OPINION NE DEVIENT JAMAIS UN FAIT --------------------------------------------------

def test_opinion_d_une_source_parfaite_reste_une_opinion():
    op = Information("Le marché est survalorisé", PRIMAIRE, Nature.OPINION)
    c = classer(op, corroborations=99, corroboration_primaire=True)
    assert c.statut is Statut.OPINION and not c.exploitable


def test_prediction_reste_speculation():
    p = Information("Le S&P fera 8000 en 2027", PRIMAIRE, Nature.PREDICTION)
    assert classer(p, corroborations=99).statut is Statut.SPECULATION


def test_exigence_de_preuve_croit_avec_l_impact():
    faible = Information("t", EXPERT, Nature.FACTUELLE, impact_potentiel="faible")
    fort = Information("t", EXPERT, Nature.FACTUELLE, impact_potentiel="fort")
    assert classer(faible, corroborations=1).statut is Statut.CONFIRMED
    assert classer(fort, corroborations=1).statut is Statut.PROBABLE
    assert classer(fort, corroborations=3).statut is Statut.CONFIRMED


def test_une_information_non_corroboree_reste_unconfirmed():
    i = Information("t", EXPERT, Nature.FACTUELLE, impact_potentiel="fort")
    c = classer(i, corroborations=0)
    assert c.statut is Statut.UNCONFIRMED and c.statut not in EXPLOITABLES


# --- LES ÉCHOS NE SONT PAS DES CONFIRMATIONS ------------------------------------------------

def test_trois_reprises_de_la_meme_origine_ne_font_pas_trois_confirmations():
    e2 = Source("expert2", Niveau.B_EXPERT, verifie=True)
    e3 = Source("expert3", Niveau.B_EXPERT, verifie=True)
    b = croiser([Rapport(EXPERT, "Reuters"), Rapport(e2, "Reuters"), Rapport(e3, "Reuters")])
    assert b.independantes == 1 and len(b.ecartees) == 2


def test_le_meme_compte_deux_fois_ne_compte_qu_une_fois():
    assert croiser([Rapport(EXPERT), Rapport(EXPERT)]).independantes == 1


def test_niveaux_D_et_E_ne_confirment_jamais():
    d = Source("d", Niveau.D_SECONDAIRE)
    b = croiser([Rapport(d), Rapport(ANON), Rapport(Source("d2", Niveau.D_SECONDAIRE))])
    assert b.independantes == 0


def test_une_source_primaire_authentifiee_est_signalee():
    assert croiser([Rapport(PRIMAIRE)]).primaire is True
    assert croiser([Rapport(EXPERT)]).primaire is False


# --- PERTINENCE : PAS LA VIRALITÉ -----------------------------------------------------------

def test_le_bruit_promotionnel_est_ecarte():
    p = pertinence("1000x garanti, airdrop gratuit, lien en bio", "fort", ("DOGE",))
    assert not p.retenue


def test_sans_sujet_de_marche_la_pertinence_est_nulle():
    assert pertinence("Mon chat a renversé mon café", "fort", ("SPY",)).score == 0.0
    assert categorie_hors_sujet()


def categorie_hors_sujet():
    return Categorie.HORS_SUJET in pertinence("rien de financier").categories


# --- WATCHLIST : AUCUNE IDENTITÉ INVENTÉE ---------------------------------------------------

def test_aucun_compte_de_la_watchlist_n_est_declare_verifie():
    assert WATCHLIST and all(not en_source(c).verifie for c in WATCHLIST)
    assert all(en_source(c).abonnes is None for c in WATCHLIST)
    assert resume()["authentifies"] == 0


def test_tous_les_comptes_restent_a_verifier():
    assert len(a_verifier()) == len(WATCHLIST)


def test_source_primaire_est_contextuelle():
    """Un dirigeant est source primaire sur SON entreprise, pas sur la macro."""
    musk = next(c for c in WATCHLIST if c.handle == "elonmusk")
    assert en_source(musk, "résultats Tesla").niveau is Niveau.A_PRIMAIRE
    assert en_source(musk, "inflation américaine").niveau is Niveau.B_EXPERT


def test_un_handle_non_resoluble_est_signale_comme_tel():
    assert "Jensen Huang" in resume()["handles_a_resoudre"]


# --- SÉPARATION STRUCTURELLE ----------------------------------------------------------------

def test_la_couche_intelligence_ne_peut_pas_atteindre_un_courtier():
    """Garantie ARCHITECTURALE, pas conventionnelle : aucune information, si bien notée
    soit-elle, ne peut produire un ordre depuis cette couche.

    On inspecte l'ARBRE SYNTAXIQUE, pas le texte : une première version cherchait la chaîne
    « packages.execution » dans le fichier et se déclenchait sur les commentaires qui
    expliquent justement l'interdiction. Un test qui confond une mention et un import ne teste
    pas l'architecture, il teste la prose."""
    import ast

    racine = pathlib.Path(__file__).resolve().parents[2] / "packages" / "intelligence"
    interdits = ("packages.execution", "packages.risk")
    fichiers = list(racine.glob("*.py"))
    assert fichiers, "aucun module d'intelligence trouvé — le test ne prouverait rien"
    for f in fichiers:
        for noeud in ast.walk(ast.parse(f.read_text(encoding="utf-8"), filename=str(f))):
            if isinstance(noeud, ast.Import):
                cibles = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                cibles = [noeud.module or ""]
            else:
                continue
            for c in cibles:
                assert not any(c.startswith(i) for i in interdits), (
                    f"{f.name} importe « {c} » — la séparation intelligence/exécution est rompue")


# --- CHAÎNE COMPLÈTE ------------------------------------------------------------------------

def test_communique_officiel_pertinent_est_exploitable():
    i = Information("La BCE relève ses taux, inflation au-dessus de la cible", PRIMAIRE,
                    Nature.FACTUELLE, sujet="macro", actifs=("TLT",), impact_potentiel="fort")
    v = qualifier(i, domaine="macro")
    assert v.exploitable and v.classement.statut is Statut.FACT and v.confiance > 0.5


def test_rumeur_virale_anonyme_n_est_jamais_exploitable():
    i = Information("Rumeur : ETF approuvé demain", ANON, Nature.RUMEUR, sujet="crypto",
                    actifs=("BTC",), impact_potentiel="fort")
    v = qualifier(i, [Rapport(ANON)], domaine="crypto")
    assert not v.exploitable and v.corroboration.independantes == 0
    assert "RUMOR" in v.rapport()


def test_le_verdict_nomme_toujours_la_raison_du_refus():
    i = Information("Le marché est cher", EXPERT, Nature.OPINION, sujet="actions")
    assert qualifier(i).motifs
