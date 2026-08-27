"""Benjamini-Hochberg : le test qui compte est celui sur du bruit PUR.

Un correcteur de tests multiples ne vaut que s'il refuse de découvrir quoi que ce
soit là où il n'y a rien. On lui donne donc des p-valeurs uniformes — l'absence
totale d'effet — et on exige qu'il ne conclue pas.
"""

import random

from packages.research.fdr import benjamini_hochberg, resume


def test_liste_vide():
    assert benjamini_hochberg([]) == []


def test_rejette_les_plus_petites_p_valeurs():
    assert benjamini_hochberg([0.001, 0.008, 0.03, 0.2, 0.6]) == \
        [True, True, True, False, False]


def test_respecte_l_ordre_d_entree():
    """L'ordre de sortie n'est pas un détail : renvoyer les rejets triés
    attribuerait le verdict au mauvais candidat, en silence."""
    assert benjamini_hochberg([0.6, 0.001]) == [False, True]


def test_ne_decouvre_RIEN_sur_du_bruit_pur():
    """500 p-valeurs uniformes = aucune vraie découverte. Le seuil naïf p<0,05 en
    trouverait ~25 ; BH doit en trouver ~0."""
    rng = random.Random(3)
    p = [rng.random() for _ in range(500)]
    naifs = sum(1 for x in p if x <= 0.05)
    assert naifs > 10, "l'échantillon doit bien piéger le seuil naïf"
    assert sum(benjamini_hochberg(p)) <= 1


def test_moins_conservateur_que_bonferroni():
    """Sur des candidats corrélés — paires, mandats voisins — Bonferroni ne laisse
    rien passer. C'est la raison du choix de BH, et elle doit rester vraie."""
    p = [0.001, 0.006, 0.011, 0.016, 0.021]
    bonferroni = sum(1 for x in p if x <= 0.05 / len(p))
    assert sum(benjamini_hochberg(p)) > bonferroni


def test_monotone():
    """Propriété de BH : si une p-valeur est rejetée, toute p-valeur plus petite
    l'est aussi. Une implémentation qui teste chaque rang isolément la viole."""
    p = [0.001, 0.02, 0.03, 0.04, 0.9]
    r = benjamini_hochberg(p)
    rejetes = [p[i] for i, x in enumerate(r) if x]
    non = [p[i] for i, x in enumerate(r) if not x]
    assert not rejetes or not non or max(rejetes) <= min(non)


def test_alpha_plus_strict_decouvre_moins():
    p = [0.001, 0.006, 0.02, 0.04, 0.3]
    assert sum(benjamini_hochberg(p, 0.01)) <= sum(benjamini_hochberg(p, 0.10))


def test_tout_significatif_tout_rejete():
    assert all(benjamini_hochberg([1e-9] * 10))


def test_resume_publie_le_nombre_de_candidats_testes():
    """« Publier le nombre de paires testées avec le verdict » — l'exigence
    littérale du P0 de vault/03_TODO.md. Sans ce chiffre le lecteur ne peut pas
    refaire le calcul."""
    r = resume([0.001, 0.2, 0.4, 0.6, 0.8])
    assert r["n_testees"] == 5
    assert r["n_decouvertes"] == 1
    assert "5 testée(s)" in r["lecture"]


def test_resume_expose_l_ecart_avec_le_seuil_naif():
    """Le chiffre qui rend la correction lisible : combien le seuil naïf aurait
    trouvé, et combien de ceux-là étaient attendus par pur hasard."""
    rng = random.Random(7)
    r = resume([rng.random() for _ in range(200)])
    assert r["n_decouvertes_naives"] > r["n_decouvertes"]
    assert r["faux_positifs_attendus_sans_correction"] == 10.0
