"""Le corpus de news datées — et les deux horodatages qui empêchent la fuite.

DÉCOUVERT LE 16/09 : le dépôt sait lire des flux, scorer, faire une étude d'événement avec
IC et Sharpe déflaté, et gérer le point-in-time. Tout est là SAUF le corpus. `data/news.csv`
n'existait pas et rien ne l'écrivait, donc mesurer l'alpha incrémental d'un LLM était
impossible — et le serait resté, puisqu'un flux RSS ne se rejoue pas.
"""

from datetime import UTC, datetime

import pytest

from packages.sentiment.corpus import (
    COLONNES,
    ajouter,
    charger,
    etat,
    normaliser,
    utilisable_le,
)

LE_16 = datetime(2026, 9, 16, tzinfo=UTC)


def _fichier(tmp_path):
    return tmp_path / "news.csv"


def _titre(t="Résultats au-dessus du consensus", d="2026-09-16", sym="AAPL",
           vu=LE_16):
    return normaliser({"title": t, "date": d, "source": "Yahoo"}, sym, vu)


# ─── Les deux horodatages ──────────────────────────────────────────────────────────────

def test_un_titre_porte_sa_date_ET_la_date_ou_on_l_a_vu():
    n = _titre(d="2026-09-10")
    assert n["date"] == "2026-09-10" and n["vu_le"] == "2026-09-16"


def test_un_article_retro_publie_n_est_utilisable_qu_a_partir_du_jour_ou_on_l_a_VU():
    """LA fuite que ce module empêche. Un flux qui rétro-publie un article de la semaine
    dernière nous le fait découvrir aujourd'hui ; se fier à `date` laisserait une stratégie
    « savoir » une semaine avant d'avoir pu savoir."""
    n = _titre(d="2026-09-10", vu=LE_16)
    assert utilisable_le(n) == "2026-09-16"


def test_un_article_du_jour_est_utilisable_le_jour_meme():
    assert utilisable_le(_titre(d="2026-09-16", vu=LE_16)) == "2026-09-16"


def test_la_borne_ne_peut_jamais_preceder_la_publication():
    """Cas inverse : un `vu_le` antérieur à la date de publication (horloge décalée) ne
    doit pas permettre d'utiliser l'article avant qu'il existe."""
    n = _titre(d="2026-09-20", vu=LE_16)
    assert utilisable_le(n) == "2026-09-20"


# ─── Ce qui est refusé ─────────────────────────────────────────────────────────────────

def test_un_titre_SANS_DATE_est_refuse():
    """Lui donner la date du jour lui prêterait une fraîcheur qu'il n'a pas, dans un jeu
    qui sert précisément à mesurer de la prédiction."""
    assert normaliser({"title": "Sans date"}, "AAPL") is None
    assert normaliser({"title": "Vide", "date": ""}, "AAPL") is None


def test_un_titre_vide_est_refuse():
    assert normaliser({"date": "2026-09-16"}, "AAPL") is None
    assert normaliser({"title": "   ", "date": "2026-09-16"}, "AAPL") is None


def test_une_date_illisible_est_refusee():
    assert normaliser({"title": "x", "date": "la semaine dernière"}, "AAPL") is None


@pytest.mark.parametrize("forme", ["2026-09-16", "2026-09-16T14:30:00+00:00",
                                   "2026-09-16T14:30:00Z", "2026-09-16 14:30:00"])
def test_les_formes_de_date_courantes_sont_acceptees(forme):
    n = normaliser({"title": "x", "date": forme}, "AAPL")
    assert n is not None and n["date"] == "2026-09-16"


# ─── Déduplication ─────────────────────────────────────────────────────────────────────

def test_le_meme_titre_repris_par_trois_agregateurs_ne_compte_qu_une_fois():
    """Trois occurrences gonfleraient artificiellement le poids de l'événement dans
    l'étude — et donc son apparente significativité."""
    a = normaliser({"title": "Rachat annoncé", "date": "2026-09-16", "source": "A"}, "AAPL")
    b = normaliser({"title": "rachat   ANNONCÉ", "date": "2026-09-16", "source": "B"}, "AAPL")
    assert a["empreinte"] == b["empreinte"]


