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
