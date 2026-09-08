"""Le diagnostic doit nommer LA bonne cause : les gestes de réparation sont opposés.

Forcer le bon ticker, retirer la série ou changer de source : se tromper de cause,
c'est réparer ce qui marche et laisser en place ce qui ment. Chaque test construit une série
dont la cause est CONNUE et vérifie que le verdict la retrouve.
"""

from __future__ import annotations

import numpy as np

from scripts.diag_source_crypto import (
    _plus_longue_plage_figee,
    diagnostiquer,
    lire_base,
)


def _serie(closes, depart: int = 0) -> list[tuple[str, float]]:
    """[(date, clôture)] sur des jours calendaires consécutifs."""
    from datetime import date, timedelta
    d0 = date(2022, 1, 1) + timedelta(days=depart)
    return [((d0 + timedelta(days=i)).isoformat(), float(c))
            for i, c in enumerate(closes)]


def _marche(n: int = 600, vol: float = 0.04, graine: int = 0) -> np.ndarray:
    g = np.random.default_rng(graine)
    return 100.0 * np.exp(np.cumsum(g.normal(0, vol, n)))


def test_une_serie_qui_suit_la_reference_est_conforme() -> None:
    """Contrôle négatif : sans lui, un diagnostic qui crie « collision » partout
    passerait tous les autres tests."""
    prix = _marche()
    fiche = diagnostiquer("ETH", _serie(prix), _serie(prix * 1.001))
    assert fiche["verdict"] == "CONFORME", fiche
    assert fiche["corr"] > 0.99


def test_un_autre_jeton_sous_le_meme_ticker_est_demasque() -> None:
    """LE cas visé. `UNI-USD` chez Yahoo peut désigner un homonyme illiquide : la série
    est propre de forme et fausse de bout en bout. Seule la confrontation le voit."""
    fiche = diagnostiquer("UNI", _serie(_marche(graine=1)), _serie(_marche(graine=2)))
    assert fiche["collision"], fiche
    assert fiche["verdict"] == "COLLISION DE TICKER", fiche


def test_un_flux_arrete_est_nomme_comme_tel() -> None:
    """Une plage figée se lit sur la série seule — pas besoin de référence pour la voir,
    et le geste (retirer) n'est pas celui d'une collision (forcer le ticker)."""
    prix = _marche()
    prix[300:] = prix[299]
    fiche = diagnostiquer("SHIB", _serie(prix), _serie(_marche()))
    assert fiche["verdict"] == "FLUX ARRÊTÉ", fiche
    assert fiche["figee"] >= 300


def test_un_arrondi_destructeur_est_distingue_d_un_flux_arrete() -> None:
    """Un jeton à 0,00001 $ arrondi à six décimales bouge en marches d'escalier : la
    série n'est pas arrêtée, elle est trop grossière. Le geste est de changer de
    source, pas de forcer un ticker."""
    prix = np.round(_marche() * 1e-7, 6)          # ~1e-5 $ arrondi à 6 décimales
    fiche = diagnostiquer("SHIB", _serie(prix), _serie(_marche()))
    assert fiche["distinctes"] < 0.5, fiche["distinctes"]
    assert fiche["verdict"] in ("PRÉCISION", "FLUX ARRÊTÉ"), fiche


def test_sans_reference_le_verdict_reste_non_verifiable() -> None:
    """Le mandat données-réelles : pas de référence, pas de verdict inventé."""
    fiche = diagnostiquer("TON", _serie(_marche()), [])
    assert fiche["verdict"] == "NON VÉRIFIABLE", fiche
    assert not fiche["collision"]
    assert np.isnan(fiche["corr"])


def test_une_serie_trop_courte_est_une_source_absente() -> None:
    fiche = diagnostiquer("ARB", _serie(_marche(n=100)), _serie(_marche(n=100)))
    assert fiche["verdict"] == "SOURCE ABSENTE", fiche


def test_la_plage_figee_mesure_l_episode_entier() -> None:
    """Publier la longueur du SEUIL au lieu de celle de l'épisode minimiserait le
    problème — l'erreur exactement dans le sens qui rassure."""
    assert _plus_longue_plage_figee([1.0, 1.0, 1.0, 2.0, 3.0, 3.0]) == 3
    assert _plus_longue_plage_figee([1.0, 2.0, 3.0]) == 1
    assert _plus_longue_plage_figee([]) == 0


def test_une_base_absente_ne_leve_pas(tmp_path) -> None:
    """Sur une machine sans crypto.db, le diagnostic doit se taire, pas planter."""
    assert lire_base(tmp_path / "absente.db", "BTC-USD") == []
