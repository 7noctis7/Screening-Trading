"""Une tendance de cours ne doit pas pouvoir se faire passer pour une news."""

from pathlib import Path

from packages.sentiment.origine import humeur, qualifier_ligne


def test_une_news_reste_une_news():
    r = qualifier_ligne(2, 0.4, 0.9)
    assert r["origine"] == "news" and r["score"] == 0.4


def test_sans_news_la_tendance_est_nommee_et_un_trou_n_est_pas_zero():
    tendance = qualifier_ligne(0, None, -0.4)
    assert tendance["origine"] == "momentum" and tendance["score"] == -0.4
    vide = qualifier_ligne(0, None, None)
    assert vide["score"] is None and vide["label"] == "n/d" and vide["origine"] == "indisponible"


def test_l_humeur_n_emprunte_pas_le_momentum_des_qu_une_news_existe():
    lignes = [
        qualifier_ligne(1, 0.5, None),
        qualifier_ligne(0, None, -1.0),
        qualifier_ligne(0, None, None),
    ]
    h = humeur(lignes)
    assert h["humeur_est_fil"] is True
    assert h["market_mood"] == 0.5
    assert h["n_lignes_tendance"] == 1 and h["n_lignes_vides"] == 1


def test_sans_aucune_news_l_humeur_dit_qu_elle_n_est_pas_un_fil():
    h = humeur([qualifier_ligne(0, None, 0.2), qualifier_ligne(0, None, None)])
    assert h["humeur_est_fil"] is False and h["market_mood"] == 0.2
    assert humeur([qualifier_ligne(0, None, None)])["market_mood"] is None


def test_le_snapshot_passe_par_le_qualificateur():
    racine = Path(__file__).resolve().parents[2]
    bloc = (racine / "apps/api/snapshot.py").read_text()
    bloc = bloc.split("def _sentiment_section", 1)[1].split("\ndef ", 1)[0]
    assert "qualifier_ligne(" in bloc
    assert "0.0 if score is None" not in bloc
    page = (racine / "apps/web/app/ml/page.tsx").read_text()
    assert "Proba hausse" not in page
    assert "non calibré" in page

