"""Une série morte se lit comme une série vivante — c'est tout le problème.

Le chômage zone euro affichait 6,7 % daté de janvier 2023 : la série OCDE avait cessé d'être
publiée, FRED servait encore sa dernière valeur, et le code la prenait sans broncher. La date
était affichée, mais rien ne disait qu'elle était anormale — un lecteur qui parcourt une grille
de tuiles lit le chiffre, pas la date.

DEUXIÈME TEMPS (03/09). Le détecteur disait « série arrêtée » pour un simple retard de
publication : le Bund, dernière observation au 01/06, dépassait le seuil d'UN jour (94
contre 93) et portait le même mot que le chômage zone euro, en retard de 1 332 jours —
43 fois sa cadence contre 3,03. Un mot qui désigne les deux ne désigne plus rien, et une
alerte qui clignote au rythme du calendrier de publication apprend à être ignorée.
"""
from datetime import date, timedelta

from packages.macro.fred import _FACTEUR_ARRET, _FACTEUR_RETARD, _retard


def _mensuel(n=4, fin=None):
    """Dates d'une série mensuelle, la plus récente en premier (ordre FRED sort_order=desc)."""
    fin = fin or date.today().replace(day=1)
    return [(fin - timedelta(days=30 * i)).isoformat() for i in range(n)]


def test_serie_mensuelle_a_jour_nest_pas_signalee():
    retard, statut = _retard(_mensuel())
    assert statut == "ok"
    assert retard < 40


def test_serie_arretee_depuis_trois_ans_est_dite_ARRETEE():
    """Le cas réel : chômage zone euro, dernière valeur en 2023 — 43× la cadence."""
    vieux = date.today() - timedelta(days=3 * 365)
    assert _retard(_mensuel(fin=vieux))[1] == "arretee"


def test_un_retard_de_publication_ordinaire_ne_declenche_rien():
    """Une série mensuelle publiée avec un mois de décalage est NORMALE, pas morte."""
    assert _retard(_mensuel(fin=date.today() - timedelta(days=35)))[1] == "ok"


def test_le_bund_est_EN_RETARD_pas_arrete():
    """Le contresens du 03/09. Trois mois sans publication sur une série mensuelle
    publiée avec deux mois de décalage structurel : c'est un retard, pas un arrêt."""
    retard, statut = _retard(_mensuel(n=12, fin=date.today() - timedelta(days=94)))
    assert statut == "retard"
    assert retard >= 94


def test_la_cadence_vient_de_la_serie_pas_dune_table():
    """Quotidienne vs mensuelle : le même retard absolu ne se juge pas pareil."""
    quot = [(date.today() - timedelta(days=20 + i)).isoformat() for i in range(4)]
    mens = _mensuel(fin=date.today() - timedelta(days=20))
    assert _retard(quot)[1] != "ok", "20 jours sans point sur une série quotidienne"
    assert _retard(mens)[1] == "ok", "20 jours sur une série mensuelle = normal"


def test_les_deux_facteurs_sont_documentes_et_ordonnes():
    """L'arrêt doit être STRICTEMENT plus exigeant que le retard, sinon l'un absorbe
    l'autre et la distinction disparaît."""
    assert _FACTEUR_RETARD == 3.0
    assert _FACTEUR_ARRET == 12.0
    assert _FACTEUR_ARRET > _FACTEUR_RETARD


def test_une_seule_observation_ne_permet_pas_de_conclure():
    """Sans deux dates, aucune cadence n'est mesurable : on ne devine pas."""
    retard, statut = _retard([date.today().isoformat()])
    assert statut == "ok" and retard == 0


def test_dates_illisibles_ne_plantent_pas():
    assert _retard(["pas-une-date", "non-plus"]) == (0, "ok")
    assert _retard([]) == (0, "ok")
