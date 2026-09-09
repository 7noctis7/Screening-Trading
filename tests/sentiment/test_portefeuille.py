"""Sentiment d'un portefeuille FOURNI — pondération, honnêteté, et non-persistance.

Le test qui compte le plus ici n'est pas le calcul : c'est `test_..._n_ecrit_rien`.
`/api/portfolio/*` promet « aucune persistance ». Un portefeuille de passage qui
alimenterait `sentiment_history.json` fausserait le Δ du lendemain pour le robot
lui-même, avec des symboles qu'il ne détient pas — une contamination silencieuse et
invisible dans l'onglet qui la subit.
"""

from __future__ import annotations

import json

import packages.sentiment.history as H
from packages.sentiment.portefeuille import (
    analyse,
    contributions,
    humeur,
    lignes,
    score_momentum,
    symbole_flux,
)


def _serie(closes: list[float]) -> dict[str, float]:
    return {f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}": c for i, c in enumerate(closes)}


def test_le_momentum_saure_a_plus_ou_moins_un():
    assert score_momentum([100.0] * 64 + [200.0]) == 1.0
    assert score_momentum([100.0] * 64 + [10.0]) == -1.0


def test_une_serie_trop_courte_ne_donne_PAS_zero_mais_rien():
    """Zéro se lit « neutre ». Une série de 10 barres n'est pas un sentiment neutre."""
    assert score_momentum([100.0] * 10) is None


def test_le_momentum_reprend_EXACTEMENT_la_formule_de_l_onglet_robot():
    closes = [100.0] * 64 + [110.0]
    attendu = round(max(-1.0, min(1.0, (closes[-1] / closes[-64] - 1) * 3.0)), 4)
    assert score_momentum(closes) == attendu


def test_les_series_sont_triees_par_DATE_pas_par_ordre_d_insertion():
    """Un dict JSON n'a aucun ordre chronologique garanti : trier est obligatoire."""
    croissant = _serie([100.0] * 64 + [130.0])
    melange = dict(reversed(list(croissant.items())))
    lignes_ = lignes(["X"], use_news=False, series={"X": melange})
    assert lignes_[0]["score"] == score_momentum([100.0] * 64 + [130.0])


def test_une_paire_crypto_est_traduite_pour_le_flux():
    assert symbole_flux("BTC/USDC") == "BTC-USD"
    assert symbole_flux("AAPL") == "AAPL"


def test_l_humeur_ponderee_DIFFERE_de_la_moyenne_simple():
    rows = [{"symbol": "GROS", "score": -0.8, "disponible": True, "origine": "news"},
            {"symbol": "PETIT", "score": 0.8, "disponible": True, "origine": "news"}]
    h = humeur(rows, {"GROS": 0.9, "PETIT": 0.1})
    assert h["mood"] == 0.0                      # à poids égal : les deux s'annulent
    assert h["mood_pondere"] < -0.6              # au capital : le portefeuille souffre
    assert h["mood_pondere_label"] == "bearish"


def test_une_couverture_partielle_est_RENORMALISEE_et_dite():
    rows = [{"symbol": "A", "score": -0.5, "disponible": True, "origine": "news"},
            {"symbol": "B", "score": None, "disponible": False,
             "origine": "indisponible"}]
    h = humeur(rows, {"A": 0.3, "B": 0.7})
    assert h["mood_pondere"] == -0.5             # pas -0.15 : B n'est pas « neutre »
    assert h["poids_non_mesure"] == 0.7
    assert h["n_mesurees"] == 1 and h["n_lignes"] == 2


def test_sans_aucune_ligne_mesuree_l_humeur_est_NONE_jamais_zero():
    h = humeur([{"symbol": "A", "score": None, "disponible": False,
                 "origine": "indisponible"}], {"A": 1.0})
    assert h["mood"] is None and h["mood_pondere"] is None
    assert h["mood_label"] == "inconnu"


def test_la_couverture_news_distingue_news_et_repli_momentum():
    rows = [{"symbol": "A", "score": 0.4, "disponible": True, "origine": "news"},
            {"symbol": "B", "score": 0.4, "disponible": True, "origine": "momentum"}]
    h = humeur(rows, {"A": 0.25, "B": 0.75})
    assert h["poids_mesure"] == 1.0
    assert h["couverture_news"] == 0.25          # 3/4 du capital n'a AUCUNE actualité


def test_les_contributions_classent_par_influence_absolue():
    rows = [{"symbol": "A", "score": 0.2, "disponible": True},
            {"symbol": "B", "score": -0.9, "disponible": True}]
    c = contributions(rows, {"A": 0.5, "B": 0.5}, -0.35)
    assert [x["symbol"] for x in c] == ["B", "A"]
    assert abs(sum(x["contribution"] for x in c) - (-0.35)) < 1e-9


