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
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: (series, {}, []))
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
    # L'avertissement suit désormais l'ÉTAT de la mesure au lieu d'une formule figée.
    # Sans mesure d'IC (cas de ce test), il doit le dire — l'aveu reste obligatoire.
    assert "JAMAIS été mesuré" in out["caveat"]


def test_les_lignes_portent_le_nom_le_secteur_et_le_score(monkeypatch):
    """Le tableau doit être lisible sans aller chercher ailleurs ce qu'est le ticker."""
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: (series, {}, []))
    rows = [{"symbol": s, "name": f"Nom {s}", "sector": "Santé", "asset_class": "equity",
             "score": 1.0, "reason": "value"} for s in series]
    out = recommander({"available": True, "rows": rows}, n=4)
    ligne = out["rows"][0]
    assert ligne["name"].startswith("Nom ") and ligne["sector"] == "Santé"
    assert ligne["score"] == 1.0 and set(("prudent", "neutre", "dynamique")) <= set(ligne)


def test_historiques_absents_sont_publies_pas_masques(monkeypatch):
    import packages.portfolio.recommendation as module
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: ({}, {}, ["X", "Y", "Z"]))
    out = recommander({"available": True, "rows": [{"symbol": s, "score": 1.0} for s in "XYZW"]})
    assert out["available"] is False
    assert out["missing"] == ["X", "Y", "Z"]


@pytest.mark.parametrize("n", [3, 5, 10])
def test_n_demande_est_respecte_ou_expliqué(monkeypatch, n):
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2015-01-01", 2000, i) for i in range(n)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: (series, {}, []))
    rows = [{"symbol": s, "score": 1.0} for s in series]
    out = recommander({"available": True, "rows": rows}, n=n)
    assert out["selection"]["asked"] == n
    assert out["selection"]["kept"] == len(out["symbols"]) <= n


# Un test RETIRÉ le 07/09, et la raison vaut d'être gardée. Il exigeait qu'un nom vide
# retombe sur le ticker, « pour que la colonne ne reste pas blanche ». C'était traiter un
# symptôme d'affichage au prix de la vérité : « BK / BK » se lit comme une identification
# alors que rien n'a été identifié, et le lecteur croit avoir vérifié. La règle est
# désormais l'inverse — un nom absent reste absent — et elle est vérifiée par
# `test_nom_absent_reste_absent_et_ne_repete_pas_le_ticker`.


# --- Profil « Conviction » : le seul que la MESURE a le droit d'interdire ----------------

def _reco_avec_ic(monkeypatch, ic):
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2018-01-01", 2000, i) for i in range(6)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: (series, {}, []))
    monkeypatch.setattr(module, "charger_ic", lambda *a, **k: ic)
    rows = [{"symbol": s, "score": 2.0 - i * 0.3} for i, s in enumerate(series)]
    return recommander({"available": True, "rows": rows}, n=6)


def test_sans_mesure_d_ic_le_profil_conviction_n_existe_pas(monkeypatch):
    """Pas de repli silencieux vers HRP sous un nom prometteur : le profil est ABSENT."""
    out = _reco_avec_ic(monkeypatch, None)
    assert "conviction" not in out["scenarios"]
    assert "jamais mesuré" in out["conviction_reason"].lower()
    assert "JAMAIS été mesuré" in out["caveat"]


def test_ic_mesure_mais_non_robuste_refuse_le_profil_et_dit_les_deux_moities(monkeypatch):
    ic = {"available": True, "ic_moyen": 0.08, "robuste": False, "n_dates": 40,
          "horizon": 21, "ic_premiere_moitie": 0.16, "ic_seconde_moitie": 0.00}
    out = _reco_avec_ic(monkeypatch, ic)
    assert "conviction" not in out["scenarios"]
    assert "+0.1600" in out["conviction_reason"] and "+0.0000" in out["conviction_reason"]
    assert "NON robuste" in out["caveat"]


