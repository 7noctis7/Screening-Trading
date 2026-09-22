"""Conserver ce que le robot savait en envoyant — pour que le rattrapage ne soit pas
aveugle.

Le 22/09, quatre achats sur six n'ont pas été journalisés pendant le run.
`completer_ouvertures` les a rattrapés depuis les seuls ordres du courtier — qui ne
connaît ni le rang du titre, ni le régime, ni le prix de décision. Les lots rattrapés
étaient donc SANS features, `legacy=1`, hors de l'échantillon de calibration ML : cet
échantillon était tombé à QUATRE lots.

Contrats épinglés ici :
  1. ce qui est déposé se retrouve — features, régime, et le JOUR de la décision ;
  2. une décision vaut jusqu'à 3 jours après, jamais 4, et JAMAIS après le fill ;
  3. la décision la plus RÉCENTE qui précède le fill gagne ;
  4. un re-run du même jour écrase sa propre trace au lieu de l'empiler ;
  5. au-delà de la rétention, les vieilles décisions disparaissent ;
    6. une décision sans features n'en apporte pas : on rend None plutôt qu'un
  dictionnaire
     vide qui ressemblerait à un contexte ;
  7. NaN n'entre pas — un JSON qui en contient n'est plus du JSON.
"""
from __future__ import annotations

from packages.execution.decisions_store import FENETRE_J, enregistrer, retrouver


def _f(tmp_path):
    return tmp_path / "decisions.json"


def _entree(sym="TTEK", venue="Alpaca", **feats):
    return {"symbol": sym, "venue": venue, "regime": "expansion/risk_on",
            "features": feats or {"rank_score": 1.5, "target_weight": 0.02}}


def test_ce_qui_est_depose_se_retrouve(tmp_path):
    f = _f(tmp_path)
    assert enregistrer([_entree()], "2026-09-22", fichier=f) is True
    d = retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f)
    assert d["features"] == {"rank_score": 1.5, "target_weight": 0.02}
    assert d["regime"] == "expansion/risk_on" and d["jour"] == "2026-09-22"


def test_la_cle_ignore_la_casse_et_la_place(tmp_path):
    """Le courtier écrit « alpaca », le snapshot « Alpaca » : le même ordre."""
    f = _f(tmp_path)
    enregistrer([_entree(sym="ttek", venue="ALPACA")], "2026-09-22", fichier=f)
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f) is not None


def test_une_decision_vaut_jusqu_a_trois_jours_apres_pas_quatre(tmp_path):
    """Un ordre reporté hors séance, ou une crypto GTC, se remplit après coup — c'est
    bien CETTE décision qui l'a produit. Au-delà, le lien devient une supposition."""
    f = _f(tmp_path)
    enregistrer([_entree()], "2026-09-18", fichier=f)
    assert FENETRE_J == 3
    assert retrouver("TTEK", "Alpaca", "2026-09-21", fichier=f) is not None   # J+3
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f) is None       # J+4


def test_une_decision_POSTERIEURE_au_fill_n_est_jamais_rendue(tmp_path):
    """Rattacher la décision de demain au fill d'hier serait du look-ahead pur."""
    f = _f(tmp_path)
    enregistrer([_entree()], "2026-09-22", fichier=f)
    assert retrouver("TTEK", "Alpaca", "2026-09-21", fichier=f) is None


def test_la_decision_la_plus_recente_avant_le_fill_gagne(tmp_path):
    f = _f(tmp_path)
    enregistrer([_entree(rank_score=1.0)], "2026-09-20", fichier=f)
    enregistrer([_entree(rank_score=9.0)], "2026-09-22", fichier=f)
    enregistrer([_entree(rank_score=5.0)], "2026-09-23", fichier=f)      # postérieure
    d = retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f)
    assert d["features"]["rank_score"] == 9.0


def test_un_re_run_du_meme_jour_ecrase_au_lieu_d_empiler(tmp_path):
    import json
    f = _f(tmp_path)
    enregistrer([_entree(rank_score=1.0)], "2026-09-22", fichier=f)
    enregistrer([_entree(rank_score=2.0)], "2026-09-22", fichier=f)
    assert len(json.loads(f.read_text())) == 1
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f)["features"] == {
        "rank_score": 2.0}


def test_les_vieilles_decisions_sont_purgees(tmp_path):
    import json
    f = _f(tmp_path)
    enregistrer([_entree(sym="VIEUX", rank_score=1.0)], "2026-01-01", fichier=f)
    enregistrer([_entree(sym="NEUF", rank_score=1.0)], "2026-09-22", fichier=f)
    assert [d["symbole"] for d in json.loads(f.read_text())] == ["NEUF"]


def test_une_decision_SANS_features_n_apporte_rien(tmp_path):
    """Rendre `{}` ressemblerait à un contexte retrouvé : le rattrapage écrirait
    `legacy=0` sur un lot aveugle, qui polluerait l'échantillon d'entraînement."""
    f = _f(tmp_path)
    enregistrer([{"symbol": "TTEK", "venue": "Alpaca", "features": {}}],
                "2026-09-22", fichier=f)
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f) is None


def test_seuls_les_nombres_FINIS_sont_conserves(tmp_path):
    f = _f(tmp_path)
    enregistrer([_entree(rank=1.5, drapeau=True, texte="x", nan=float("nan"))],
                "2026-09-22", fichier=f)
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f)["features"] == {
        "rank": 1.5}
    assert "NaN" not in f.read_text()          # sinon ce n'est plus du JSON


def test_un_fichier_illisible_ne_plante_pas(tmp_path):
    f = _f(tmp_path)
    f.write_text("{ ceci n'est pas du json")
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=f) is None
    assert enregistrer([_entree()], "2026-09-22", fichier=f) is True   # et il repart


def test_une_ecriture_impossible_rend_False_sans_lever(tmp_path):
    """Le run doit pouvoir l'ANNONCER — un magasin muet ferait croire à une mémoire
    alimentée, et le manque ne se verrait qu'au moment d'entraîner."""
    impossible = tmp_path / "fichier" / "sous" / "un" / "fichier.json"
    (tmp_path / "fichier").write_text("je suis un fichier, pas un dossier")
    assert enregistrer([_entree()], "2026-09-22", fichier=impossible) is False


def test_une_date_de_fill_illisible_rend_None(tmp_path):
    f = _f(tmp_path)
    enregistrer([_entree()], "2026-09-22", fichier=f)
    assert retrouver("TTEK", "Alpaca", "pas-une-date", fichier=f) is None


def test_rien_a_enregistrer_est_un_succes(tmp_path):
    assert enregistrer([], "2026-09-22", fichier=_f(tmp_path)) is True
