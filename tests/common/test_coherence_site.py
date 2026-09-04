"""Ce que toutes les pages doivent dire ensemble — invariants, pas préférences.

Les 24 payloads publiés dérivent d'UN SEUL snapshot. Deux pages qui énoncent la même
quantité ne peuvent donc pas diverger à cause des données : si elles divergent, le même
nombre est calculé à deux endroits et l'un des deux est faux. Ce dépôt en a
l'historique — PSR à 0,0 % et 100 % sur la même page, trois conventions de Sortino, un
bêta de 0,006 issu d'un appariement positionnel, un CAGR de −100 % avec Sharpe positif.

CHAQUE RÈGLE TESTÉE ICI EST UNE IMPOSSIBILITÉ, jamais un seuil. Un gate qui crie au loup
finit désactivé : le détecteur de fraîcheur macro de ce dépôt se trompait 4 fois sur 5
et « apprenait à être ignoré ». Les tests « doit PASSER » comptent donc autant que les
autres — ce sont eux qui gardent le gate crédible.
"""

from __future__ import annotations

from packages.common.coherence_site import (
    auditer,
    courbe_vs_amplitude,
    dates_d_arrete,
    longueurs_courbe_dates,
)

# ────────── règle 1 : une courbe positive interdit l'anéantissement ──────────

def test_une_courbe_strictement_positive_interdit_une_stat_a_moins_100():
    """La panne du 04/09, attrapée par la DONNÉE et non par le symptôme : si le capital
    n'a jamais touché zéro, aucune statistique ne peut dire qu'il a été anéanti."""
    motifs = courbe_vs_amplitude({"equity": [100.0, 110.0, 121.0],
                                  "metrics": {"cagr": -1.0, "total_return": -1.0}})
    assert len(motifs) == 2
    assert all("jamais été anéanti" in m for m in motifs)


def test_une_VRAIE_ruine_passe():
    """Tout perdre est possible. Le gate refuse l'impossible, pas les mauvaises
    nouvelles — sans ce test, il finirait par cacher les vraies ruines."""
    assert courbe_vs_amplitude({"equity": [100.0, 50.0, 0.0],
                                "stats": {"total_return": -1.0}}) == []


def test_une_perte_severe_mais_coherente_passe():
    assert courbe_vs_amplitude({"equity": [100.0, 38.0],
                                "metrics": {"total_return": -0.62}}) == []


def test_les_stats_sont_cherchees_dans_le_bloc_ET_dans_metrics_et_stats():
    """Le dépôt range ses ratios aux trois endroits selon la page."""
    for cle in ("metrics", "stats"):
        assert courbe_vs_amplitude({"equity": [100.0, 110.0], cle: {"cagr": -1.0}})
    assert courbe_vs_amplitude({"equity": [100.0, 110.0], "cagr": -1.0})


def test_une_courbe_trop_courte_ou_absente_ne_declenche_rien():
    """Un seul point ne décrit aucune amplitude : rien à contredire."""
    assert courbe_vs_amplitude({"equity": [100.0], "metrics": {"cagr": -1.0}}) == []
    assert courbe_vs_amplitude({"metrics": {"cagr": -1.0}}) == []


# ────────── règle 2 : une courbe et ses dates ont la même longueur ──────────

def test_une_courbe_plus_longue_que_ses_dates_est_refusee():
    """Signature de l'empilement positionnel — quatre occurrences dans ce dépôt. L'axe
    est décalé : les bons montants s'affichent aux mauvais jours, sans rien signaler."""
    motifs = longueurs_courbe_dates({"equity": [1, 2, 3], "dates": ["a", "b"]})
    assert motifs and "axe est décalé" in motifs[0]


def test_des_longueurs_egales_passent():
    assert longueurs_courbe_dates({"equity": [1, 2], "dates": ["a", "b"]}) == []


def test_sans_dates_la_regle_ne_s_applique_pas():
    """Beaucoup de courbes sont publiées sans axe : ce n'est pas une faute."""
    assert longueurs_courbe_dates({"equity": [1, 2, 3]}) == []
    assert longueurs_courbe_dates({"equity": [1, 2, 3], "dates": []}) == []


def test_les_quatre_courbes_du_coeur_sont_couvertes():
    for cle in ("preset", "qqq", "megacap", "sector_mom"):
        assert longueurs_courbe_dates({cle: [1, 2, 3], "dates": ["a"]}), cle


# ────────── l'audit récursif ──────────

def test_l_audit_descend_dans_les_blocs_ET_les_listes():
    """Courbes et stats sont imbriquées différemment selon les pages ; une règle qui ne
    regarde qu'un chemin connu rate le prochain endroit où le défaut apparaîtra."""
    motifs = auditer({"dashboard": {"index_core": {"equity": [1, 2, 3],
                                                  "dates": ["a", "b"]}},
                      "comptes": [{"equity": [100.0, 110.0], "stats": {"cagr": -1.0}}]})
    assert any("/dashboard/index_core" in m for m in motifs)
    assert any("/comptes[0]" in m for m in motifs)


def test_un_payload_sain_ne_produit_aucun_motif():
    assert auditer({"dashboard": {"equity": [100.0, 110.0], "dates": ["a", "b"],
                                  "metrics": {"cagr": 0.1, "sharpe": 0.9}}}) == []


# ────────── inventaire (ne bloque pas) ──────────

def test_les_dates_d_arrete_sont_RECENSEES_et_non_jugees():
    """Elles diffèrent légitimement entre domaines — la crypto cote le week-end. En
    faire une règle bloquante produirait un faux positif chaque samedi."""
    out = dates_d_arrete({"as_of": "2026-09-04T00:00:00",
                          "crypto": {"as_of": "2026-09-06"}})
    assert out == {"racine": "2026-09-04", "/crypto": "2026-09-06"}


def test_un_payload_sans_arrete_ne_recense_rien():
    assert dates_d_arrete({"x": {"y": 1}}) == {}
