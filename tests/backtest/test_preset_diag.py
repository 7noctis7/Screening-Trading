"""Pourquoi le preset ne demande-t-il RIEN ? — la question sans réponse du 26/08.

Le compte paper ne contenait AUCUNE action du satellite. Trois hypothèses successives
sur la cause — plancher de ligne, horaires de marché, mode léger — se sont toutes
révélées FAUSSES, précisément parce qu'aucune trace ne disait où la chaîne s'arrêtait.
Le coût du silence a dépassé celui du défaut.

Ces tests vérifient que chaque cause d'arrêt est nommée, et surtout que le diagnostic
ne change AUCUN chiffre.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from packages.backtest.preset_diag import Diag
from packages.backtest.preset_weights import (
    preset_latest_weights,
    preset_latest_weights_explique,
)


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _serie(seed: int, n: int = 900, drift: float = 0.0004) -> list:
    rng = np.random.default_rng(seed)
    t0 = datetime(2021, 1, 1, tzinfo=UTC)
    px = 100 * np.cumprod(1 + rng.normal(drift, 0.012, n))
    return [Bar(t0 + timedelta(days=j), *(4 * [float(px[j])]), 1e6) for j in range(n)]


def _panier(n_titres: int = 20, n_barres: int = 900, seed: int = 0) -> dict:
    return {f"S{i:02d}": _serie(seed * 100 + i, n_barres) for i in range(n_titres)}


# --- LE point : le diagnostic ne change rien --------------------------------

def test_les_poids_sont_identiques_avec_ou_sans_diagnostic():
    """Un diagnostic qui modifie ce qu'il observe ne vaut rien."""
    for essai in range(5):
        data = _panier(seed=essai)
        rq = np.random.default_rng(essai)
        qual = {s: float(rq.random()) for s in data}
        assert preset_latest_weights(data, qual, top_k=12) == \
            preset_latest_weights_explique(data, qual, top_k=12)[0]


# --- chaque cause d'arrêt est NOMMÉE ----------------------------------------

def test_trop_peu_de_titres_eligibles():
    data = _panier(n_titres=3)
    poids, d = preset_latest_weights_explique(data, {})
    assert poids == {} and d.bloque
    assert "éligibles" in d.arret


def test_historique_trop_court_pour_la_mm200():
    """`regime_mult` lit une MM200 : sous 200 barres, aucun titre n'est éligible."""
    data = _panier(n_titres=20, n_barres=150)
    poids, d = preset_latest_weights_explique(data, {})
    assert poids == {} and d.bloque


def test_le_repli_sans_score_qualite_est_TRACÉ():
    """Le repli reste un INCIDENT à signaler, même maintenant qu'il est principiel.

    `len(q) >= 5` basculait sur un autre comportement sans un mot. Le basculement
    est désormais tracé — et la stratégie de repli est le momentum, plus l'ordre
    du dictionnaire (cf. `test_le_repli_sans_score_choisit_par_MOMENTUM_...`).
    """
    data = _panier(n_titres=20)
    _poids, d = preset_latest_weights_explique(data, {})      # aucun score
    trace = dict(d.etapes)
    assert "repli" in trace["score qualité"].lower()
    assert "MOMENTUM" in trace["score qualité"]


def test_avec_scores_la_selection_est_par_qualite():
    data = _panier(n_titres=20)
    rq = np.random.default_rng(1)
    _poids, d = preset_latest_weights_explique(
        data, {s: float(rq.random()) for s in data}, top_k=12)
    trace = dict(d.etapes)
    assert "top-12 par qualité" in trace["score qualité"]
    assert "REPLI" not in trace["score qualité"]


def test_chaque_porte_publie_son_effet():
    """Ce qui manquait le plus : QUELLE porte réduit l'exposition, et de combien."""
    data = _panier(n_titres=20)
    rq = np.random.default_rng(2)
    _poids, d = preset_latest_weights_explique(
        data, {s: float(rq.random()) for s in data}, top_k=12)
    assert set(d.gross) >= {"DD-target", "régime", "ampleur"}
    assert all(0.0 <= v <= 1.0 for v in d.gross.values())


