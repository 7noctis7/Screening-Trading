"""Générer beaucoup de signaux ne doit jamais être gratuit.

La boucle du blueprint NVIDIA `quantitative-signal-discovery-agent` retient un signal
à |IC| ≥ 0,02 avec p ≤ 0,05. C'est le critère d'un signal ISOLÉ, appliqué à une machine
qui en produit des centaines : sans correction pour essais multiples, en tirer assez
finit toujours par en sortir un qui passe.

Le chiffre de ce projet le dit mieux qu'un argument. La sélection du screening a été
mesurée à IC = +0,0202, t = 0,76 : elle FRANCHIT le seuil de 0,02 du blueprint, alors
que notre méthode la rejette parce que 0,76 n'est pas 2. Un générateur branché sur ce
seuil aurait « découvert » exactement ce qu'on venait d'écarter.

Ces tests gardent les trois garanties : la grammaire est fermée (aucun code exécuté),
tout candidat est inscrit au registre AVANT d'être jugé (donc le compte d'essais monte,
donc la déflation se resserre), et notre verdict distingue « rejeté » de « non mesuré ».

Données synthétiques, comme le mandat l'autorise dans tests/ : elles valident la
mécanique, elles ne calibrent aucun seuil de production.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.research import generateur_signaux as gen
from packages.research.ledger import read_records, trial_count

# ------------------------------------------------------------------- sécurité

def test_un_operateur_inconnu_est_refuse_avant_toute_evaluation() -> None:
    """La grammaire est FERMÉE. C'est la différence avec une boucle qui fait écrire du
    Python par un modèle puis l'exécute — dans un dépôt qui peut passer des ordres
    réels, ce serait une porte d'entrée pour du code arbitraire."""
    with pytest.raises(gen.ExpressionInvalide, match="opérateur inconnu"):
        gen.valider({"champ": "close", "operateur": "__import__"})


def test_un_champ_inconnu_est_refuse() -> None:
    with pytest.raises(gen.ExpressionInvalide, match="champ inconnu"):
        gen.valider({"champ": "os.system", "operateur": "identite"})


def test_un_retard_absurde_est_refuse() -> None:
    with pytest.raises(gen.ExpressionInvalide):
        gen.valider({"champ": "close", "operateur": "identite", "retard": -3})


def test_le_retard_regarde_le_passe_jamais_le_futur() -> None:
    """Un décalage dans le mauvais sens fabriquerait de l'information : le signal
    connaîtrait le prix de demain, et l'IC deviendrait spectaculaire pour rien."""
    panneau = {"close": np.arange(20, dtype=float).reshape(10, 2)}
    sortie = gen.evaluer({"champ": "close", "operateur": "identite", "retard": 2},
                         panneau)
    assert np.isnan(sortie[:2]).all(), "les premières dates devraient être inconnues"
    assert sortie[5][0] == pytest.approx(panneau["close"][3][0]), (
        "le retard ne pointe pas vers le passé"
    )


# ------------------------------------------------- le test qui justifie le module

def test_le_signal_deja_rejete_du_projet_passerait_le_seuil_du_blueprint() -> None:
    """IC +0,0202 avec t = 0,76 : accepté par le blueprint, refusé par nous.

    C'est LE cas qui justifie de ne pas reprendre leur critère tel quel.
    """
    mesure = {"ic_moyen": 0.0202, "t_stat": 0.76, "n_fenetres": 83}
    assert gen.accepte_par_le_blueprint(mesure) is True, (
        "le seuil de comparaison ne reproduit plus la règle du blueprint"
    )
    statut, motif = gen.verdict(mesure)
    assert statut == "rejete", f"notre gate accepte un t de 0,76 : {motif}"
    assert "0.76" in motif and "2" in motif, "le motif doit DIRE le seuil manqué"


def test_un_signal_franchement_significatif_est_promu() -> None:
    """Sinon le gate refuserait tout : ce n'est pas de la rigueur, c'est une panne."""
    statut, _ = gen.verdict({"ic_moyen": 0.06, "t_stat": 3.4, "n_fenetres": 40})
    assert statut == "promu"


