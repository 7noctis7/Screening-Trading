"""Le banc du lexique : sans LLM, et il DIT pourquoi il ne peut pas conclure.

LE DÉFAUT DU 16/09, et il a coûté une soirée. `make alpha-nlp` répondait « Aucun
événement
exploitable : prix absents ou fenêtre trop courte » — une phrase qui ne dit PAS
laquelle des
deux causes s'applique. La machine avait le corpus et pas les prix ; le message envoyait
chercher du côté du LLM, qui n'y était pour rien.

Les deux causes n'ont pas le même remède : un symbole sans barres se règle en ingérant
des
prix, un titre trop récent se règle en ATTENDANT. Les confondre fait croire à une
panne là
où il n'y a que du temps qui n'est pas encore passé.
"""

import pathlib

import pytest

BANC = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "alpha_lexique_lab.py"
SRC = BANC.read_text(encoding="utf-8")


@pytest.fixture
def diagnostic():
    import importlib.util
    spec = importlib.util.spec_from_file_location("banc_lexique", BANC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._diagnostic


CORPUS = [{"symbol": "AAPL"}, {"symbol": "MSFT"}, {"symbol": "XYZ"}]


def test_des_symboles_SANS_PRIX_sont_comptes_et_nommes(diagnostic):
    d = diagnostic(CORPUS, {"AAPL": [1]}, 5)
    assert "3 symbole(s) au corpus" in d and "2 SANS" in d
    assert "MSFT" in d and "XYZ" in d


def test_l_absence_de_prix_renvoie_vers_LA_MACHINE_qui_les_a(diagnostic):
    """Le corpus vit sur le VPS, les prix aussi — c'est le Mac qui n'avait que l'un."""
    d = diagnostic(CORPUS, {}, 5)
    assert "SUR LE VPS" in d or "sur le VPS" in d


def test_avec_TOUS_les_prix_la_cause_est_le_TEMPS_pas_les_donnees(diagnostic):
    """Aucune ambiguïté possible : si toutes les barres sont là, il ne manque que des
    jours de bourse après l'entrée."""
    d = diagnostic(CORPUS, {"AAPL": [1], "MSFT": [1], "XYZ": [1]}, 5)
    assert "les prix sont là" in d
    assert "trop récent" in d and "attendre" in d
    assert "VPS" not in d, "ne pas renvoyer ailleurs quand ce n'est pas la cause"


# ─── Ce que le banc n'est PAS
# ──────────────────────────────────────────────────────────

def test_le_banc_ne_depend_d_AUCUN_fournisseur_de_LLM():
    """C'est sa raison d'être : la chaîne NLP locale a été retirée, la question non."""
    for interdit in ("packages.nlp", "lmstudio", "ollama", "LOCAL_TRADING_MODEL"):
        assert interdit not in SRC


def test_le_banc_refuse_de_parler_sous_un_plancher_d_observations():
    """Une étude d'événement sur quelques dizaines d'observations ne conclut rien, et
    prétendre le contraire serait la pire sortie possible de ce banc."""
    assert "MIN_POUR_PARLER" in SRC
    assert "return 2" in SRC, "il doit SORTIR en erreur, pas afficher un tableau vide"


def test_un_verdict_sans_scoreur_retenu_est_presente_comme_un_RESULTAT():
    assert "RÉSULTAT, pas un" in SRC and "Poids sentiment = 0" in SRC
