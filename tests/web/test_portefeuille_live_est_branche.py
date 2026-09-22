"""Le bloc « COURTIER » de la page Positions : branché, et honnête sur ce qu'il montre.

Le bandeau du site annonçait « LIVE · il y a 15min ». Ces quinze minutes ne sont pas un
retard de la donnée : c'est la période de reconstruction du snapshot, qui recalcule
aussi
tout le screening — lequel lit des barres QUOTIDIENNES et ne bougerait pas d'un chiffre.
Le portefeuille, lui, bouge à chaque seconde de séance.

Ces tests vérifient le CÂBLAGE, pas le rendu : une règle correcte mais non branchée ne
protège rien, et un composant jamais importé ne montre rien.
"""

from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
WEB = RACINE / "apps" / "web"
COMPOSANT = (WEB / "components" / "PortefeuilleLive.tsx").read_text(encoding="utf-8")
PAGE = (WEB / "app" / "positions" / "page.tsx").read_text(encoding="utf-8")
API = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")


def test_le_hook_interroge_la_route_legere_et_pas_le_snapshot():
    assert 'q("portefeuille", "/api/portefeuille"' in API
    # 30 s : le rythme de la séance, pas celui du snapshot (900 s).
    assert 'q("portefeuille", "/api/portefeuille", 30000)' in API


def test_le_composant_est_REELLEMENT_importe_par_la_page():
    """Un composant écrit et jamais monté est un correctif qui n'existe pas."""
    assert 'import { PortefeuilleLive }' in PAGE
    assert "<PortefeuilleLive />" in PAGE


def test_l_age_affiche_est_celui_de_la_DONNEE_pas_de_la_requete():
    """Le défaut déjà corrigé sur `LiveBadge` : il lisait `dataUpdatedAt`, l'instant
    de la requête, et affichait « il y a 1s » sur des positions vendues un quart
    d'heure plus tôt. L'âge serveur doit être ADDITIONNÉ au temps écoulé depuis la
    réponse."""
    assert "data.age_s" in COMPOSANT and "dataUpdatedAt" in COMPOSANT
    assert "Date.now() - dataUpdatedAt" in COMPOSANT


def test_un_total_INCOMPLET_ne_se_presente_jamais_comme_un_total():
    """ABSENT n'est pas ZÉRO : un total amputé d'un courtier muet ressemble à une
    perte."""
    assert "data.complet" in COMPOSANT
    assert "INCOMPLET" in COMPOSANT and "incidents" in COMPOSANT


def test_les_lignes_non_chiffrees_par_le_courtier_sont_CITEES():
    assert "sans_valeur" in COMPOSANT


def test_le_composant_DIT_que_le_reste_de_la_page_a_un_autre_rythme():
    """Mélanger un compte lu à la seconde et une cible recalculée une fois par jour sous
        un même mot « LIVE » était le vrai défaut. Les deux natures doivent être
    étiquetées."""
    assert "CIBLE du modèle" in COMPOSANT and "courtier" in COMPOSANT.lower()


def test_le_composant_ne_valorise_RIEN_lui_meme():
    """Aucun calcul de prix côté front : il affiche ce que le courtier a chiffré, ou
    « — ». Un repli sur une valeur inventée est exactement ce que le mandat
    données-réelles interdit."""
    for invente in ("* qty", "qty *", "prix *", "* prix"):
        assert invente not in COMPOSANT
