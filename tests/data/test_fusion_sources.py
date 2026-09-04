"""Une seule politique de fusion — et la trace de qui a produit quoi.

Le dépôt fusionnait les mêmes bases selon DEUX règles opposées : `_load_prices` en
« premier gagne », `merge_bars` en « dernier gagne ». Mêmes bases, mêmes dates, deux
historiques pour le même actif selon la fonction qui le demandait — 0,71 %/an d'écart
mesuré sur le cœur QQQ. Ces tests verrouillent la règle unique et son lignage.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.core.models import Bar
from packages.data.fusion_sources import (
    desaccords,
    fusionner,
    jour,
    provenance,
)


def _bar(d: str, close: float) -> Bar:
    ts = datetime.fromisoformat(d).replace(tzinfo=UTC)
    return Bar("X", "1d", ts, close, close, close, close, 1_000)


def test_le_premier_gagne_le_second_ne_comble_que_les_trous():
    """LA règle. La base longue est ajustée, la maj quotidienne est brute : la laisser
    écraser insérerait une discontinuité raw/ajusté au milieu de l'historique."""
    cible: dict = {}
    fusionner(cible, [_bar("2026-08-01", 100.0), _bar("2026-08-02", 101.0)])
    fusionner(cible, [_bar("2026-08-02", 999.0), _bar("2026-08-03", 102.0)])
    assert cible["2026-08-02"][1] == 101.0          # NON écrasé par 999
    assert cible["2026-08-03"][1] == 102.0          # trou comblé
    assert len(cible) == 3


def test_la_fraicheur_survit_a_la_regle():
    """L'objection évidente : si la base longue prime, perd-on les dates récentes ?
    Non — ce sont justement celles qui lui manquent : aucun conflit possible."""
    cible: dict = {}
    fusionner(cible, [_bar("2026-08-01", 100.0)], source="base longue")
    fusionner(cible, [_bar("2026-09-04", 110.0)], source="maj quotidienne")
    assert max(cible) == "2026-09-04"


def test_le_lignage_suit_la_donnee_retenue_pas_la_derniere_tentative():
    """Une trace qui enregistre la dernière écriture au lieu du jour retenu mentirait
    exactement là où on la consulte."""
    lignage: dict[str, str] = {}
    cible: dict = {}
    fusionner(cible, [_bar("2026-08-02", 101.0)], source="base longue", lignage=lignage)
    fusionner(cible, [_bar("2026-08-02", 999.0), _bar("2026-08-03", 102.0)],
              source="maj quotidienne", lignage=lignage)
    assert lignage["2026-08-02"] == "base longue"       # la source qui a GAGNÉ
    assert lignage["2026-08-03"] == "maj quotidienne"


def test_provenance_compte_les_jours_par_source():
    lignage = {"j1": "base longue", "j2": "base longue", "j3": "maj quotidienne"}
    assert provenance(lignage) == {"base longue": 2, "maj quotidienne": 1}


def test_fusionner_renvoie_le_nombre_de_jours_AJOUTES():
    """Zéro ajout est une information : la source n'apporte rien de neuf."""
    cible: dict = {}
    assert fusionner(cible, [_bar("2026-08-01", 100.0)]) == 1
    assert fusionner(cible, [_bar("2026-08-01", 999.0)]) == 0


def test_le_desaccord_entre_bases_est_MESURE_pas_supposé():
    """« Les bases sont d'accord » doit être un nombre, pas une hypothèse."""
    out = desaccords({
        "base longue": {"2026-08-01": 100.0, "2026-08-02": 101.0},
        "maj quotidienne": {"2026-08-01": 100.0, "2026-08-02": 105.0},
    })
    assert len(out) == 1
    assert out[0]["jour"] == "2026-08-02"
    assert abs(out[0]["ecart_relatif"] - (105.0 - 101.0) / 105.0) < 1e-12


def test_un_arrondi_de_serialisation_n_est_pas_un_desaccord():
    """Sinon chaque jour serait signalé et la mesure deviendrait illisible."""
    assert desaccords({
        "a": {"2026-08-01": 100.0},
        "b": {"2026-08-01": 100.00000001},
    }) == []


def test_une_date_vue_par_une_seule_source_n_est_pas_un_desaccord():
    """Un trou comblé n'est pas un conflit : c'est le fonctionnement normal."""
    assert desaccords({"a": {"2026-08-01": 100.0}, "b": {"2026-08-02": 200.0}}) == []


def test_la_cle_de_fusion_est_le_JOUR_quelle_que_soit_la_forme():
    """Trois représentations du même jour doivent fusionner, sinon la même barre entre
    deux fois et l'historique porte un plateau artificiel."""
    from datetime import date
    assert jour(datetime(2026, 8, 1, 20, 0, tzinfo=UTC)) == "2026-08-01"
    assert jour(date(2026, 8, 1)) == "2026-08-01"
    assert jour("2026-08-01T00:00:00+00:00") == "2026-08-01"