def test_exposition_nulle_nomme_la_porte_responsable():
    """Un marché en chute profonde met la porte de régime à zéro : légitime, mais qui
    doit être AFFICHÉ, pas deviné."""
    data = {f"S{i:02d}": _serie(500 + i, 900, drift=-0.004) for i in range(20)}
    rq = np.random.default_rng(3)
    poids, d = preset_latest_weights_explique(
        data, {s: float(rq.random()) for s in data}, top_k=12)
    if not poids:
        assert d.bloque
        assert "brute NULLE" in d.arret or "seuil" in d.arret


# --- lisibilité et sérialisation --------------------------------------------

def test_resume_est_lisible_et_ordonne():
    d = Diag()
    d.note("éligibles", "788 titres")
    d.porte("régime", 0.0)
    d.stop("exposition brute NULLE")
    r = d.resume()
    assert "788 titres" in r and "ARRÊT" in r
    assert r.index("788") < r.index("ARRÊT")     # les étages avant la cause


def test_le_premier_arret_gagne():
    """La CAUSE est le premier étage qui bloque, pas le dernier message écrit."""
    d = Diag()
    d.stop("cause racine")
    d.stop("conséquence")
    assert d.arret == "cause racine"


def test_as_dict_est_serialisable_json():
    import json
    data = _panier(n_titres=20)
    _poids, d = preset_latest_weights_explique(data, {}, top_k=12)
    json.dumps(d.as_dict())          # le snapshot le publie : il doit passer en JSON
    assert set(d.as_dict()) == {"etapes", "portes", "arret", "bloque"}


# --- LE défaut de production du 26/08 ---------------------------------------

def _panier_ordonne_du_pire_au_meilleur(n: int = 20) -> dict:
    """Les PREMIERS du dictionnaire sont les pires titres, les derniers les meilleurs.

    Reproduit ce qui piégeait la production : le repli prenait les `top_k` premiers
    dans l'ordre du dictionnaire, sans aucun lien avec leur qualité ni leur momentum.
    """
    data = {}
    for i in range(n):
        data[f"A{i:02d}"] = _serie(i, 900, drift=-0.0015)        # mauvais, en tête
    for i in range(n):
        data[f"Z{i:02d}"] = _serie(100 + i, 900, drift=+0.0015)  # bons, en fin
    return data


def test_le_repli_sans_score_choisit_par_MOMENTUM_pas_par_ordre_de_dict():
    """LE défaut constaté en production. `make live` tourne en mode LÉGER, qui coupe la
    section `fundamentals` : `quality` est donc TOUJOURS vide à l'exécution, et le repli
    tirait les 12 premiers symboles de `data`.

    Conséquence en chaîne : `mkt`, l'indice de marché des portes de régime et d'ampleur,
    était la moyenne de ces 12 noms arbitraires. Les portes concluaient « chute > 15 %,
    aucun titre au-dessus de sa MM200 » et mettaient l'exposition brute à ZÉRO. Le
    satellite actions était vide non par décision de risque, mais parce qu'on mesurait
    le risque d'un panier tiré au hasard.
    """
    poids, d = preset_latest_weights_explique(
        _panier_ordonne_du_pire_au_meilleur(), {}, top_k=12)   # AUCUN score → repli
    assert poids, "le repli momentum doit produire un univers exploitable"
    assert all(s.startswith("Z") for s in poids), \
        f"le repli a retenu des titres de tête de dict : {sorted(poids)}"
    trace = dict(d.etapes)
    assert "MOMENTUM" in trace["score qualité"]
    assert "ARBITRAIRE" not in trace["score qualité"]


def test_le_repli_momentum_ne_ferme_pas_les_portes():
    """Contre-épreuve directe du symptôme : avec un univers sensé, l'exposition brute
    n'est plus annulée par les portes."""
    _poids, d = preset_latest_weights_explique(
        _panier_ordonne_du_pire_au_meilleur(), {}, top_k=12)
    assert d.gross.get("régime", 0.0) > 0.0
    assert d.gross.get("ampleur", 0.0) > 0.0
    assert not d.bloque
