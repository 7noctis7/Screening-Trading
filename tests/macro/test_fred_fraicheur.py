"""Une série morte se lit comme une série vivante — c'est tout le problème.

Le chômage zone euro affichait 6,7 % daté de janvier 2023 : la série OCDE avait cessé d'être
publiée, FRED servait encore sa dernière valeur, et le code la prenait sans broncher. La date
était affichée, mais rien ne disait qu'elle était anormale — un lecteur qui parcourt une grille
de tuiles lit le chiffre, pas la date.
"""
from datetime import date, timedelta

from packages.macro.fred import _FACTEUR_RETARD, _retard


def _mensuel(n=4, fin=None):
    """Dates d'une série mensuelle, la plus récente en premier (ordre FRED sort_order=desc)."""
    fin = fin or date.today().replace(day=1)
    return [(fin - timedelta(days=30 * i)).isoformat() for i in range(n)]


def test_serie_mensuelle_a_jour_nest_pas_perimee():
    retard, perimee = _retard(_mensuel())
    assert not perimee
    assert retard < 40


def test_serie_mensuelle_arretee_depuis_trois_ans_est_perimee():
    """Le cas réel : chômage zone euro, dernière valeur en 2023."""
    vieux = date.today() - timedelta(days=3 * 365)
    _, perimee = _retard(_mensuel(fin=vieux))
    assert perimee


def test_un_retard_de_publication_ordinaire_ne_declenche_rien():
    """Une série mensuelle publiée avec un mois de décalage est NORMALE, pas morte."""
    _, perimee = _retard(_mensuel(fin=date.today() - timedelta(days=35)))
    assert not perimee


def test_la_cadence_vient_de_la_serie_pas_dune_table():
    """Quotidienne vs mensuelle : le même retard absolu ne se juge pas pareil."""
    quot = [(date.today() - timedelta(days=20 + i)).isoformat() for i in range(4)]
    mens = _mensuel(fin=date.today() - timedelta(days=20))
    assert _retard(quot)[1], "20 jours sans point sur une série quotidienne = morte"
    assert not _retard(mens)[1], "20 jours sur une série mensuelle = normal"


def test_le_facteur_est_documente():
    assert _FACTEUR_RETARD == 3.0


def test_une_seule_observation_ne_permet_pas_de_conclure():
    """Sans deux dates, aucune cadence n'est mesurable : on ne devine pas."""
    retard, perimee = _retard([date.today().isoformat()])
    assert not perimee and retard == 0


def test_dates_illisibles_ne_plantent_pas():
    assert _retard(["pas-une-date", "non-plus"]) == (0, False)
    assert _retard([]) == (0, False)
