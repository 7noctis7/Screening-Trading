"""La forme canonique : un hash qui dérive ne prouve rien.

Chaque test correspond à une manière SILENCIEUSE dont deux écritures du même mandat
pourraient hasher différemment — et donc rompre le lien d'audit entre un ordre et la
définition qui l'a produit.
"""

import json

import pytest

from packages.mandate.canonical import canoniser, hacher, hacher_court, normaliser


def test_ordre_des_cles_sans_effet():
    assert hacher({"a": 1, "b": 2}) == hacher({"b": 2, "a": 1})


def test_flottant_entier_egale_entier():
    """`top_k: 30` et `top_k: 30.0` sont le même mandat."""
    assert hacher({"top_k": 30}) == hacher({"top_k": 30.0})


def test_zero_signe_normalise():
    """-0.0 traverse certains round-trips YAML/JSON ; il ne doit pas créer
    d'identité."""
    assert hacher({"x": 0.0}) == hacher({"x": -0.0})


def test_bruit_flottant_reste_distinct():
    """Choix ASSUMÉ : 0.3 et 0.1+0.2 sont des nombres différents, donc des mandats
    différents. Arrondir en douce ferait collisionner deux configurations réellement
    distinctes, ce qui est plus grave que l'inverse."""
    assert hacher({"x": 0.3}) != hacher({"x": 0.1 + 0.2})


def test_non_fini_refuse():
    """Un NaN dans un mandat ne décrit aucune décision — et le dépôt a déjà la
    cicatrice des NaN qui traversent un export (`dump_static::_clean`)."""
    for mauvais in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="non finie"):
            hacher({"x": mauvais})


def test_cle_non_textuelle_refusee():
    """`json` convertirait 1 en "1" en silence : {1: x} et {"1": x} hasheraient
    pareil."""
    with pytest.raises(TypeError, match="non textuelle"):
        hacher({1: "a"})


def test_type_non_serialisable_refuse():
    with pytest.raises(TypeError, match="non canonisable"):
        hacher({"f": lambda: 1})


def test_stabilite_par_round_trip_json():
    """Écrire puis relire un mandat ne doit pas changer son identité."""
    m = {"moteur": "preset", "p": {"k": 30, "seuil": 0.025, "noms": ["AAPL", "MSFT"]}}
    assert hacher(m) == hacher(json.loads(json.dumps(m)))


def test_bool_non_confondu_avec_entier():
    """`True == 1` en Python : sans traitement explicite, les deux hasheraient pareil
    alors que `regime_gate: true` et `regime_gate: 1` n'ont pas le même sens de
    lecture."""
    assert hacher({"x": True}) != hacher({"x": 1})


def test_octets_canoniques_sans_espace():
    assert b" " not in canoniser({"a": 1, "b": [1, 2]})


def test_hash_court_est_un_prefixe():
    m = {"a": 1}
    assert hacher(m).startswith(hacher_court(m))


def test_normaliser_est_recursif():
    assert normaliser({"a": [{"b": 2.0}]}) == {"a": [{"b": 2}]}
