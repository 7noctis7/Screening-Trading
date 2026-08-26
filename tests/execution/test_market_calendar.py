"""Calendrier de marché — le garde-fou qui manquait au chemin d'exécution.

Contexte (26/08) : le compte paper contenait le cœur QQQ, huit lignes crypto et
ZÉRO action. Les actions partent en `TimeInForce.DAY` sans `extended_hours`, la
crypto en `GTC` (24/7) : un rebalancement lancé depuis l'Europe tombe à 03 h à
New York, donc seule la crypto se remplit. Aucun contrôle d'horaires n'existait.
"""

from datetime import date, datetime, timezone

from packages.execution.market_calendar import (
    DERNIERE_ANNEE_FERIES,
    est_ferie,
    feries_a_jour,
    is_open,
    prochaine_ouverture,
    raison_fermeture,
)


def _utc(a, m, j, h, mi=0):
    return datetime(a, m, j, h, mi, tzinfo=timezone.utc)


# --- LE cas observé ---------------------------------------------------------

def test_le_cas_du_26_aout_actions_fermees_crypto_ouvert():
    """09:18 CEST = 03:18 ET : l'horodatage exact des captures du compte."""
    t = _utc(2026, 8, 26, 7, 18)
    assert is_open(t, "equity") is False
    assert is_open(t, "crypto") is True
    assert "avant l'ouverture" in raison_fermeture(t, "equity")
    assert raison_fermeture(t, "crypto") == ""


# --- séance régulière -------------------------------------------------------

def test_seance_ouverte_en_plein_apres_midi_ny():
    # mercredi 26/08/2026, 15:00 UTC = 11:00 ET (heure d'été)
    assert is_open(_utc(2026, 8, 26, 15, 0), "equity") is True


def test_bornes_de_seance():
    assert is_open(_utc(2026, 8, 26, 13, 29), "equity") is False   # 09:29 ET
    assert is_open(_utc(2026, 8, 26, 13, 30), "equity") is True    # 09:30 pile
    assert is_open(_utc(2026, 8, 26, 19, 59), "equity") is True    # 15:59 ET
    assert is_open(_utc(2026, 8, 26, 20, 0), "equity") is False    # 16:00 fermé


def test_apres_cloture():
    r = raison_fermeture(_utc(2026, 8, 26, 21, 0), "equity")
    assert "après la clôture" in r


def test_hiver_decalage_horaire_est_pris_en_compte():
    """En janvier l'ET est à UTC−5 : 14:35 UTC = 09:35 ET, donc OUVERT.

    Un offset figé à −4 aurait répondu 10:35 et laissé passer une demi-heure de
    faux « ouvert » chaque hiver.
    """
    assert is_open(_utc(2026, 1, 7, 14, 35), "equity") is True
    assert is_open(_utc(2026, 1, 7, 14, 25), "equity") is False    # 09:25 ET


# --- fermetures -------------------------------------------------------------

def test_week_end():
    sam = _utc(2026, 8, 29, 15, 0)
    assert is_open(sam, "equity") is False
    assert "week-end" in raison_fermeture(sam, "equity")
    assert is_open(sam, "crypto") is True          # le crypto s'en moque


def test_ferie_nyse():
    noel = _utc(2026, 12, 25, 16, 0)               # 11:00 ET, séance sinon
    assert est_ferie(date(2026, 12, 25))
    assert is_open(noel, "equity") is False
    assert "férié" in raison_fermeture(noel, "equity")


# --- prochaine ouverture ----------------------------------------------------

def test_prochaine_ouverture_saute_le_week_end():
    p = prochaine_ouverture(_utc(2026, 8, 29, 15, 0))              # samedi
    assert p.weekday() == 0 and (p.hour, p.minute) == (9, 30)      # lundi


def test_prochaine_ouverture_saute_un_ferie():
    p = prochaine_ouverture(_utc(2026, 12, 24, 21, 0))             # veille Noël
    assert not est_ferie(p.date()) and p.weekday() < 5


def test_prochaine_ouverture_le_jour_meme_si_avant_930():
    p = prochaine_ouverture(_utc(2026, 8, 26, 7, 18))              # 03:18 ET
    assert p.date() == date(2026, 8, 26) and (p.hour, p.minute) == (9, 30)


# --- péremption -------------------------------------------------------------

def test_table_des_feries_couvre_l_annee_en_cours():
    """Un garde-fou qui se périme en silence rassure sans protéger.

    Quand ce test casse, AJOUTER l'année suivante à FERIES_NYSE.
    """
    assert feries_a_jour(_utc(DERNIERE_ANNEE_FERIES, 6, 1, 15))
    assert not feries_a_jour(_utc(DERNIERE_ANNEE_FERIES + 1, 6, 1, 15))
