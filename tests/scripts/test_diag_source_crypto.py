"""Le diagnostic doit nommer LA bonne cause : les gestes de réparation sont opposés.

Forcer le bon ticker, retirer la série ou changer de source : se tromper de cause,
c'est réparer ce qui marche et laisser en place ce qui ment. Chaque test construit une
série dont la cause est CONNUE et vérifie que le verdict la retrouve.
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


def test_un_homonyme_illiquide_est_une_collision_pas_un_flux_arrete() -> None:
    """L'ordre des verdicts, corrigé par les données réelles du 09/09.

    UNI et ARB sortaient « FLUX ARRÊTÉ » (figées 24 et 174 séances) alors que leur
    corrélation à la référence valait +0,25 et +0,04 : la base contient un homonyme
    illiquide, dont l'immobilité est le SYMPTÔME, pas la cause. Les deux gestes sont
    opposés — changer de source, ou retirer la série — donc l'ordre décide du geste.
    """
    autre = _marche(graine=3)
    autre[300:] = autre[299]                   # homonyme illiquide : plus de cotation
    fiche = diagnostiquer("ARB", _serie(autre), _serie(_marche(graine=4)))
    assert fiche["figee"] >= 300, "contrôle inopérant : la série n'est pas figée"
    assert fiche["verdict"] == "COLLISION DE TICKER", fiche


def test_un_arrondi_prime_sur_la_plage_figee_qu_il_fabrique() -> None:
    """SHIB, mesuré le 09/09 : corr +0,80 — c'est le BON jeton — mais 3 % de clôtures
    distinctes et des plages de 61 séances. L'arrondi produit les plages ; les nommer
    « flux arrêté » ferait retirer une série qu'il suffit de resourcer."""
    prix = _marche()
    grossier = np.round(prix * 1e-7, 6)
    fiche = diagnostiquer("SHIB", _serie(grossier), _serie(prix * 1e-7))
    assert fiche["corr"] > 0.5, "contrôle inopérant : ce n'est pas le bon jeton"
    assert fiche["figee"] >= 20, "contrôle inopérant : aucune plage figée fabriquée"
    assert fiche["verdict"] == "PRÉCISION", fiche


def test_une_serie_qui_s_arrete_des_annees_avant_les_autres_est_perimee() -> None:
    """Trouvé sur données réelles le 09/09 : MATIC s'arrête en mars 2025, RNDR en
    juillet 2024, IMX en juillet 2022 — pendant que le reste du lot cote en 2026.

    Ces jetons ont migré ou été délistés. Rien dans leur série ne cloche : elle est
    juste MORTE. Sans contrôle de fraîcheur, elles sortaient « CONFORMES » et
    continuaient de peupler l'univers en se faisant passer pour vivantes.
    """
    prix = _marche(n=400)
    vieille = _serie(prix)                      # se termine ~400 jours après le départ
    fiche = diagnostiquer("MATIC", vieille, _serie(prix), dernier_jour="2026-09-07")
    assert fiche["retard"] > 1000, fiche["retard"]
    assert fiche["verdict"] == "PÉRIMÉE", fiche


def test_une_serie_a_jour_n_est_pas_perimee() -> None:
    """Contrôle négatif : sans lui, tout le lot sortirait « PÉRIMÉE » et le verdict
    ne vaudrait rien."""
    prix = _marche(n=400)
    serie = _serie(prix)
    fiche = diagnostiquer("ETH", serie, _serie(prix), dernier_jour=serie[-1][0])
    assert fiche["retard"] == 0
    assert fiche["verdict"] == "CONFORME", fiche


def test_sans_lot_de_reference_aucune_serie_n_est_declaree_perimee() -> None:
    """La fraîcheur se mesure contre le lot. Sans lot, on ne conclut pas."""
    prix = _marche(n=400)
    fiche = diagnostiquer("ETH", _serie(prix), _serie(prix))
    assert fiche["retard"] == 0 and fiche["verdict"] == "CONFORME"


def test_un_ticker_reattribue_est_nomme_serie_recollee() -> None:
    """L'anomalie qui faisait se contredire l'instrument, trouvée le 09/09.

    `OP` est sorti CONFORME (corr +1,00 sur les 640 jours récents) puis COLLISION
    (corr −0,00 sur 1559 jours) d'un passage à l'autre — seule la fenêtre de référence
    avait changé. Ce n'était pas une contradiction : la série est RECOLLÉE, juste depuis
    la réattribution du ticker et étrangère avant. Une seule corrélation ne peut pas le
    dire, et le verdict dépendait alors de la fenêtre interrogée.
    """
    ancien, recent = _marche(n=800, graine=5), _marche(n=500, graine=6)
    serie = _serie(list(ancien) + list(recent))
    reference = _serie(list(_marche(n=800, graine=7)) + list(recent))

    fiche = diagnostiquer("OP", serie, reference)
    assert fiche["corr"] < 0.5, fiche["corr"]
    assert fiche["corr_recente"] > 0.9, fiche["corr_recente"]
    assert fiche["verdict"] == "SÉRIE RECOLLÉE", fiche


def test_une_collision_franche_n_est_pas_prise_pour_un_recollage() -> None:
    """Contrôle négatif : si tout sortait « recollé », le diagnostic ne dirait plus rien
    — et laisserait croire que les données récentes sont bonnes alors qu'elles ne le
    sont pas."""
    fiche = diagnostiquer("UNI", _serie(_marche(graine=1)), _serie(_marche(graine=2)))
    assert fiche["verdict"] == "COLLISION DE TICKER", fiche
    assert not fiche["recollee"]
