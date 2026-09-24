"""Un flux social ne se rejoue pas : chaque jour sans ingestion est perdu pour toujours.

`t.me/s/<canal>` ne rend qu'une vingtaine de messages, un miroir RSS guère plus. Sur un
canal actif, une semaine sans passage fait SORTIR les messages de la fenêtre — et aucune
relance ne les rattrape. C'est ce qui distingue cette tâche de celles qu'on lance quand
on y pense : son coût augmente avec le retard.

Le dépôt encode déjà ce raisonnement pour le corpus de news, dans le même fichier. Ces
tests vérifient que le flux social l'a rejoint, et aux mêmes conditions.

Ce qu'ils épinglent :
  1. l'ingestion est dans la chaîne QUOTIDIENNE, pas dans un script qu'on oublie ;
  2. chaque source ne tourne que si elle est CONFIGURÉE — sinon le log se remplirait
     d'échecs attendus, et un vrai échec s'y noierait — et cette question se pose LÀ
     OÙ `.env` est lu, c'est-à-dire en Python, jamais dans le shell ;
  3. un échec est VISIBLE, jamais avalé par un `|| true` — c'est la leçon que ce fichier
     s'est déjà écrite à lui-même à propos de `train_model.py` ;
  4. l'ingestion ne peut pas faire TOMBER la chaîne : les rapports et la watchlist qui
     la suivent ne dépendent pas d'elle.
"""
from __future__ import annotations

import re
from pathlib import Path

CRON = Path(__file__).resolve().parents[2] / "scripts" / "cron_daily.sh"


def _texte() -> str:
    return CRON.read_text(encoding="utf-8")


def _code() -> str:
    """Le script SANS ses commentaires.

    Les deux tests de garde ci-dessous cherchent ce que le script FAIT. La prose qui
    explique pourquoi la garde n'est plus en shell cite forcément la forme qu'elle
    avait — et sans cette séparation, l'explication d'un défaut déclencherait le test
    qui interdit ce défaut.
    """
    lignes = _texte().splitlines()
    return "\n".join(x for x in lignes if not x.lstrip().startswith("#"))


def test_l_ingestion_sociale_est_dans_la_chaine_QUOTIDIENNE():
    assert "social_x_ingest.py" in _texte(), (
        "un flux qu'on doit penser à rafraîchir cesse d'être rafraîchi")


def test_les_TROIS_sources_reseau_sont_branchees():
    code = _texte()
    for source in ("--source telegram", "--source rss", "--source discord"):
        assert source in code, source


def test_chaque_source_ne_tourne_QUE_si_elle_est_configuree():
    """Sans garde, le log se remplirait chaque jour d'un échec attendu."""
    assert _code().count("--si-configuree") == 3


def test_la_garde_n_est_PAS_ecrite_dans_le_SHELL():
    """La première version testait les variables en bash. Elle était FAUSSE, et muette.

    `.env` n'est lu qu'en Python (`packages/common/env.py`). Sous cron — dont
    l'environnement est nu — `[ -n "${QUANT_TG_CANAUX:-}" ]` est toujours faux : les
    trois sources auraient été sautées chaque nuit, sans une ligne dans le log. Une
    garde placée au mauvais étage n'assainit pas la tâche, elle l'éteint.

    Ce test épingle l'étage, pas la syntaxe : la question « ai-je de quoi lire ? » se
    pose là où la configuration est LUE.
    """
    code = _code()
    for variable in ("QUANT_TG_CANAUX", "QUANT_X_RSS", "QUANT_DISCORD_SALONS",
                     "DISCORD_BOT_TOKEN"):
        assert f'"${{{variable}:-}}"' not in code, (
            f"{variable} testée en shell : vide sous cron, donc source sautée")


def test_un_echec_d_ingestion_est_VISIBLE_jamais_avale():
    """`|| true` seul rendait la panne indétectable — le fichier se l'est déjà écrit."""
    code = _texte()
    for ligne in re.findall(r"^\s*python scripts/social_x_ingest\.py.*$", code,
                            re.MULTILINE):
        assert "|| true" not in ligne, ligne
    # chaque appel est suivi d'un `|| echo` qui NOMME la conséquence
    appels = code.count("python scripts/social_x_ingest.py")
    avertissements = sum(code.count(f"EN ÉCHEC — {q}")
                         for q in ("l'onglet", "miroir", "jeton"))
    assert appels == avertissements == 3, (appels, avertissements)


def test_l_ingestion_ne_peut_pas_faire_TOMBER_la_chaine():
    """Le script est en `set -e` : sans `||`, un canal mort arrêterait tout le reste —
    rapports, watchlist, miroirs — pour une cause sans rapport avec eux."""
    code = _texte()
    assert "set -euo pipefail" in code
    for ligne in re.findall(r"^\s*python scripts/social_x_ingest\.py.*$", code,
                            re.MULTILINE):
        assert ligne.rstrip().endswith("\\"), (
            f"appel sans repli, il arrêterait la chaîne : {ligne}")


def test_la_RAISON_d_etre_quotidienne_est_ECRITE():
    """Une tâche planifiée sans motif écrit finit par être déplacée ou supprimée par
    quelqu'un qui ne sait pas ce qu'elle protège."""
    # Le commentaire shell est enveloppé sur plusieurs lignes, chacune préfixée
    # par `#` :
    # chercher la phrase telle quelle échouerait sur une simple césure, et le test
    # imposerait alors une mise en page au lieu d'un raisonnement.
    prose = re.sub(r"\s+", " ", re.sub(r"^\s*#", "", _texte(), flags=re.MULTILINE))
    assert "PERDUE DÉFINITIVEMENT" in prose
