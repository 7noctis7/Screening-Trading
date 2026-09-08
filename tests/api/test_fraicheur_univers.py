"""Un prix périmé est pire qu'un prix absent : il a l'air d'un prix.

Le chargement ne regardait que le NOMBRE de barres. Une série arrêtée — jeton migré
(MATIC→POL), délisté, source qui lâche — comptait donc pour un actif RÉEL avec un cours
vieux de deux ans. Mesuré le 09/09 : `HYPE/USDC` s'arrête le 27 août 2024 et figurait
encore dans l'univers réel du 8 septembre 2026. Le screener pouvait le classer, le
dimensionnement le dimensionner, les graphiques l'afficher.

Le test lit la source plutôt que d'importer l'API : `fastapi` n'est pas installé partout
où cette suite tourne, et un test qui ne s'exécute nulle part ne garde rien.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parents[2]
SOURCE = (RACINE / "apps" / "api" / "snapshot.py").read_text(encoding="utf-8")


def _charger():
    debut = SOURCE.index("RETARD_MAX_JOURS = ")
    fin = SOURCE.index("def _index_series", debut)
    espace: dict = {}
    exec(SOURCE[debut:fin], espace)  # noqa: S102
    return espace["_series_perimees"], espace["RETARD_MAX_JOURS"]


def _barres(fin: datetime, n: int = 300) -> list:
    return [SimpleNamespace(ts=fin - timedelta(days=i)) for i in range(n)]


def test_une_serie_arretee_depuis_deux_ans_sort_du_reel() -> None:
    perimees, _ = _charger()
    frais = datetime(2026, 9, 8)
    data = {"AAPL": _barres(frais), "HYPE/USDC": _barres(datetime(2024, 8, 27))}

    assert perimees(data, {"AAPL", "HYPE/USDC"}) == {"HYPE/USDC"}


def test_un_univers_entier_en_retard_ne_se_condamne_pas_lui_meme() -> None:
    """LE contrôle négatif. La comparaison se fait au PANNEAU, pas à la date du jour :
    une ingestion de la veille, un lundi férié, ou une machine éteinte une semaine ne
    doivent vider l'univers de personne."""
    perimees, _ = _charger()
    vieux = datetime(2020, 1, 1)
    data = {"A": _barres(vieux), "B": _barres(vieux - timedelta(days=1))}

    assert perimees(data, {"A", "B"}) == set()


def test_le_seuil_laisse_passer_un_retard_ordinaire() -> None:
    """Un actif qui ne cote pas depuis quelques jours — suspension courte, place
    fermée — n'est pas périmé. Un seuil serré viderait l'univers à chaque pont."""
    perimees, retard_max = _charger()
    frais = datetime(2026, 9, 8)
    data = {"A": _barres(frais),
            "B": _barres(frais - timedelta(days=retard_max - 5)),
            "C": _barres(frais - timedelta(days=retard_max + 5))}

    assert perimees(data, {"A", "B", "C"}) == {"C"}


def test_une_serie_sans_barre_est_periemee() -> None:
    perimees, _ = _charger()
    data = {"A": _barres(datetime(2026, 9, 8)), "VIDE": []}
    assert perimees(data, {"A", "VIDE"}) == {"VIDE"}


def test_le_filtre_est_branche_sur_le_chargement() -> None:
    """Une fonction juste que personne n'appelle ne corrige rien."""
    assert "real_syms -= _series_perimees(data, real_syms)" in SOURCE, (
        "le filtre de fraîcheur n'est plus appliqué au chargement des prix"
    )
