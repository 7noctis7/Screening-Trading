"""« Périmé » et « en train d'être refait » ne sont pas la même chose.

Le 22/09, le bandeau affichait `DIFFÉRÉ · il y a 33min` alors que le serveur
reconstruisait justement le snapshot. Mesuré dans son journal : trois quarts d'heure de
DIFFÉRÉ, et **pas un seul** `snapshot rebuild failed`. Le mot alarmant décrivait la
situation la plus ordinaire du système — celle qui suit chaque redémarrage ou chaque
visite après une période creuse, puisque la reconstruction n'est déclenchée QUE par une
requête du front.

Une alarme qui se déclenche sur le cas normal cesse d'être lue le jour où elle a raison.
C'est tout l'enjeu : rendre à DIFFÉRÉ un sens qu'il vaille la peine de regarder.

Ce que ces tests épinglent :
  1. l'API transmet l'ÉTAT du snapshot, pas seulement son âge ;
  2. elle le fait avec le vocabulaire de `apps.api.sante` — /health et le bandeau ne
     décrivent pas le même serveur avec deux mots différents ;
  3. le badge dit MAJ EN COURS pendant une reconstruction ;
  4. DIFFÉRÉ est réservé au cas « périmé ET personne ne reconstruit » — qui, la
     reconstruction étant déclenchée par la requête elle-même, ne devrait pas exister ;
  5. le va-et-vient du NAVIGATEUR ne change pas le mot : il n'est pas un diagnostic.
"""

from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BADGE = (RACINE / "apps" / "web" / "components" / "LiveBadge.tsx").read_text(
    encoding="utf-8")
MAIN = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")


def _corps_dashboard() -> str:
    for n in ast.walk(ast.parse(MAIN)):
        if isinstance(n, ast.FunctionDef) and n.name == "dashboard":
            return "\n".join(ast.unparse(x) for x in n.body)
    raise AssertionError("route `dashboard` introuvable")


def test_l_api_transmet_l_ETAT_du_snapshot_et_pas_seulement_son_age():
    """Le front ne peut pas le déduire : il ignore si un fil tourne côté serveur."""
    code = _corps_dashboard()
    assert "snapshot_etat" in code
    assert "_BUILDING" in code, "l'état doit venir du drapeau RÉEL de reconstruction"


def test_l_api_reutilise_le_vocabulaire_de_sante():
    """Deux vocabulaires pour le même serveur, c'est deux vérités à rapprocher à la main
    le jour où l'une des deux se trompe."""
    code = _corps_dashboard()
    assert "etat(" in code and "sante" in code


def test_le_badge_dit_MAJ_EN_COURS_pendant_une_reconstruction():
    assert "MAJ EN COURS" in BADGE
    assert 'snapshot_etat === "pret_rafraichissement"' in BADGE


def test_DIFFERE_est_reserve_au_cas_ou_PERSONNE_ne_reconstruit():
    """Sinon le mot décrit la situation la plus ordinaire du système, et ne veut plus
    rien dire quand la reconstruction échoue vraiment."""
    assert "const bloque = perime && !refait;" in BADGE
    assert '"DIFFÉRÉ"' in BADGE
    # le rouge non plus ne se déclenche pas sur une reconstruction en cours
    assert "ttl * 2 && !refait" in BADGE


def test_le_va_et_vient_du_navigateur_ne_change_pas_le_MOT():
    """`isFetching` est le sondage du front toutes les 15 s. Le laisser piloter le mot
    remplacerait un diagnostic par un clignotement."""
    ligne = [x for x in BADGE.splitlines()
             if x.strip().startswith("const mot =")][0]
    assert "isFetching" not in ligne


def test_l_infobulle_du_cas_BLOQUE_donne_la_commande_qui_tranche():
    """Un voyant qui alarme sans dire quoi regarder fait perdre le temps qu'il prétend
    faire gagner."""
    assert "snapshot rebuil" in BADGE and "logs/app.log" in BADGE
