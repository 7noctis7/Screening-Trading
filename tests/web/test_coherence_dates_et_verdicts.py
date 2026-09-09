"""Trois dates d'arrêté sur un même site, et personne pour le dire au lecteur.

Constaté le 04/09 par l'inventaire du gate de publication : le tableau de bord et
les données étaient datés du 18/06, les événements et les thèmes du 04/09, le tri
du 02/09. Certaines de ces divergences sont LÉGITIMES — une fenêtre de mesure
close ne bouge plus, la crypto cote le samedi quand les actions non. En faire une
règle bloquante produirait donc un faux positif chaque week-end.

Mais l'inventaire ne sortait que dans les journaux de fabrication, où personne ne
va le lire. À l'écran : rien. Un visiteur qui comparait deux onglets croyait
comparer deux photos du même instant.

Ce fichier garde les deux bouts de la correction :
  1. l'API publie l'inventaire (`meta.arretes`) et la date la plus fraîche ;
  2. `/api/universe` ne se déclare plus frais du jour même.

Le second point était le plus sournois. `as_of` y valait `datetime.now()` : la
liste d'actifs s'affirmait à jour à chaque fabrication, quel que soit l'âge réel
de ses fichiers sources. Une fraîcheur affirmée sans être vraie est pire qu'une
date ancienne assumée — elle empêche de repérer la source qui a cessé d'être
rafraîchie, et elle fausse l'inventaire censé la surveiller.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SNAPSHOT = (RACINE / "apps" / "api" / "snapshot.py").read_text(encoding="utf-8")
MAIN = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
WEB = RACINE / "apps" / "web"

_ANCRE = '"rebuild_cadence_days"'


def test_l_univers_ne_se_declare_plus_frais_du_jour() -> None:
    """`as_of` dit de QUAND datent les données, jamais quand la page a été faite."""
    fin = SNAPSHOT.index(_ANCRE)
    bloc = SNAPSHOT[fin - 900 : fin]
    assert '"as_of": datetime.now(UTC).isoformat()' not in bloc, (
        "L'univers republie `now()` comme date de données : il se déclarera frais "
        "du jour même si ses fichiers sources n'ont pas bougé depuis des mois."
    )
    assert '"genere_le"' in bloc, (
        "La date de FABRICATION doit rester publiée sous son propre nom — elle est "
        "utile, elle n'est simplement pas la date des données."
    )


def test_l_inventaire_des_dates_est_publie() -> None:
    """Sans inventaire, une page ne peut pas dire qu'elle est en retard sur le site."""
    assert '"arretes"' in SNAPSHOT and '"arrete_le_plus_frais"' in SNAPSHOT, (
        "L'inventaire des dates d'arrêté n'est plus publié dans `meta` : les pages "
        "ne peuvent plus signaler leur retard sur le reste du site."
    )
    assert "dates_d_arrete" in SNAPSHOT, (
        "L'inventaire doit réutiliser `coherence_site.dates_d_arrete`, pas une "
        "seconde implémentation qui dériverait de la première."
    )


def test_la_fenetre_d_exclusion_vient_du_moteur() -> None:
    """Le calendrier affiche « écartée » avec LA constante du moteur, pas une copie.

    Deux nombres — un côté moteur, un côté affichage — dériveraient l'un de l'autre
    au premier réglage : le site dirait alors deux choses du même titre."""
    assert "from packages.portfolio.filtre_resultats import FENETRE_DEFAUT" in MAIN, (
        "La fenêtre d'exclusion doit être IMPORTÉE du moteur, jamais recopiée."
    )
    assert '"blackout_jours"' in MAIN, (
        "La fenêtre n'est plus publiée : le calendrier ne peut plus la dire."
    )


def test_le_screener_conclut_avec_le_moteur_de_la_fiche() -> None:
    """Un verdict « version liste » plus permissif serait pire que pas de verdict :
    deux réponses au même titre selon la page qu'on ouvre."""
    verdicts = (WEB / "lib" / "verdicts.ts").read_text(encoding="utf-8")
    screener = (WEB / "app" / "screener" / "page.tsx").read_text(encoding="utf-8")
    assert 'from "@/lib/decision"' in verdicts, (
        "La jointure doit appeler `decide()`, le moteur de la fiche — jamais "
        "réimplémenter ses seuils."
    )
    assert re.search(r"\bdecide\(", verdicts), "`decide()` n'est plus appelé."
    assert "useVerdicts" in screener, (
        "Le screener ne conclut plus : il est redevenu un simple classement."
    )
