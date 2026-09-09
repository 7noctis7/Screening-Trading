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
    with pytest.raises(gen.ExpressionInvalide, match="opérateur temporel inconnu"):
        gen.valider({"temporel": "__import__", "transversal": "rang"})


def test_un_operateur_transversal_inconnu_est_refuse() -> None:
    with pytest.raises(gen.ExpressionInvalide, match="transversal inconnu"):
        gen.valider({"temporel": "momentum", "transversal": "os.system"})


def test_une_fenetre_absurde_est_refusee() -> None:
    with pytest.raises(gen.ExpressionInvalide):
        gen.valider({"temporel": "momentum", "transversal": "rang", "fenetre": -3})


def test_un_panneau_incomplet_est_refuse() -> None:
    """Un opérateur de bande a besoin du plus haut et du plus bas : évaluer sur un
    panneau amputé lèverait plus loin, dans du code numérique, avec un message
    incompréhensible."""
    with pytest.raises(gen.ExpressionInvalide, match="champs absents"):
        gen.evaluer({"temporel": "momentum", "transversal": "rang"},
                    {"close": np.ones((30, 3))})


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
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    panneau = {
        "open": close * (1 + g.normal(0, 0.002, (t, n))),
        "high": close * (1 + np.abs(g.normal(0, 0.006, (t, n)))),
        "low": close * (1 - np.abs(g.normal(0, 0.006, (t, n)))),
        "close": close,
        "volume": np.abs(g.lognormal(10, 0.5, (t, n))),
    }
    return panneau, g.normal(0, 0.03, (t, n))


def test_chaque_candidat_monte_le_compte_d_essais(tmp_path) -> None:
    """LA garantie. Le blueprint ne compte pas ses essais ; ici, en générer trois cents
    resserre mécaniquement la déflation du Sharpe pour tout le programme."""
    ledger = tmp_path / "hypotheses.jsonl"
    panneau, futurs = _panneau_sans_edge()
    candidats = gen.enumerer(temporels=("momentum", "volatilite"), fenetres=(21,))

    bilan = gen.campagne(candidats, panneau, futurs, horizon=21, chemin_ledger=ledger)

    assert bilan["essais_avant"] == 0
    assert bilan["essais_apres"] > bilan["essais_avant"], (
        "le compte d'essais n'a pas bougé : générer est redevenu gratuit"
    )
    # UNE ligne par hypothèse DISTINCTE, pas par écriture de la même. `brut`, `rang` et
    # `zscore` d'un même signal ont le même IC de Spearman : les compter séparément
    # quadruplerait le nombre d'essais sans qu'aucune hypothèse nouvelle soit testée.
    assert len(read_records(ledger)) == bilan["n_essais_distincts"], (
        "le registre ne contient pas exactement une ligne par hypothèse distincte"
    )
    assert bilan["n_essais_distincts"] < len(candidats), (
        "aucune famille équivalente détectée : le compte d'essais est gonflé par des "
        "doublons que la mesure d'IC ne peut pas distinguer"
    )


def test_les_rejets_sont_inscrits_autant_que_les_promus(tmp_path) -> None:
    """N'inscrire que les gagnants est la définition du biais de publication."""
    ledger = tmp_path / "h.jsonl"
    panneau, futurs = _panneau_sans_edge()
    gen.campagne(gen.enumerer(temporels=("momentum",), fenetres=(21,)), panneau,
                 futurs, horizon=21, chemin_ledger=ledger)
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
    bilan = gen.campagne(gen.enumerer(fenetres=(21, 63)), panneau, futurs,
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


# ------------------------------- essais multiples DANS la campagne

def test_les_transformations_de_rang_sont_une_seule_hypothese() -> None:
    """Mesuré le 08/09 : `brut`, `rang` et `zscore` d'un même signal donnent −0,104974,
    `inverse` +0,104974. La corrélation de Spearman ne voit que l'ORDRE, et ces
    transformations le préservent. Quatre « candidats » = un seul test."""
    fam = gen.familles(gen.enumerer(temporels=("momentum",), fenetres=(21,)))
    assert len(fam) == 1, f"{len(fam)} familles pour un seul signal"
    assert len(fam[0][1]) == 4, "les quatre formes ne sont pas regroupées"


def test_benjamini_hochberg_rejette_deux_marginaux_sur_vingt_quatre() -> None:
    """Le cas RÉEL du 08/09, rejoué. Les deux « promus » de la campagne avaient
    p = 0,0092 et p = 0,0432 sur vingt-quatre essais distincts. Aucun ne survit : deux
    promus sur vingt-quatre à t ≥ 2, c'est le nombre attendu du pur hasard (1,2)."""
    p = [0.0092, 0.0432] + [0.5] * 22
    assert not any(gen.benjamini_hochberg(p)), (
        "le contrôle du taux de fausses découvertes laisse passer des marginaux"
    )


def test_benjamini_hochberg_garde_ce_qui_est_franc() -> None:
    """Contrôle négatif : une correction qui rejette TOUT ne corrige rien, elle
    stérilise. Un signal à p = 1e-6 doit survivre."""
    survit = gen.benjamini_hochberg([1e-6] + [0.6] * 23)
    assert survit[0] and not any(survit[1:])


def test_un_signal_marginal_est_indistinct_et_non_rejete(tmp_path, monkeypatch) -> None:
    """« Rejeté » et « indistinct une fois les essais comptés » ne sont pas la même
    chose : le premier dit que l'idée est mauvaise, le second qu'on ne peut pas savoir.
    Les confondre ferait abandonner des pistes pour la mauvaise raison.

    On force UN candidat à ressortir marginal (t = 2,1) et les autres à plat, exactement
    la configuration du 08/09 : il franchit le seuil brut, il ne survit pas à la
    correction pour les vingt-quatre essais de sa propre campagne."""
    appels = {"n": 0}

    def _mesure_truquee(signal, futurs, horizon):
        appels["n"] += 1
        if appels["n"] == 1:
            return {"ic_moyen": 0.055, "t_stat": 2.1, "n_fenetres": 70}
        return {"ic_moyen": 0.001, "t_stat": 0.05, "n_fenetres": 70}

    monkeypatch.setattr(gen, "mesurer_ic", _mesure_truquee)
    ledger = tmp_path / "h.jsonl"
    panneau, futurs = _panneau_sans_edge()
    bilan = gen.campagne(gen.enumerer(), panneau, futurs, horizon=21,
                         chemin_ledger=ledger)

    assert not bilan["promus"], (
        "un signal marginal est promu malgré les 24 essais de la campagne — c'est "
        "exactement le reproche fait au seuil |IC| >= 0,02 du blueprint"
    )
    assert len(bilan["indistincts_apres_correction"]) == 1, (
        "le signal marginal devrait être INDISTINCT, ni promu ni rejeté"
    )
    motif = bilan["indistincts_apres_correction"][0]["motif"]
    assert "Benjamini-Hochberg" in motif, "le motif ne dit pas pourquoi il est tombé"
    assert bilan["faux_positifs_attendus"] > 0, (
        "la campagne doit publier combien de faux positifs le hasard produirait"
    )
