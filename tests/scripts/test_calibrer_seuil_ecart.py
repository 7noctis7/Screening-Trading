"""Le seuil doit venir d'une mesure, et la mesure doit être honnête.

Un instrument de calibration qui se trompe est pire qu'aucun : il donne un chiffre, donc
on le croit. Ces tests vérifient les deux façons dont celui-ci pourrait mentir :
surestimer sa sensibilité en se créditant de séries déjà cassées, ou nier son coût.
"""

from __future__ import annotations

import numpy as np

from scripts.calibrer_seuil_ecart import sensibilite, taux_de_fond


def _panel(t: int = 500, n: int = 60, vol: float = 0.02, graine: int = 0) -> np.ndarray:
    g = np.random.default_rng(graine)
    return 100.0 * np.exp(np.cumsum(g.normal(0, vol, (t, n)), axis=0))


def test_un_panneau_sain_a_un_cout_nul() -> None:
    """Le taux de fond, c'est ce qu'un humain doit lire pour rien."""
    p = _panel()
    total, par_classe = taux_de_fond(p, ["equity"] * p.shape[1], 8.0, normaliser=True)
    assert total == 0.0, f"{100 * total:.0f} % signalé sans le moindre défaut"
    assert par_classe["equity"] == 0.0


def test_le_cout_decroit_quand_le_seuil_monte() -> None:
    """Propriété de définition : signaler au-delà de 12 écarts ne peut pas signaler PLUS
    qu'au-delà de 6. Un instrument non monotone est cassé, pas sévère."""
    p = _panel()
    p[100, 3] *= 4.0
    p[200:, 7] /= 3.0
    classes = ["equity"] * p.shape[1]
    taux = [taux_de_fond(p, classes, s, True)[0] for s in (4.0, 6.0, 8.0, 12.0, 20.0)]
    assert taux == sorted(taux, reverse=True), taux


def test_un_defaut_injecte_est_retrouve() -> None:
    """Contrôle positif : sans lui, le seuil « le moins coûteux » serait l'infini."""
    p = _panel()
    for genre in ("split", "tick"):
        taux, testes = sensibilite(p, 8.0, True, genre, n=10)
        assert taux == 1.0, (genre, taux)
        assert testes == 10, (genre, testes)


def test_un_defaut_injecte_un_jour_non_cote_ne_compte_pas_contre_le_detecteur() -> None:
    """Correctif du 09/09, trouvé sur données réelles.

    Un panneau multi-classes est plein de trous : une action ne cote pas le week-end,
    une crypto cote sept jours sur sept. Une date d'injection tirée au hasard tombe donc
    souvent sur un jour non coté — le défaut n'y produit aucun rendement, il n'y a
    rien à détecter, et la sensibilité s'effondre. Elle sortait à 61 % pour un split de
    −75 % qu'aucun détecteur ne peut manquer, ce qui poussait la proposition vers le
    seuil le plus silencieux : le biais désarmait le détecteur.

    Ici, un calendrier 5 jours sur 7 — celui des actions dans un panneau qui contient
    aussi des cryptos. Deux séances sur sept sont vides, et une date tirée au hasard y
    tombe une fois sur trois et demie. La détection doit rester totale : l'injection ne
    vise que des séances réellement cotées.
    """
    p = _panel(t=700)
    for jour in (5, 6):                        # week-ends : l'action ne cote pas
        p[jour::7] = np.nan
    taux, testes = sensibilite(p, 8.0, True, "split", n=10)
    assert testes == 10, f"{testes} actifs testés : des cibles ont été perdues"
    assert taux == 1.0, f"sensibilité {taux:.0%} — l'injection tombe dans les trous"


def test_la_sensibilite_ne_se_credite_pas_des_series_deja_cassees() -> None:
    """LE piège de la mesure. Injecter un défaut dans une série que le détecteur
    signalait DÉJÀ, puis compter cette série comme « trouvée », mesurerait le taux de
    fond en le prenant pour de la sensibilité — et le chiffre monterait avec le bruit.

    Ici, TOUT le panneau est déjà signalé : il ne reste aucune série vierge, donc la
    sensibilité n'est pas mesurable et doit le dire (NaN), pas répondre 100 %.
    """
    p = _panel(n=20)
    for j in range(p.shape[1]):
        p[150 + j, j] *= 6.0                # chaque série porte déjà un tick aberrant
    deja = taux_de_fond(p, ["equity"] * p.shape[1], 8.0, True)[0]
    assert deja == 1.0, f"contrôle inopérant : seulement {100 * deja:.0f} % signalés"
    taux, testes = sensibilite(p, 8.0, True, "tick", n=20)
    assert np.isnan(taux) and testes == 0


def _mesure(seuil: float, fond: float, sens: float, n: int = 50) -> dict:
    return {"seuil": seuil, "fond": fond, "split": sens, "tick": sens, "n_testes": n}


def test_un_optimum_sur_le_bord_de_la_grille_est_signale(capsys) -> None:
    """L'erreur que j'ai failli commettre le 09/09.

    Le premier passage réel proposait 24 — le plus grand seuil essayé — alors que le
    score y était ENCORE croissant. Ce n'était pas un maximum, c'était la fin de la
    grille. Proposer un bord sans le dire fait passer « je n'ai pas cherché plus loin »
    pour « j'ai trouvé le meilleur ».
    """
    from scripts.calibrer_seuil_ecart import SEUILS, proposer

    croissant = [_mesure(s, fond=1.0 / (i + 1), sens=1.0) for i, s in enumerate(SEUILS)]
    proposer(croissant)
    sortie = capsys.readouterr().out
    assert f"SEUIL_ECART = {SEUILS[-1]:.0f}" in sortie
    assert "BORD de la grille" in sortie, sortie


def test_un_optimum_interieur_n_est_pas_signale_comme_un_bord(capsys) -> None:
    """Contrôle négatif : un avertissement permanent ne veut plus rien dire."""
    from scripts.calibrer_seuil_ecart import SEUILS, proposer

    milieu = len(SEUILS) // 2
    mesures = [_mesure(s, fond=0.5, sens=1.0 if i == milieu else 0.2)
               for i, s in enumerate(SEUILS)]
    proposer(mesures)
    sortie = capsys.readouterr().out
    assert f"SEUIL_ECART = {SEUILS[milieu]:.0f}" in sortie
    assert "BORD" not in sortie, sortie