def test_l_analyse_d_un_portefeuille_n_ecrit_RIEN(tmp_path, monkeypatch):
    """Sabotage : historique pointé sur un fichier neuf ; il doit rester absent."""
    cible = tmp_path / "sentiment_history.json"
    monkeypatch.setattr(H, "_F", cible)
    out = analyse([{"symbol": "AAA", "weight": 1.0}], use_news=False,
                  series={"AAA": _serie([100.0] * 64 + [120.0])}, fils=False)
    # le Δ a bien été CALCULÉ (sinon le test passerait pour la mauvaise raison : une
    # exception avalée n'écrit rien non plus)
    assert out["historique_jours"] == 0 and "score_change" in out["rows"][0]
    assert out["rows"][0]["score_change"] is None      # aucun passé = inconnu, pas 0,0
    assert not cible.exists(), "un portefeuille de passage a écrit dans l'historique"


def test_le_snapshot_du_robot_lui_CONTINUE_d_ecrire(tmp_path, monkeypatch):
    """Garde-fou du test précédent : si `record_and_delta` n'écrivait plus, il
    passerait lui aussi — sans rien garantir."""
    cible = tmp_path / "sentiment_history.json"
    monkeypatch.setattr(H, "_F", cible)
    H.record_and_delta({"AAA": 0.5}, today="2024-01-01")
    assert json.loads(cible.read_text())[-1]["scores"] == {"AAA": 0.5}


def test_delta_lit_l_historique_sans_le_modifier(tmp_path, monkeypatch):
    cible = tmp_path / "sentiment_history.json"
    cible.write_text(json.dumps([{"date": "2024-01-01", "scores": {"AAA": 0.2}}]))
    monkeypatch.setattr(H, "_F", cible)
    d = H.delta({"AAA": 0.6}, today="2024-01-02")
    assert d["by_symbol"]["AAA"] == 0.4 and d["history_days"] == 1
    assert json.loads(cible.read_text()) == [
        {"date": "2024-01-01", "scores": {"AAA": 0.2}}]


def test_l_analyse_trie_les_lignes_par_poids_decroissant():
    out = analyse([{"symbol": "PETIT", "weight": 0.1},
                   {"symbol": "GROS", "weight": 0.9}], use_news=False, fils=False)
    assert [r["symbol"] for r in out["rows"]] == ["GROS", "PETIT"]
    assert out["available"] is True


def test_sans_AUCUNE_mesure_la_source_ne_credite_pas_le_momentum():
    """Dire « dérivé du momentum » quand aucun momentum n'a tourné attribue le vide
    à une méthode qui n'a jamais été appelée — le lecteur croit à un résultat."""
    out = analyse([{"symbol": "AAA", "weight": 1.0}], use_news=False, series={}, fils=False)
    assert "aucune mesure possible" in out["source"]
    assert out["mood_pondere"] is None and out["poids_non_mesure"] == 1.0


def test_la_revision_NE_compare_PAS_deux_paniers_differents(tmp_path, monkeypatch):
    """Le défaut mesuré le 09/09 : `history.mood_delta` soustrayait la moyenne du
    portefeuille de l'utilisateur à la moyenne HISTORISÉE du robot — deux paniers
    sans rapport. Ici l'historique ne contient QUE des titres du robot ; la révision
    de l'utilisateur doit rester inconnue, pas prendre la valeur du robot."""
    cible = tmp_path / "sentiment_history.json"
    cible.write_text(json.dumps([
        {"date": "2024-01-01", "scores": {"ROBOT1": -0.9, "ROBOT2": -0.9}},
        {"date": "2024-01-02", "scores": {"ROBOT1": -0.9, "ROBOT2": -0.9}}]))
    monkeypatch.setattr(H, "_F", cible)
    out = analyse([{"symbol": "AAA", "weight": 1.0}], use_news=False,
                  series={"AAA": _serie([100.0] * 64 + [110.0])}, fils=False)
    assert out["mood_change"] is None, "un panier étranger a produit une révision"
    assert out["n_revisions"] == 0
    assert out["rows"][0]["score_change"] is None


def test_la_revision_est_PONDEREE_par_les_poids():
    """Chaque actif comparé à SON passé, puis pondéré comme l'humeur."""
    rows = [{"symbol": "GROS", "disponible": True, "score_change": -0.4},
            {"symbol": "PETIT", "disponible": True, "score_change": 0.4}]
    from packages.sentiment.portefeuille import _revision_ponderee
    m, n = _revision_ponderee(rows, {"GROS": 0.9, "PETIT": 0.1}, {"GROS", "PETIT"})
    assert m == -0.32 and n == 2                 # 0,9·(−0,4) + 0,1·(+0,4)


def test_une_ligne_sans_historique_est_EXCLUE_pas_comptee_a_zero():
    """L'inclure à 0 diluerait la révision vers zéro et se lirait « stable »."""
    rows = [{"symbol": "A", "disponible": True, "score_change": -0.6},
            {"symbol": "B", "disponible": True, "score_change": None}]
    from packages.sentiment.portefeuille import _revision_ponderee
    m, n = _revision_ponderee(rows, {"A": 0.5, "B": 0.5}, {"A"})
    assert m == -0.6 and n == 1                  # pas -0.3
