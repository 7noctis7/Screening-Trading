"""Viser « une heure avant la clôture » sans jamais retoucher le cron.

Une heure de cron fixe ne peut pas y arriver : la clôture de 16 h à New York tombe à
20 h UTC l'été et à 21 h UTC l'hiver, les bascules américaine et européenne ne se
font pas le même dimanche, et la machine peut vivre dans n'importe quel fuseau.
L'installation se réveille donc CHAQUE HEURE et ce garde-fou décide, dans l'heure
du marché.

Ces tests vérifient la seule propriété qui compte : **exactement un** réveil horaire
tombe dans la fenêtre, chaque jour de bourse, été comme hiver — zéro sinon.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.execution.market_calendar import minutes_avant_cloture

RACINE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "fenetre_execution", RACINE / "scripts" / "fenetre_execution.py")
fen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fen)


def _declenchements(jour: str, visee: float = 60.0) -> list[int]:
    """Heures UTC (réveil à la minute 5) où le garde-fou dit « agir », ce jour-là."""
    base = datetime.fromisoformat(jour).replace(tzinfo=UTC)
    return [h for h in range(24)
            if fen.dans_la_fenetre(
                minutes_avant_cloture(base + timedelta(hours=h, minutes=5)), visee)]


@pytest.mark.parametrize(("jour", "saison"), [
    ("2026-07-01", "heure d'été"),
    ("2026-01-15", "heure d'hiver"),
    ("2026-03-10", "juste après la bascule américaine"),
    ("2026-10-28", "entre la bascule européenne et l'américaine"),
    ("2026-11-10", "après les deux bascules"),
])
def test_exactement_un_declenchement_par_seance(jour, saison) -> None:
    """LE test. Zéro déclenchement = le robot ne tourne pas ; deux = il rebalance deux
    fois le même jour. Les deux sont des pannes, et une heure fixe produit l'une ou
    l'autre à chaque changement d'heure."""
    heures = _declenchements(jour)
    assert len(heures) == 1, f"{saison} ({jour}) : {len(heures)} déclenchement(s)"


def test_aucun_declenchement_les_jours_fermes() -> None:
    """Week-ends et fériés NYSE : le calendrier du projet les connaît déjà."""
    assert _declenchements("2026-07-04") == []          # samedi
    assert _declenchements("2026-07-03") == []          # férié (4 juillet observé)
    assert _declenchements("2026-11-26") == []          # Thanksgiving


def test_l_heure_de_declenchement_suit_bien_l_heure_d_ete() -> None:
    """La preuve que le garde-fou ne fige rien : l'heure UTC qui déclenche CHANGE
    entre l'été et l'hiver, ce qu'une ligne de cron ne sait pas faire seule."""
    assert _declenchements("2026-07-01") == [19]        # 15 h à New York
    assert _declenchements("2026-01-15") == [20]        # 15 h à New York aussi


def test_la_cible_est_reglable() -> None:
    """Viser 30 min avant la clôture déplace le déclenchement, ne le supprime pas."""
    assert len(_declenchements("2026-07-01", visee=30.0)) == 1
    assert len(_declenchements("2026-07-01", visee=180.0)) == 1


def test_la_fenetre_est_semi_ouverte() -> None:
    """Fermée des deux côtés, une minute pile sur la borne déclencherait deux fois le
    même jour — le rebalancement partirait en double."""
    # `restant` compte les minutes AVANT la clôture : plus il est grand, plus on est
    # tôt. La fenêtre visant 60 min court donc sur [30, 90) — bornes en « minutes
    # restantes », la borne INCLUSE étant la plus tardive.
    assert fen.dans_la_fenetre(30.0, 60.0) is True      # 30 min avant : inclus
    assert fen.dans_la_fenetre(90.0, 60.0) is False     # 90 min avant : exclu
    assert fen.dans_la_fenetre(29.9, 60.0) is False     # trop près de la clôture
    assert fen.dans_la_fenetre(None, 60.0) is False     # marché fermé


def _passages_crypto(jour: str, heure: int = 0) -> list[int]:
    """Heures UTC où le passage CRYPTO SEUL s'arme, ce jour-là."""
    base = datetime.fromisoformat(jour).replace(tzinfo=UTC)
    return [h for h in range(24)
            if fen.passage_crypto(base + timedelta(hours=h, minutes=5), heure)]


def test_le_crypto_tourne_les_week_ends_et_les_feries() -> None:
    """Le crypto cote 24/7 : un portefeuille qui ne le rebalance que du lundi au
    vendredi dérive tout le week-end, et le lundi il rattrape deux jours d'un coup."""
    assert _passages_crypto("2026-07-04") == [0]       # samedi
    assert _passages_crypto("2026-07-05") == [0]       # dimanche
    assert _passages_crypto("2026-11-26") == [0]       # Thanksgiving


def test_aucun_passage_crypto_en_double_les_jours_de_bourse() -> None:
    """LE garde-fou. Les jours de séance, le passage d'avant-clôture rebalance déjà
    tout, crypto compris. En ajouter un second ferait deux rebalancements le même jour,
    donc deux fois les frais, pour exactement le même portefeuille."""
    for jour in ("2026-07-01", "2026-01-15", "2026-11-10"):
        assert _passages_crypto(jour) == [], jour


def test_les_deux_declencheurs_ne_se_chevauchent_jamais() -> None:
    """Sur un mois entier, aucune heure ne doit armer les deux à la fois — et chaque
    jour doit en armer exactement un : passage complet, ou passage crypto."""
    base = datetime(2026, 6, 29, tzinfo=UTC)           # lundi
    for d in range(30):
        jour = (base + timedelta(days=d)).date().isoformat()
        complets, cryptos = _declenchements(jour), _passages_crypto(jour)
        assert not (complets and cryptos), f"{jour} : les deux déclencheurs s'arment"
        assert len(complets) + len(cryptos) == 1, f"{jour} : {complets} / {cryptos}"


def test_l_heure_crypto_est_reglable() -> None:
    """UTC fixe est ICI le bon choix : le crypto n'a ni clôture ni heure d'été. C'est
    exactement l'inverse des actions, et c'est pour ça que les deux sont séparés."""
    assert _passages_crypto("2026-07-04", heure=14) == [14]
    assert _passages_crypto("2026-07-04", heure=23) == [23]
