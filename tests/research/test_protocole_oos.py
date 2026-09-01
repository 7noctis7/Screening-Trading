"""Protocole IS/OOS et porte DSR (spec utilisateur 01/09, module 4).

Le test central : à Sharpe IDENTIQUE, plus on a essayé de stratégies, moins on est
déployable. Si ce n'était pas vrai, le DSR ne servirait à rien.
"""

import pytest

from packages.research.protocole_oos import (
    STATUT,
    parcimonie,
    partitionner,
    porte_de_deploiement,
)


def test_le_module_demarre_en_SHADOW():
    assert STATUT == "SHADOW_UNCALIBRATED"


# ------------------------------------------------------------- partition
def test_partition_60_40():
    p = partitionner(1000)
    assert (p.n_is, p.n_oos) == (600, 400)


def test_la_partition_ne_RECOUVRE_pas():
    """`fin_is` est l'indice de début de l'OOS : aucun point n'appartient aux deux."""
    p = partitionner(997)
    assert p.n_is + p.n_oos == 997
    assert p.fin_is == p.n_is


def test_la_partition_est_CHRONOLOGIQUE():
    """Un découpage aléatoire mettrait des points postérieurs dans l'apprentissage —
    look-ahead pur, et la validation « à l'aveugle » ne validerait plus rien."""
    p = partitionner(100, part_is=0.6)
    serie = list(range(100))
    assert max(serie[:p.fin_is]) < min(serie[p.fin_is:])


def test_serie_trop_courte_refusee():
    with pytest.raises(ValueError, match="trop court"):
        partitionner(5)


def test_part_aberrante_refusee():
    for mauvais in (0.0, 0.99):
        with pytest.raises(ValueError):
            partitionner(1000, part_is=mauvais)


def test_les_deux_cotes_restent_non_vides():
    for n in (10, 11, 1001):
        p = partitionner(n)
        assert p.n_is >= 1 and p.n_oos >= 1


# ------------------------------------------------------------- parcimonie
def test_trois_parametres_passent():
    assert parcimonie({"a": 1, "b": 2, "c": 3})["accepte"]


def test_quatre_parametres_rejetes():
    r = parcimonie({"a": 1, "b": 2, "c": 3, "d": 4})
    assert not r["accepte"] and "degré de liberté" in r["motif"]


def test_aucun_parametre_passe():
    assert parcimonie({})["accepte"]


# ------------------------------------------------------------- porte DSR
def test_le_DSR_BAISSE_quand_le_nombre_d_essais_MONTE():
    """LE test. À Sharpe et échantillon identiques, chercher davantage doit coûter."""
    peu = porte_de_deploiement(0.10, 1000, 1)["dsr"]
    beaucoup = porte_de_deploiement(0.10, 1000, 200)["dsr"]
    assert beaucoup < peu, (peu, beaucoup)


def test_une_recherche_massive_BLOQUE_le_deploiement():
    r = porte_de_deploiement(0.10, 1000, 500)
    assert not r["deployable"] and "déflation" in r["motif"]


def test_un_sharpe_franc_sur_peu_d_essais_passe():
    """Contrepartie : la porte ne doit pas tout bloquer, sinon elle ne mesure rien."""
    assert porte_de_deploiement(0.20, 2500, 3)["deployable"]


def test_echantillon_OOS_degenere_refuse():
    assert not porte_de_deploiement(0.5, 1, 10)["deployable"]


def test_zero_essai_refuse():
    """Zéro essai est incohérent : la stratégie évaluée en est un."""
    assert not porte_de_deploiement(0.5, 1000, 0)["deployable"]


def test_la_kurtosis_penalise():
    """Des queues épaisses rendent le Sharpe moins fiable — le DSR doit le refléter."""
    normal = porte_de_deploiement(0.12, 1500, 20, kurtosis=3.0)["dsr"]
    epais = porte_de_deploiement(0.12, 1500, 20, kurtosis=12.0)["dsr"]
    assert epais < normal


def test_l_asymetrie_negative_penalise():
    normal = porte_de_deploiement(0.12, 1500, 20, skew=0.0)["dsr"]
    gauche = porte_de_deploiement(0.12, 1500, 20, skew=-1.5)["dsr"]
    assert gauche < normal


def test_le_verdict_publie_le_nombre_d_essais():
    """Un DSR sans son nombre d'essais n'est pas contestable, donc il ne vaut rien."""
    r = porte_de_deploiement(0.10, 1000, 42)
    assert r["n_essais"] == 42 and r["n_obs_oos"] == 1000
