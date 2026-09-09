"""Filtre d'entrée « résultats imminents » — un risque daté que la covariance ne voit pas."""
from datetime import UTC, datetime

from packages.portfolio.filtre_resultats import FENETRE_DEFAUT, dates_resultats, ecarter


def test_un_resultat_dans_la_fenetre_ecarte_le_candidat():
    retenus, ecartes, _ = ecarter(["A", "B"], fenetre=7, dates={"A": 3, "B": 30})
    assert retenus == ["B"]
    assert ecartes[0]["symbol"] == "A" and ecartes[0]["days"] == 3
    assert "binaire" in ecartes[0]["reason"]


def test_le_jour_meme_est_ecarte_et_la_borne_est_inclusive():
    _, ecartes, _ = ecarter(["A", "B", "C"], fenetre=7, dates={"A": 0, "B": 7, "C": 8})
    assert [e["symbol"] for e in ecartes] == ["A", "B"]      # 8 jours passe, 7 non


def test_date_inconnue_est_conservee_MAIS_publiee():
    """L'exclure viderait la sélection ; la garder en silence laisserait croire que le
    filtre l'a couverte. Il ne l'a pas couverte — et il le dit."""
    retenus, ecartes, inconnus = ecarter(["ALI=F", "A"], fenetre=7, dates={"ALI=F": None, "A": 30})
    assert retenus == ["ALI=F", "A"] and ecartes == []
    assert inconnus == ["ALI=F"]


def test_fenetre_nulle_desactive_le_filtre_sans_appeler_le_reseau():
    retenus, ecartes, inconnus = ecarter(["A", "B"], fenetre=0)
    assert retenus == ["A", "B"] and ecartes == [] and inconnus == []


def test_les_ecartes_sont_tries_du_plus_urgent_au_moins_urgent():
    _, ecartes, _ = ecarter(list("ABC"), fenetre=10, dates={"A": 9, "B": 1, "C": 5})
    assert [e["days"] for e in ecartes] == [1, 5, 9]


def test_liste_vide_ne_declenche_aucun_appel():
    assert dates_resultats([]) == {}


def test_la_fenetre_par_defaut_vaut_celle_de_l_alerte_sur_positions_detenues():
    """Deux seuils différents pour le même risque finiraient par diverger silencieusement."""
    import inspect

    from packages.strategies.earnings_blackout import flag_positions
    defaut_alerte = inspect.signature(flag_positions).parameters["within"].default
    assert FENETRE_DEFAUT == defaut_alerte


def test_le_relevé_injecte_evite_tout_reseau(monkeypatch):
    """Un appelant qui a déjà mesuré ne doit pas repayer le réseau."""
    import packages.portfolio.filtre_resultats as module

    def interdit(*a, **k):
        raise AssertionError("aucun appel réseau ne devait avoir lieu")

    monkeypatch.setattr(module, "dates_resultats", interdit)
    retenus, _, _ = ecarter(["A"], fenetre=7, dates={"A": 30})
    assert retenus == ["A"]


def test_maintenant_est_injectable_pour_une_mesure_reproductible():
    """Sans date injectable, le test dépendrait du jour où il tourne."""
    import inspect
    assert "maintenant" in inspect.signature(ecarter).parameters
    assert isinstance(datetime.now(UTC), datetime)