def test_ic_robuste_ouvre_le_profil_conviction(monkeypatch):
    ic = {"available": True, "ic_moyen": 0.06, "robuste": True, "n_dates": 40,
          "horizon": 21, "ic_premiere_moitie": 0.07, "ic_seconde_moitie": 0.05}
    out = _reco_avec_ic(monkeypatch, ic)
    assert "conviction" in out["scenarios"]
    poids = out["scenarios"]["conviction"]
    assert len(poids) == len(out["symbols"])
    assert abs(sum(poids) - 1.0) < 5e-7 * len(poids) + 1e-9
    assert all(p >= -1e-12 for p in poids)                    # long-only
    assert "robuste hors échantillon" in out["caveat"]


def test_un_ic_plus_fort_ecarte_davantage_les_poids_du_prior(monkeypatch):
    """Grinold : l'amplitude des vues vaut IC × σ × z. Un IC faible DOIT donner un
    postérieur proche du prior — c'est ce qui empêche une conviction non mesurée de
    déplacer un euro. On vérifie la monotonie, pas une valeur."""
    faible = _reco_avec_ic(monkeypatch, {"available": True, "ic_moyen": 0.005, "robuste": True,
                                         "n_dates": 40, "horizon": 21})
    fort = _reco_avec_ic(monkeypatch, {"available": True, "ic_moyen": 0.25, "robuste": True,
                                       "n_dates": 40, "horizon": 21})
    import numpy as np
    prior = np.array(faible["scenarios"]["neutre"])
    ecart_faible = float(np.abs(np.array(faible["scenarios"]["conviction"]) - prior).sum())
    ecart_fort = float(np.abs(np.array(fort["scenarios"]["conviction"]) - prior).sum())
    assert ecart_fort > ecart_faible


# --- Contrainte de profil : le déclaré BORNE le calculé ----------------------------------

PROFIL = {"horizon_annees": 10, "perte_max_toleree": 0.25, "part_du_patrimoine": 0.5,
          "besoin_liquidite": 0.0, "revenus_stables": True, "experience_annees": 2}


def _cov(vols):
    import numpy as np
    return np.diag(np.asarray(vols, dtype=float) ** 2)


def test_plafond_projette_sur_le_simplex_sans_depasser():
    """Un `min(w, cap)` suivi d'une renormalisation ferait REPASSER au-dessus du plafond."""
    from packages.portfolio.recommendation import _plafonner
    poids, actives, _ = _plafonner([0.70, 0.20, 0.05, 0.05], 0.30)
    assert max(poids) <= 0.30 + 1e-9
    assert abs(sum(poids) - 1.0) < 1e-9
    assert actives == 1


def test_plafond_infaisable_ne_bricole_pas():
    """3 actifs × 20 % < 100 % : on rend l'entrée telle quelle plutôt qu'un faux résultat."""
    from packages.portfolio.recommendation import _plafonner
    poids, actives, effet = _plafonner([0.5, 0.3, 0.2], 0.20)
    assert poids == [0.5, 0.3, 0.2] and actives == 0 and effet == 0.0


def test_sans_profil_l_exposition_reste_totale():
    from packages.portfolio.recommendation import contraindre
    out = contraindre([0.5, 0.5], _cov([0.30, 0.30]), 1.0, None)
    assert out["exposition"] == 1.0 and out["cash"] == 0.0
    assert out["budget_perte"] is None


def test_le_budget_de_perte_reduit_l_exposition_et_sort_du_cash():
    """Actifs très volatils + budget déclaré : l'outil REFUSE d'être investi à 100 %."""
    from packages.portfolio.recommendation import contraindre
    out = contraindre([0.5, 0.5], _cov([0.60, 0.60]), 1.0, PROFIL)
    assert 0.0 < out["exposition"] < 1.0
    assert out["cash"] == pytest.approx(1.0 - out["exposition"])
    # La volatilité APRÈS exposition ATTEINT la cible : c'est la contrainte, pas une marge.
    assert out["vol_apres_exposition"] == pytest.approx(out["vol_cible"], rel=1e-6)


