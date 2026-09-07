"""Recommandation d'univers — la sélection vient du screening, les poids du risque.

Séries SYNTHÉTIQUES : on valide la mécanique (élagage, T/N, publication des écartés),
jamais un chiffre de marché. Le mandat données-réelles s'applique à la production.
"""
import numpy as np
import pytest

from packages.portfolio.recommendation import (
    MIN_ACTIFS,
    RATIO_T_SUR_N_MIN,
    elaguer,
    recommander,
)


def _serie(debut: str, n: int, graine: int) -> dict[str, float]:
    """n clôtures ouvrées consécutives à partir de `debut`, marche aléatoire positive."""
    rng = np.random.default_rng(graine)
    dates = np.busday_range = [str(d) for d in
                               np.arange(np.datetime64(debut), np.datetime64(debut) + np.timedelta64(n * 2, "D"),
                                         np.timedelta64(1, "D"))][:n]
    prix = 100 * np.cumprod(1 + rng.normal(0, 0.01, size=n))
    return dict(zip(dates, prix.tolist()))


def test_elaguer_retire_l_actif_qui_borne_l_intersection():
    """Un nouvel entrant réduit la fenêtre commune à rien : c'est LUI qu'on retire."""
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    series["NEUF"] = _serie("2025-01-01", 40, 99)          # historique très récent et court
    retenus, ecartes = elaguer(series, scores={s: 1.0 for s in series})
    assert "NEUF" not in retenus
    assert [e["symbol"] for e in ecartes] == ["NEUF"]
    assert ecartes[0]["start"] == "2025-01-01"             # la raison est CHIFFRÉE, pas vague


def test_elaguer_respecte_le_ratio_t_sur_n():
    """Trop d'actifs pour la fenêtre disponible : on réduit N jusqu'à T/N ≥ seuil."""
    series = {f"A{i}": _serie("2024-01-01", 200, i) for i in range(12)}
    retenus, _ = elaguer(series, scores={s: float(i) for i, s in enumerate(series)})
    dates_communes = set.intersection(*(set(v) for v in retenus.values()))
    assert len(dates_communes) >= RATIO_T_SUR_N_MIN * len(retenus)


def test_elaguer_ne_descend_jamais_sous_le_plancher():
    """Même si rien ne satisfait le ratio, on garde MIN_ACTIFS — et on ne boucle pas."""
    series = {f"A{i}": _serie("2025-01-01", 70, i) for i in range(6)}
    retenus, ecartes = elaguer(series, scores={s: 1.0 for s in series})
    assert len(retenus) == MIN_ACTIFS
    assert len(ecartes) == 3


def test_departage_par_score_a_date_de_debut_egale():
    """Deux débuts identiques : le moins bien classé part en premier."""
    series = {"BON": _serie("2025-01-01", 40, 1), "MAUVAIS": _serie("2025-01-01", 40, 2)}
    series |= {f"A{i}": _serie("2020-01-01", 900, i + 10) for i in range(4)}
    retenus, ecartes = elaguer(series, scores={"BON": 5.0, "MAUVAIS": 0.1})
    # Les deux partent (leur fenêtre 2025 ne croise pas les séries 2020), mais l'ORDRE
    # porte l'information : à date de début égale, le moins bien classé sort d'abord.
    assert [e["symbol"] for e in ecartes] == ["MAUVAIS", "BON"]
    assert set(retenus) == {"A0", "A1", "A2", "A3"}


def test_screening_indisponible_ne_recommande_rien():
    out = recommander({"available": False})
    assert out["available"] is False and "screening" in out["reason"]


def test_screening_trop_maigre_est_refuse_pas_complete():
    """Deux candidats ne font pas une recommandation : on le dit, on n'invente pas."""
    out = recommander({"available": True, "rows": [{"symbol": "A", "score": 1.0}]})
    assert out["available"] is False and "minimum" in out["reason"]


def test_recommandation_publie_les_trois_profils_et_son_avertissement(monkeypatch):
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(6)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years: (series, {}, []))
    rows = [{"symbol": s, "name": f"Nom {s}", "sector": "Tech", "asset_class": "equity",
             "score": 3.0 - i, "reason": "momentum"} for i, s in enumerate(series)]
    out = recommander({"available": True, "rows": rows, "universe_size": 900,
                       "filters": ["dollar_volume >= 1e7"]}, n=6)
    assert out["available"] is True
    assert set(out["scenarios"]) == {"prudent", "neutre", "dynamique"}
    for profil, poids in out["scenarios"].items():
        assert len(poids) == len(out["symbols"]), profil
        # Tolérance = l'arrondi JSON à 6 décimales sur N lignes, pas un flou de calcul.
        assert abs(sum(poids) - 1.0) < 5e-7 * len(poids) + 1e-9, profil
        assert all(p >= -1e-12 for p in poids), profil          # long-only
    assert out["selection"]["universe_size"] == 900
    assert out["t_sur_n"] >= RATIO_T_SUR_N_MIN
    assert "pas validé hors échantillon" in out["caveat"]        # l'aveu est OBLIGATOIRE


def test_les_lignes_portent_le_nom_le_secteur_et_le_score(monkeypatch):
    """Le tableau doit être lisible sans aller chercher ailleurs ce qu'est le ticker."""
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years: (series, {}, []))
    rows = [{"symbol": s, "name": f"Nom {s}", "sector": "Santé", "asset_class": "equity",
             "score": 1.0, "reason": "value"} for s in series]
    out = recommander({"available": True, "rows": rows}, n=4)
    ligne = out["rows"][0]
    assert ligne["name"].startswith("Nom ") and ligne["sector"] == "Santé"
    assert ligne["score"] == 1.0 and set(("prudent", "neutre", "dynamique")) <= set(ligne)


def test_historiques_absents_sont_publies_pas_masques(monkeypatch):
    import packages.portfolio.recommendation as module
    monkeypatch.setattr(module, "charger_series", lambda symboles, years: ({}, {}, ["X", "Y", "Z"]))
    out = recommander({"available": True, "rows": [{"symbol": s, "score": 1.0} for s in "XYZW"]})
    assert out["available"] is False
    assert out["missing"] == ["X", "Y", "Z"]


@pytest.mark.parametrize("n", [3, 5, 10])
def test_n_demande_est_respecte_ou_expliqué(monkeypatch, n):
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2015-01-01", 2000, i) for i in range(n)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years: (series, {}, []))
    rows = [{"symbol": s, "score": 1.0} for s in series]
    out = recommander({"available": True, "rows": rows}, n=n)
    assert out["selection"]["asked"] == n
    assert out["selection"]["kept"] == len(out["symbols"]) <= n


def test_nom_vide_retombe_sur_le_ticker(monkeypatch):
    """Le screener publie parfois `name: ""` : la colonne ne doit pas rester blanche."""
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years: (series, {}, []))
    rows = [{"symbol": s, "name": "", "sector": "", "score": 1.0} for s in series]
    out = recommander({"available": True, "rows": rows}, n=4)
    assert all(ligne["name"] == ligne["symbol"] for ligne in out["rows"])
