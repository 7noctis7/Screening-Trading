"""Le bandeau « LIVE » mesurait l'aller-retour réseau, pas l'âge de la donnée.

CE QUE CES TESTS PROTÈGENT. `LiveBadge` calculait son « il y a Ns » depuis
`dataUpdatedAt` — l'instant où le NAVIGATEUR a interrogé l'API. Or l'API répond
instantanément depuis un cache serveur (`_TTL_S`, 15 min) rafraîchi en arrière-plan.
Le badge affichait donc « LIVE · il y a 1s », point vert pulsant, sur un snapshot vieux
d'un quart d'heure. Constaté sur la page Positions : dix-huit lignes affichées comme
détenues alors qu'elles avaient été VENDUES treize minutes plus tôt, et 38 000 $ d'écart
entre la valeur affichée et celle du courtier.

Un indicateur de fraîcheur qui ne regarde pas la donnée est pire qu'aucun indicateur :
il ne se contente pas de ne rien dire, il affirme.

Ces tests lisent la SOURCE : `fastapi` n'est pas installé partout où cette suite tourne,
et un test qui ne s'exécute nulle part ne garde rien (même choix que
`test_fraicheur_univers.py`).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
API = RACINE / "apps" / "api" / "main.py"
BADGE = RACINE / "apps" / "web" / "components" / "LiveBadge.tsx"


def _fonction(nom: str) -> ast.FunctionDef:
    arbre = ast.parse(API.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(arbre)
                if isinstance(n, ast.FunctionDef) and n.name == nom)


# ─────────────────────────── côté serveur ───────────────────────────

def test_le_dashboard_publie_l_age_du_snapshot():
    src = ast.unparse(_fonction("dashboard"))
    assert "snapshot_age_s" in src
    assert "snapshot_ttl_s" in src


def test_l_age_est_CALCULÉ_depuis_l_horodatage_du_cache():
    """Une constante ou un zéro ferait un indicateur toujours vert."""
    src = ast.unparse(_fonction("dashboard"))
    assert "_CACHE_TS" in src, "l'âge doit venir de l'horodatage réel du cache"
    assert "time.time()" in src


def test_l_age_ne_peut_pas_etre_negatif():
    """Une horloge qui recule ne doit pas produire « il y a -3s »."""
    assert "max(0.0" in ast.unparse(_fonction("dashboard"))


# ─────────────────────────── côté front ───────────────────────────

def test_le_badge_lit_l_age_SERVEUR():
    assert "snapshot_age_s" in BADGE.read_text(encoding="utf-8")


def test_le_badge_ne_se_fie_plus_au_seul_instant_de_requete():
    """`dataUpdatedAt` reste utile — pour AJOUTER le temps écoulé depuis la réponse.

    Ce qui est interdit, c'est qu'il soit la SEULE source de l'âge affiché.
    """
    txt = BADGE.read_text(encoding="utf-8")
    assert "dataUpdatedAt" in txt
    calculs = [ln for ln in txt.splitlines()
               if "dataUpdatedAt" in ln and "Date.now()" in ln]
    assert calculs, "le temps écoulé depuis la réponse doit bien être ajouté"
    assert all("ageServeur" in ln or "snapshot_age_s" in ln or "?" in ln
               for ln in calculs), "l'âge ne doit pas se déduire de la seule requête"


def test_le_badge_sait_dire_qu_il_n_est_PAS_live():
    """Vert et « LIVE » quoi qu'il arrive, c'est une affirmation, pas une mesure."""
    txt = BADGE.read_text(encoding="utf-8")
    assert "DIFFÉRÉ" in txt
    assert "snapshot_ttl_s" in txt, "le seuil vient du serveur, pas du code front"


def test_le_badge_ne_code_pas_le_ttl_en_dur_sans_repli_explicite():
    """Un 900 codé en dur se désynchroniserait d'un `_TTL_S` changé côté serveur."""
    txt = BADGE.read_text(encoding="utf-8")
    durs = re.findall(r"ttl\s*[:=]\s*(\d+)", txt, re.I)
    assert all("snapshot_ttl_s" in ln
               for ln in txt.splitlines() if re.search(r"\b900\b", ln)), \
        f"900 apparaît hors du repli sur snapshot_ttl_s ({durs})"


def test_les_deux_cotes_parlent_du_meme_champ():
    """Le contrat tient en un nom : si l'un le renomme, l'autre devient muet."""
    serveur = ast.unparse(_fonction("dashboard"))
    front = BADGE.read_text(encoding="utf-8")
    for champ in ("snapshot_age_s", "snapshot_ttl_s"):
        assert champ in serveur and champ in front
