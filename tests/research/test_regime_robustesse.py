"""Les quatre contrôles doivent DÉTECTER la loterie, pas la maquiller.

Synthétique assumé : on valide la math sur des cas construits dont on connaît la
réponse. La mesure sur données réelles est le travail de `scripts/regime_atr_lab.py`.
"""

from __future__ import annotations

from datetime import datetime

from packages.research import regime_robustesse as RR

# --- 1. la moyenne ressemble-t-elle à la médiane ? -------------------------------

def test_une_loterie_se_voit_a_l_ecart_moyenne_mediane():
    """99 zéros et un +100 : moyenne +1, médiane 0, taux de gain 1 %."""
    d = RR.distribution([0.0] * 99 + [100.0])
    assert d["moyenne"] == 1.0
    assert d["mediane"] == 0.0
    assert d["taux_gain"] == 0.01
    assert d["ecart_moyenne_mediane"] == 1.0


def test_une_distribution_saine_colle_moyenne_et_mediane():
    d = RR.distribution([0.01, 0.02, 0.03, 0.04, 0.05])
    assert abs(d["ecart_moyenne_mediane"]) < 1e-9
    assert d["taux_gain"] == 1.0


def test_un_echantillon_vide_ne_rend_pas_zero():
    """Inconnu n'est pas nul — la règle de ce dépôt, ici aussi."""
    d = RR.distribution([])
    assert d["n"] == 0 and d["moyenne"] is None and d["taux_gain"] is None


def test_les_queues_sont_rendues():
    d = RR.distribution([float(i) for i in range(101)])
    assert d["p10"] == 10.0 and d["p90"] == 90.0


# --- 2. que reste-t-il sans les meilleures ? -------------------------------------

def test_retirer_un_pourcent_peut_renverser_le_signe():
    """Le cas `sizing_lab` : l'agrégat est positif, le corps de la distribution non."""
    xs = [-0.01] * 99 + [2.0]
    r = RR.sans_les_meilleurs(xs, part=0.01)
    assert r["moyenne_complete"] > 0
    assert r["moyenne_amputee"] < 0
    assert r["survit"] is False


def test_un_effet_reparti_survit_a_l_amputation():
    r = RR.sans_les_meilleurs([0.02] * 100, part=0.01)
    assert r["survit"] is True
    assert abs(r["perte_relative"]) < 1e-9


def test_retirer_un_pourcent_retire_au_moins_une_observation():
    """Sur 50 lignes, 1 % arrondit à 0. Un contrôle qui ne retire rien ne
    contrôle rien."""
    r = RR.sans_les_meilleurs([0.01] * 50, part=0.01)
    assert r["retirees"] == 1


# --- 3. combien d'épisodes, et non de journées ? ---------------------------------

def test_des_journees_consecutives_forment_UN_episode():
    jours = ["2020-03-16", "2020-03-17", "2020-03-18", "2020-03-19"]
    assert len(RR.episodes(jours)) == 1


def test_des_journees_eloignees_forment_des_episodes_distincts():
    jours = ["2020-03-16", "2020-03-17", "2021-11-02", "2023-06-14"]
    grappes = RR.episodes(jours)
    assert len(grappes) == 3
    assert grappes[0] == ["2020-03-16", "2020-03-17"]


def test_le_seuil_d_ecart_est_calendaire_pas_ouvre():
    """Un vendredi et le lundi suivant sont séparés de 3 jours : même secousse."""
    assert len(RR.episodes(["2020-03-20", "2020-03-23"])) == 1
    assert len(RR.episodes(["2020-03-20", "2020-03-30"])) == 2


def test_les_doublons_de_date_ne_gonflent_pas_le_compte():
    assert len(RR.episodes(["2020-03-16"] * 40)) == 1


# --- 4. une seule année porte-t-elle le résultat ? -------------------------------

def _obs(jour, n, valeur):
    return [(jour, valeur)] * n


def test_une_crise_qui_porte_tout_est_signalee():
    """Mars 2020 pèse 90 % du total : c'est un événement, pas un régime."""
    obs = (_obs("2020-03-16", 9, 1.0)
           + [("2021-05-04", 0.5), ("2022-08-11", 0.5)])
    c = RR.concentration(obs)
    assert c["annee_dominante"] == "2020"
    assert c["part_annee_dominante"] == 0.9
    assert c["part_plus_gros_episode"] == 0.9
    assert c["n_episodes"] == 3


def test_un_effet_reparti_ne_declenche_aucune_concentration():
    obs = [(f"20{a:02d}-06-15", 1.0) for a in range(15, 26)]
    c = RR.concentration(obs)
    assert c["n_episodes"] == 11
    assert c["part_plus_gros_episode"] < RR.PART_ALERTE


def test_l_episode_dominant_est_nomme_par_ses_bornes():
    obs = _obs("2020-03-16", 1, 1.0) + _obs("2020-03-18", 1, 1.0)
    c = RR.concentration(obs)
    assert c["episode_dominant"] == "2020-03-16 → 2020-03-18"


def test_sans_observation_on_ne_conclut_pas():
    assert RR.concentration([])["disponible"] is False


def test_les_horodatages_se_reduisent_a_leur_journee():
    """`regime_atr.jour` normalise en amont ; on vérifie que le contrat tient ici."""
    from packages.research.regime_atr import jour
    jours = [jour(datetime(2020, 3, 16, 20, 0)), jour("2020-03-17T00:00:00Z")]
    assert RR.episodes(jours) == [["2020-03-16", "2020-03-17"]]
