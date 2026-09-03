"""Pagination de l'historique d'ordres : ni troncature silencieuse, ni boucle infinie.

Mesuré le 03/09 : `limit=500` rendait 202 ordres, et la réconciliation du journal ne
soldait que la MOITIÉ de chaque position — les ventes plus anciennes n'arrivaient jamais.
Une API qui plafonne à 500 et rend les plus récents d'abord tronque SANS RIEN DIRE.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from packages.execution.alpaca_broker import paginer


@dataclass
class Ordre:
    id: str
    submitted_at: datetime


def _historique(n: int) -> list[Ordre]:
    """`n` ordres, du plus RÉCENT au plus ancien — l'ordre que rend l'API."""
    base = datetime(2026, 9, 1, tzinfo=UTC)
    return [Ordre(f"o{i}", base - timedelta(hours=i)) for i in range(n)]


def _api(tous: list[Ordre], page_max: int = 500):
    """API factice : rend les `n` plus récents STRICTEMENT antérieurs à `borne`."""
    def page(n, borne):
        dispo = [o for o in tous if borne is None or o.submitted_at < borne]
        return dispo[:min(n, page_max)]
    return page


def test_un_historique_plus_long_qu_une_page_est_recupere_en_entier():
    """LE défaut du 03/09 : un seul appel ne pouvait pas rendre plus de 500 ordres."""
    tous = _historique(1200)
    res = paginer(_api(tous), limit=1200, page_max=500)
    assert len(res) == 1200
    assert len({o.id for o in res}) == 1200          # aucun doublon entre les pages


def test_on_ne_rend_jamais_plus_que_demande():
    res = paginer(_api(_historique(1200)), limit=300, page_max=500)
    assert len(res) == 300


def test_un_historique_court_ne_declenche_pas_de_page_superflue():
    appels = []
    tous = _historique(37)

    def page(n, borne):
        appels.append(borne)
        return _api(tous)(n, borne)

    assert len(paginer(page, limit=500, page_max=500)) == 37
    assert len(appels) == 1                          # une page a suffi


def test_une_api_qui_rend_toujours_la_meme_page_ne_fait_pas_boucler():
    """Le garde-fou qui compte : sans lui, la boucle ne s'arrêterait jamais."""
    fige = _historique(10)
    appels = []

    def page(n, borne):
        appels.append(borne)
        return fige                                  # ignore `borne` — toujours pareil

    res = paginer(page, limit=5000, page_max=500)
    assert len(res) == 10                            # dédoublonné par id
    assert len(appels) <= 12                         # borné, pas infini


def test_une_api_vide_rend_une_liste_vide():
    assert paginer(lambda n, b: [], limit=500) == []