def test_le_meme_titre_sur_deux_symboles_compte_deux_fois():
    a = normaliser({"title": "Le secteur progresse", "date": "2026-09-16"}, "AAPL")
    b = normaliser({"title": "Le secteur progresse", "date": "2026-09-16"}, "MSFT")
    assert a["empreinte"] != b["empreinte"]


def test_un_doublon_n_est_pas_reecrit(tmp_path):
    f = _fichier(tmp_path)
    n = [_titre()]
    assert ajouter(n, f)["ajoutees"] == 1
    r = ajouter(n, f)
    assert r["ajoutees"] == 0 and r["doublons"] == 1
    assert len(charger(f)) == 1


# ─── Append-only ───────────────────────────────────────────────────────────────────────

def test_l_ecriture_est_APPEND_ONLY(tmp_path):
    """Réécrire le fichier permettrait de modifier rétroactivement un `vu_le`, c'est-à-dire
    de fabriquer une antériorité qu'on n'avait pas. Un corpus réécrivable ne prouve rien."""
    f = _fichier(tmp_path)
    ajouter([_titre(t="Premier")], f)
    avant = f.read_text(encoding="utf-8")
    ajouter([_titre(t="Second")], f)
    apres = f.read_text(encoding="utf-8")
    assert apres.startswith(avant), "le contenu existant a été réécrit"


def test_l_entete_n_est_ecrit_qu_une_fois(tmp_path):
    f = _fichier(tmp_path)
    ajouter([_titre(t="A")], f)
    ajouter([_titre(t="B")], f)
    assert f.read_text(encoding="utf-8").count("empreinte") == 1


def test_les_colonnes_sont_stables(tmp_path):
    f = _fichier(tmp_path)
    ajouter([_titre()], f)
    assert list(charger(f)[0]) == list(COLONNES)


def test_ajouter_une_liste_vide_ne_cree_pas_de_fichier(tmp_path):
    f = _fichier(tmp_path)
    assert ajouter([], f)["ajoutees"] == 0
    assert not f.exists()


# ─── État ──────────────────────────────────────────────────────────────────────────────

def test_l_etat_dit_qu_un_corpus_vide_est_vide(tmp_path):
    e = etat(_fichier(tmp_path))
    assert not e["disponible"] and e["n"] == 0


def test_l_etat_compte_les_retro_publies(tmp_path):
    """C'est la mesure de la fuite qu'on aurait introduite en se fiant à `date` seule."""
    f = _fichier(tmp_path)
    ajouter([_titre(t="À l'heure", d="2026-09-16"),
             _titre(t="En retard", d="2026-09-01")], f)
    e = etat(f)
    assert e["n"] == 2 and e["retro_publies"] == 1 and e["part_retro"] == 0.5


def test_l_etat_donne_la_periode_couverte(tmp_path):
    f = _fichier(tmp_path)
    ajouter([_titre(t="A", d="2026-09-01"), _titre(t="B", d="2026-09-16")], f)
    e = etat(f)
    assert e["du"] == "2026-09-01" and e["au"] == "2026-09-16" and e["n_jours"] == 2


# ─── Branchement ───────────────────────────────────────────────────────────────────────

def test_la_collecte_est_dans_la_chaine_QUOTIDIENNE():
    """Un flux RSS ne se rejoue pas : une collecte qu'on lance « quand on y pense » produit
    un corpus troué, et un corpus troué ne mesure rien."""
    import pathlib
    racine = pathlib.Path(__file__).resolve().parents[2]
    cron = (racine / "scripts" / "cron_daily.sh").read_text(encoding="utf-8")
    assert "collecter_news.py" in cron


def test_le_collecteur_n_envoie_aucun_ordre():
    import pathlib
    racine = pathlib.Path(__file__).resolve().parents[2]
    src = (racine / "scripts" / "collecter_news.py").read_text(encoding="utf-8")
    for interdit in ("run_live", "submit", "--live", "close_position"):
        assert interdit not in src
