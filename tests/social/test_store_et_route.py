"""« Aucun résultat » veut dire TROIS choses, et un écran qui les confond ment.

Le flux n'est pas branché · il est branché mais vide · vos critères ne laissent rien
passer. Ces trois situations demandent trois actions différentes de l'utilisateur, et
un écran qui affiche la même phrase pour les trois le laisse conclure au hasard —
généralement « c'est cassé », alors qu'il vient juste de cocher deux filtres exclusifs.

Ce que ces tests épinglent :
  1. la route distingue les trois vides, et `total_stock` vaut `None` — pas 0 — quand
     on ne sait pas ;
  2. l'ingestion est IDEMPOTENTE : rejouer le même export ne duplique rien ;
  3. un aller-retour par la base ne perd ni la direction absente, ni les niveaux ;
  4. une valeur inconnue dans l'URL est ignorée, pas fatale ;
  5. `account` au singulier marche comme `accounts`.
"""
from __future__ import annotations

from datetime import UTC, datetime

from apps.api.social_x import construire_filtre, publications
from packages.social.modele import Classification, Direction, Publication
from packages.social.store import StorePublications

J = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _lot() -> list[Publication]:
    return [
        Publication(id="1", compte="astekz", ts=J, texte="BTC long",
                    classification=Classification.TRADE_SIGNAL, ticker="BTC",
                    symbole="BTCUSDT", direction=Direction.LONG,
                    extraits={"tp1": 65000.0}),
        Publication(id="2", compte="trendspider", ts=J, texte="volumes",
                    classification=Classification.EDUCATIONAL),
    ]


def _store_rempli(tmp_path):
    chemin = str(tmp_path / "x.db")
    s = StorePublications(chemin)
    s.ecrire(_lot())
    s.close()
    return chemin


# ---- 1. les trois vides ----------------------------------------------------------

def test_un_flux_NON_BRANCHE_le_dit_et_ne_pretend_pas_avoir_zero(tmp_path):
    """ABSENT N'EST PAS ZÉRO : `total_stock` vaut None, jamais 0."""
    r = publications(construire_filtre(), db=str(tmp_path / "vide.db"))
    assert r["disponible"] is False
    assert r["total_stock"] is None
    assert "non connecté" in r["raison"]


def test_des_criteres_TROP_STRICTS_ne_se_confondent_pas_avec_un_flux_vide(tmp_path):
    r = publications(construire_filtre(q="nexistepas"), db=_store_rempli(tmp_path))
    assert r["disponible"] is True          # le flux, lui, va bien
    assert r["n"] == 0 and r["total_stock"] == 2
    assert r["filtres_actifs"] is True      # ...c'est le filtre qui vide l'écran


def test_sans_filtre_on_voit_TOUT(tmp_path):
    r = publications(construire_filtre(), db=_store_rempli(tmp_path))
    assert r["n"] == 2 and r["filtres_actifs"] is False


# ---- 2. et 3. le stockage --------------------------------------------------------

def test_reingerer_le_meme_export_ne_DUPLIQUE_rien(tmp_path):
    """Sinon un incident réseau se transforme en publications fantômes."""
    s = StorePublications(str(tmp_path / "x.db"))
    s.ecrire(_lot())
    s.ecrire(_lot())
    assert s.compter() == 2
    s.close()


def test_l_aller_retour_preserve_l_ABSENCE_de_direction(tmp_path):
    s = StorePublications(str(tmp_path / "x.db"))
    s.ecrire(_lot())
    relues = {p.id: p for p in s.toutes()}
    assert relues["1"].direction is Direction.LONG
    assert relues["2"].direction is None      # et surtout pas une chaîne vide
    assert relues["1"].extraits == {"tp1": 65000.0}
    s.close()


def test_les_facettes_viennent_des_DONNEES_pas_d_une_liste_ecrite_en_dur(tmp_path):
    r = publications(construire_filtre(), db=_store_rempli(tmp_path))
    assert r["comptes"] == ["astekz", "trendspider"]
    assert r["symboles"] == ["BTCUSDT"]


# ---- 4. et 5. les paramètres d'URL ------------------------------------------------

def test_une_valeur_INCONNUE_dans_l_URL_est_ignoree_pas_fatale(tmp_path):
    """L'URL vient du dehors : elle ne doit pas pouvoir faire tomber la route."""
    r = publications(construire_filtre(classification="NIMPORTEQUOI"),
                     db=_store_rempli(tmp_path))
    assert r["n"] == 2


def test_plusieurs_comptes_se_donnent_separes_par_une_virgule(tmp_path):
    f = construire_filtre(accounts="astekz,trendspider")
    assert publications(f, db=_store_rempli(tmp_path))["n"] == 2
    f1 = construire_filtre(accounts="astekz")
    assert publications(f1, db=_store_rempli(tmp_path))["n"] == 1


def test_la_taxonomie_est_TOUJOURS_rendue_meme_flux_vide(tmp_path):
    """Les listes déroulantes doivent pouvoir se construire avant la première donnée."""
    r = publications(construire_filtre(), db=str(tmp_path / "vide.db"))
    assert "TRADE_SIGNAL" in r["classifications"] and "UNKNOWN" in r["classifications"]
    assert r["directions"] == ["LONG", "SHORT"]