def test_des_actifs_calmes_ne_declenchent_aucune_reduction():
    """La contrainte ne prélève pas de cash quand elle n'a rien à protéger."""
    from packages.portfolio.recommendation import contraindre
    out = contraindre([0.5, 0.5], _cov([0.02, 0.02]), 1.0, PROFIL)
    assert out["exposition"] == 1.0 and out["cash"] == 0.0


def test_un_budget_plus_serre_laisse_plus_de_liquidites():
    """Monotonie : moins de perte acceptée ⇒ moins d'exposition. Jamais l'inverse."""
    from packages.portfolio.recommendation import contraindre
    cov = _cov([0.40, 0.40])
    serre = contraindre([0.5, 0.5], cov, 1.0, {**PROFIL, "perte_max_toleree": 0.10})
    large = contraindre([0.5, 0.5], cov, 1.0, {**PROFIL, "perte_max_toleree": 0.40})
    assert serre["exposition"] < large["exposition"]
    assert serre["cash"] > large["cash"]


def test_l_ordre_est_plafond_puis_exposition():
    """L'exposition se lit sur les poids DÉFINITIFS. Mesurer la volatilité d'une allocation
    qu'on ne détiendra pas donnerait une exposition fausse."""
    from packages.portfolio.recommendation import contraindre
    cov = _cov([0.80, 0.10, 0.10, 0.10])
    brut = [0.85, 0.05, 0.05, 0.05]
    libre = contraindre(brut, cov, 1.0, PROFIL)
    plafonne = contraindre(brut, cov, 0.30, PROFIL)
    assert plafonne["vol_annuelle"] < libre["vol_annuelle"]
    assert plafonne["exposition"] > libre["exposition"]


# --- Identification de l'instrument : ne jamais faire passer un ticker pour un nom -------

def test_nom_absent_reste_absent_et_ne_repete_pas_le_ticker(monkeypatch):
    """« BK / BK » a l'apparence d'une information et n'en est pas une : le lecteur croit
    avoir vérifié. Un nom manquant doit se voir comme manquant."""
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    monkeypatch.setattr(module, "charger_series", lambda symboles, years, classes=None: (series, {}, []))
    rows = [{"symbol": s, "name": "", "score": 1.0} for s in series]
    out = recommander({"available": True, "rows": rows}, n=4)
    assert all(ligne["name"] is None for ligne in out["rows"])


def test_la_ligne_porte_place_de_cotation_devise_et_alias(monkeypatch):
    """Trois identifiants qui EXISTENT déjà dans les seeds et n'étaient pas publiés."""
    import packages.portfolio.recommendation as module
    series = {f"A{i}": _serie("2020-01-01", 900, i) for i in range(4)}
    monkeypatch.setattr(module, "charger_series",
                        lambda symboles, years, classes=None: (series, {"A0": "A0-USD"}, []))
    rows = [{"symbol": s, "name": "Nom", "venue": "NASDAQ", "currency": "USD",
             "asset_class": "equity", "score": 1.0} for s in series]
    out = recommander({"available": True, "rows": rows}, n=4)
    ligne = next(r for r in out["rows"] if r["symbol"] == "A0")
    assert ligne["venue"] == "NASDAQ" and ligne["currency"] == "USD"
    assert ligne["alias"] == "A0-USD"                  # la série RÉELLEMENT valorisée
    assert ligne["lien"].endswith("/A0-USD")           # le lien suit l'alias, pas le ticker


def test_le_lien_utilise_le_symbole_exact_donc_echoue_de_facon_detectable():
    """Un lien déduit d'un NOM pourrait ouvrir la page d'une autre société — l'erreur même
    qu'on veut éviter. Indexé par le symbole utilisé, un identifiant faux donne une page
    visiblement fausse."""
    from packages.portfolio.recommendation import lien_source
    assert lien_source("BK") == "https://finance.yahoo.com/quote/BK"
    assert lien_source("ETH-USD").endswith("/ETH-USD")