def test_trop_peu_de_fenetres_n_est_pas_un_rejet() -> None:
    """« Non mesurable » et « mauvais » sont deux choses. Les confondre
    remplirait le registre de faux négatifs, et fausserait le taux de réussite
    affiché sur /methode."""
    statut, motif = gen.verdict({"ic_moyen": 0.2, "t_stat": 5.0, "n_fenetres": 3})
    assert statut == "en_test", motif
    assert "pas un rejet" in motif


# ------------------------------------------ la garantie anti-essais-multiples

def _panneau_sans_edge(t: int = 240, n: int = 30, graine: int = 3):
    """Prix et rendements INDÉPENDANTS : aucun signal ne peut prédire quoi que ce soit.

    C'est le cas le plus sévère pour un générateur — tout ce qu'il « trouve » ici est
    du bruit, par construction.
    """
    g = np.random.default_rng(graine)
    panneau = {c: g.lognormal(0, 0.02, (t, n)) for c in gen.CHAMPS}
    return panneau, g.normal(0, 0.03, (t, n))


def test_chaque_candidat_monte_le_compte_d_essais(tmp_path) -> None:
    """LA garantie. Le blueprint ne compte pas ses essais ; ici, en générer trois cents
    resserre mécaniquement la déflation du Sharpe pour tout le programme."""
    ledger = tmp_path / "hypotheses.jsonl"
    panneau, futurs = _panneau_sans_edge()
    candidats = gen.enumerer(champs=("close", "volume"), retards=(0, 5))

    bilan = gen.campagne(candidats, panneau, futurs, horizon=21, chemin_ledger=ledger)

    assert bilan["essais_avant"] == 0
    assert bilan["essais_apres"] > bilan["essais_avant"], (
        "le compte d'essais n'a pas bougé : générer est redevenu gratuit"
    )
    assert len(read_records(ledger)) == len(candidats), (
        "des candidats ne sont pas inscrits — le compte d'essais ment, donc la "
        "déflation de TOUS les autres travaux est faussée"
    )


def test_les_rejets_sont_inscrits_autant_que_les_promus(tmp_path) -> None:
    """N'inscrire que les gagnants est la définition du biais de publication."""
    ledger = tmp_path / "h.jsonl"
    panneau, futurs = _panneau_sans_edge()
    gen.campagne(gen.enumerer(champs=("close",), retards=(0,)), panneau, futurs,
                 horizon=21, chemin_ledger=ledger)
    statuts = {r["statut"] for r in read_records(ledger)}
    assert statuts, "registre vide"
    assert statuts <= {"promu", "rejete", "en_test"}
    assert trial_count(path=ledger) > 0


def test_sur_du_bruit_pur_le_gate_ne_promeut_presque_rien(tmp_path) -> None:
    """Prix et rendements indépendants : tout ce qui serait « découvert » est du bruit.

    On tolère au plus un promu sur l'ensemble (le hasard existe), mais on vérifie
    surtout que le blueprint en aurait retenu STRICTEMENT PLUS que nous — sinon la
    démonstration ne tient pas.
    """
    ledger = tmp_path / "h.jsonl"
    panneau, futurs = _panneau_sans_edge()
    bilan = gen.campagne(gen.enumerer(retards=(0, 5, 21)), panneau, futurs,
                         horizon=21, chemin_ledger=ledger)
    n_blueprint = sum(1 for r in bilan["resultats"] if r["accepte_par_le_blueprint"])
    assert len(bilan["promus"]) <= 1, (
        f"{len(bilan['promus'])} signaux promus sur du bruit pur : le gate fuit"
    )
    assert n_blueprint >= len(bilan["promus"]), (
        "le seuil du blueprint serait plus strict que le nôtre : vérifier les règles"
    )


def test_l_enumeration_est_deterministe() -> None:
    """Un générateur non déterministe rendrait le registre inexploitable : deux
    campagnes ne seraient plus comparables."""
    assert gen.enumerer() == gen.enumerer()
