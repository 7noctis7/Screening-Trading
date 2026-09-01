"""Disjoncteur journalier (spec utilisateur 01/09, module 2.4).

Les deux comportements qui font la différence entre un disjoncteur et une décoration :
le latent compte, et le verrou ne se lève pas sur un rebond.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from packages.risk.disjoncteur import STATUT, DisjoncteurJournalier

T0 = datetime(2026, 9, 1, 14, 0, tzinfo=UTC)


def test_le_module_demarre_en_SHADOW():
    assert STATUT == "SHADOW_UNCALIBRATED"


def test_sous_le_seuil_rien_ne_bouge():
    d = DisjoncteurJournalier(seuil=0.03)
    r = d.observer(T0, 100_000, -2_000)
    assert r["entrees_autorisees"] and not r["fermer_positions"]


def test_au_seuil_tout_est_coupe():
    d = DisjoncteurJournalier(seuil=0.03)
    r = d.observer(T0, 100_000, -3_000)
    assert not r["entrees_autorisees"]
    assert r["fermer_positions"] and r["annuler_ordres"]
    assert "seuil" in r["motif"]


def test_le_LATENT_compte_aussi():
    """Ne compter que le réalisé laisserait un compte fondre sur des positions ouvertes
    sans jamais déclencher — le mode de panne exact qu'un disjoncteur doit empêcher."""
    d = DisjoncteurJournalier(seuil=0.03)
    r = d.observer(T0, 100_000, pnl_realise=-500, pnl_latent=-2_600)
    assert not r["entrees_autorisees"], r


def test_un_REBOND_intrajournalier_ne_deverrouille_PAS():
    """« Bloquer jusqu'au lendemain » veut dire jusqu'au lendemain. Se réarmer sur
    un rebond ferait rentrer dans la volatilité qui a déclenché la coupure."""
    d = DisjoncteurJournalier(seuil=0.03)
    d.observer(T0, 100_000, -3_500)
    r = d.observer(T0 + timedelta(hours=2), 100_000, +2_000)
    assert not r["entrees_autorisees"], "le verrou a sauté sur un rebond"


def test_le_lendemain_rearme():
    d = DisjoncteurJournalier(seuil=0.03)
    d.observer(T0, 100_000, -3_500)
    r = d.observer(T0 + timedelta(days=1), 100_000, 0.0)
    assert r["entrees_autorisees"] and r["perte_jour"] == 0.0


def test_la_bascule_se_fait_a_MINUIT_UTC():
    """23h59 et 00h01 UTC sont deux jours, même à deux minutes d'écart."""
    d = DisjoncteurJournalier(seuil=0.03)
    d.observer(datetime(2026, 9, 1, 23, 59, tzinfo=UTC), 100_000, -3_500)
    assert not d.entrees_autorisees()
    d.observer(datetime(2026, 9, 2, 0, 1, tzinfo=UTC), 100_000, 0.0)
    assert d.entrees_autorisees()


def test_un_horodatage_NAIF_est_refuse():
    """Supposer UTC déplacerait la remise à zéro de plusieurs heures selon le fuseau,
    et le verrou sauterait au mauvais moment."""
    d = DisjoncteurJournalier()
    with pytest.raises(ValueError, match="naïf"):
        d.observer(datetime(2026, 9, 1, 14, 0), 100_000, -5_000)


def test_un_fuseau_non_UTC_est_converti_pas_refuse():
    """Paris 01h30 = 31/08 23h30 UTC : c'est encore la veille côté compteur."""
    paris = timezone(timedelta(hours=2))
    d = DisjoncteurJournalier(seuil=0.03)
    d.observer(datetime(2026, 9, 1, 1, 30, tzinfo=paris), 100_000, -3_500)
    assert d.jour.isoformat() == "2026-08-31"


def test_observer_est_IDEMPOTENT():
    """Appelé deux fois sur les mêmes chiffres, il ne déclenche qu'une fois."""
    d = DisjoncteurJournalier(seuil=0.03)
    for _ in range(3):
        d.observer(T0, 100_000, -3_500)
    assert len(d.declenchements) == 1


def test_seuil_hors_fourchette_refuse():
    """Spec : 2-4 %. Trop lâche ne protège rien, trop serré coupe sur le bruit."""
    for mauvais in (0.005, 0.10):
        with pytest.raises(ValueError, match="fourchette"):
            DisjoncteurJournalier(seuil=mauvais)


def test_equity_nulle_ne_declenche_pas_par_division():
    d = DisjoncteurJournalier(seuil=0.03)
    assert d.observer(T0, 0.0, -100.0)["entrees_autorisees"]
