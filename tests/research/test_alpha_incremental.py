"""Le NLP apporte-t-il quelque chose ? — l'instrument qui tranchera, éprouvé sur des séries
SYNTHÉTIQUES (autorisé en tests pour valider la math, cf. CLAUDE.md).

La question que ce module décide — poids du NLP validé ou ZÉRO — est la seule qui justifie
ou non la suite du chantier. Un instrument faux donnerait un feu vert à une dépense.
"""

import math
from dataclasses import dataclass

import numpy as np
import pytest

from packages.research.alpha_incremental import (
    MIN_EVENEMENTS,
    Evenement,
    comparer,
    evaluer,
    extraire,
    placebo,
    verdict,
)


@dataclass
class Barre:
    ts: str
    close: float


def _bars(n=80, depart="2026-01-01", pas=1.0):
    from datetime import date, timedelta
    d0 = date.fromisoformat(depart)
    return [Barre(ts=(d0 + timedelta(days=i)).isoformat(), close=100.0 + i * pas)
            for i in range(n)]


def _evenements(n=60, graine=7):
    rng = np.random.default_rng(graine)
    return [Evenement(symbole="AAPL", jour=f"2026-01-{i % 28 + 1:02d}",
                      titre=f"titre {i}", rendement=float(rng.normal(0, 0.02)))
            for i in range(n)]


# ─── Extraction : le point-in-time vient du CORPUS ─────────────────────────────────────

def test_l_evenement_est_date_par_utilisable_le_PAS_par_la_publication():
    """Un article publié le 5 mais découvert le 10 ne peut pas être exploité le 5."""
    data = {"AAPL": _bars()}
    corpus = [{"symbol": "AAPL", "headline": "Nouvelle", "date": "2026-01-05",
               "vu_le": "2026-01-10"}]
    ev = extraire(data, corpus, hold=5, entry_lag=1)
    assert len(ev) == 1 and ev[0].jour == "2026-01-10"


def test_on_entre_au_close_SUIVANT_la_disponibilite():
    """Entrer le jour même supposerait d'avoir lu, décidé et exécuté avant la clôture."""
    data = {"AAPL": _bars(pas=1.0)}
    corpus = [{"symbol": "AAPL", "headline": "x", "date": "2026-01-10",
               "vu_le": "2026-01-10"}]
    ev = extraire(data, corpus, hold=5, entry_lag=1)
    # index du 10/01 = 9 ; entrée au 10 (close 110), sortie au 15 (close 115)
    assert ev[0].rendement == pytest.approx(115.0 / 110.0 - 1.0, rel=1e-9)


def test_un_evenement_trop_proche_de_la_fin_est_ecarte():
    """Sans barres futures, il n'y a pas de rendement à mesurer — l'inventer serait pire."""
    data = {"AAPL": _bars(n=12)}
    corpus = [{"symbol": "AAPL", "headline": "x", "date": "2026-01-11",
               "vu_le": "2026-01-11"}]
    assert extraire(data, corpus, hold=5) == []


def test_un_symbole_sans_prix_est_ecarte():
    corpus = [{"symbol": "INCONNU", "headline": "x", "date": "2026-01-05",
               "vu_le": "2026-01-05"}]
    assert extraire({"AAPL": _bars()}, corpus) == []


def test_un_titre_vide_est_ecarte():
    corpus = [{"symbol": "AAPL", "headline": "  ", "date": "2026-01-05",
               "vu_le": "2026-01-05"}]
    assert extraire({"AAPL": _bars()}, corpus) == []


# ─── L'échantillon est PARTAGÉ — le piège central ──────────────────────────────────────

def test_deux_scoreurs_DOIVENT_noter_le_meme_echantillon():
    """C'est le piège qui invalide la plupart des comparaisons : « score nul » dépend du
    scoreur, donc écarter les nuls mesurerait les deux sur des échantillons différents, et
    l'écart mélangerait pouvoir prédictif et sélection."""
    ev = _evenements(40)
    with pytest.raises(ValueError, match="même échantillon"):
        comparer(ev, {"a": [0.1] * 40, "b": [0.1] * 39})


def test_un_scoreur_muet_est_signale_pas_ecarte():
    """Se taire est une information sur le scoreur : l'écarter la ferait disparaître."""
    ev = _evenements(60)
    scores = [0.0] * 55 + [0.5] * 5
    m = evaluer("muet", ev, scores)
    assert m.part_notee == pytest.approx(5 / 60, abs=1e-3)
    assert any("se tait" in i for i in m.incidents)


# ─── Échantillon insuffisant ───────────────────────────────────────────────────────────

def test_sous_le_seuil_aucune_conclusion():
    ev = _evenements(MIN_EVENEMENTS - 1)
    m = evaluer("x", ev, [0.5] * len(ev))
    assert m.ic == 0.0 and m.dsr == 0.0
    assert any("rien à conclure" in i for i in m.incidents)


def test_le_placebo_rend_1_sur_un_echantillon_insuffisant():
    ev = _evenements(5)
    assert placebo(ev, [0.5] * 5, tirages=10) == 1.0


# ─── IC ────────────────────────────────────────────────────────────────────────────────

def test_un_scoreur_PARFAIT_a_un_IC_de_un():
    ev = _evenements(60)
    scores = [e.rendement for e in ev]          # il connaît l'avenir
    assert evaluer("oracle", ev, scores).ic == pytest.approx(1.0, abs=1e-6)


def test_un_scoreur_INVERSE_a_un_IC_de_moins_un():
    ev = _evenements(60)
    scores = [-e.rendement for e in ev]
    assert evaluer("miroir", ev, scores).ic == pytest.approx(-1.0, abs=1e-6)


def test_un_scoreur_CONSTANT_a_un_IC_NUL():
    """Aucune variance, donc aucune information — et surtout pas une corrélation NaN."""
    ev = _evenements(60)
    m = evaluer("plat", ev, [0.3] * 60)
    assert m.ic == 0.0 and math.isfinite(m.ic)


def test_l_IC_est_un_rang_pas_un_pearson():
    """Un IC de Pearson serait dominé par quelques valeurs extrêmes — et un titre de presse
    produit exactement ce genre de valeurs."""
    ev = [Evenement("A", "2026-01-01", "t", r) for r in
          [0.01, 0.02, 0.03, 0.04, 5.0] + [0.001] * 40]
    scores = [1.0, 2.0, 3.0, 4.0, 5.0] + [0.5] * 40
    m = evaluer("rangs", ev, scores)
    assert -1.0 <= m.ic <= 1.0


# ─── Placebo ───────────────────────────────────────────────────────────────────────────

def test_un_scoreur_ALEATOIRE_ne_passe_pas_le_placebo():
    rng = np.random.default_rng(3)
    ev = _evenements(200, graine=11)
    p = placebo(ev, list(rng.normal(0, 1, 200)), tirages=300)
    assert p > 0.05, f"un scoreur aléatoire a passé le placebo (p={p})"


def test_un_ORACLE_ecrase_le_placebo():
    ev = _evenements(200, graine=13)
    p = placebo(ev, [e.rendement for e in ev], tirages=300)
    assert p < 0.01


def test_la_p_valeur_n_est_JAMAIS_exactement_zero():
    """Avec un nombre fini de tirages, une p-valeur nulle n'existe pas — l'écrire
    laisserait croire à une certitude. D'où le +1 au numérateur et au dénominateur."""
    ev = _evenements(200, graine=17)
    p = placebo(ev, [e.rendement for e in ev], tirages=100)
    assert p > 0.0 and p >= 1 / 101


def test_le_placebo_est_reproductible():
    ev = _evenements(100)
    s = [e.rendement * 0.5 for e in ev]
    assert placebo(ev, s, tirages=50, graine=1) == placebo(ev, s, tirages=50, graine=1)


# ─── Tests multiples ───────────────────────────────────────────────────────────────────

def test_comparer_six_scoreurs_DEFLATE_le_sharpe_de_chacun():
    """Laisser `n_essais=1` quand on en a comparé six fait passer pour significatif le
    meilleur de six tirages — la définition même du surapprentissage par sélection."""
    ev = _evenements(120, graine=5)
    oracle = [e.rendement for e in ev]
    seul = comparer(ev, {"oracle": oracle}, tirages=20)
    six = comparer(ev, {f"s{i}": oracle for i in range(6)}, tirages=20)
    assert seul["n_essais"] == 1 and six["n_essais"] == 6
    assert six["mesures"]["s0"]["dsr"] <= seul["mesures"]["oracle"]["dsr"]


# ─── Écarts appariés ───────────────────────────────────────────────────────────────────

def test_les_ecarts_sont_APPARIES():
    """Un test apparié élimine la variance commune — celle du marché ce jour-là, qui
    affecte les deux scoreurs identiquement et n'apprend rien sur l'un contre l'autre."""
    ev = _evenements(100, graine=19)
    r = comparer(ev, {"oracle": [e.rendement for e in ev],
                      "miroir": [-e.rendement for e in ev]}, tirages=20)
    ec = r["ecarts"][0]
    # Les paires sont ordonnées alphabétiquement : « miroir » puis « oracle ». Le nom de la
    # clé porte le sens (a − b), ce qui évite l'erreur de signe la plus banale.
    assert (ec["a"], ec["b"]) == ("miroir", "oracle")
    assert ec["t_apparie_a_moins_b"] < -3.0, "miroir − oracle doit être franchement négatif"
    assert abs(ec["t_apparie_a_moins_b"]) > 3.0


def test_deux_scoreurs_IDENTIQUES_ont_un_ecart_nul():
    ev = _evenements(60)
    s = [e.rendement for e in ev]
    ec = comparer(ev, {"a": s, "b": list(s)}, tirages=20)["ecarts"][0]
    assert ec["ecart_moyen_a_moins_b"] == 0.0 and ec["t_apparie_a_moins_b"] == 0.0


# ─── Verdict ───────────────────────────────────────────────────────────────────────────

def test_un_scoreur_aleatoire_recoit_le_poids_ZERO():
    rng = np.random.default_rng(23)
    ev = _evenements(200, graine=29)
    r = comparer(ev, {"bruit": list(rng.normal(0, 1, 200))}, tirages=200)
    v = verdict(r)
    assert v["retenus"] == []
    assert v["scoreurs"][0]["poids"] == 0.0 and v["scoreurs"][0]["motif"]


def test_les_trois_portes_sont_CONJOINTES():
    """Un IC élevé avec un placebo non concluant est un tirage chanceux ; un DSR élevé avec
    un IC nul est un artefact de distribution, pas un signal."""
    rapport = {"n_evenements": 100, "n_essais": 1, "mesures": {
        "ic_seul": {"n": 100, "ic": 0.5, "dsr": 0.2, "p_placebo": 0.5,
                    "rendement_moyen": 0.0, "sharpe": 0.0, "part_notee": 1.0},
        "dsr_seul": {"n": 100, "ic": 0.001, "dsr": 0.99, "p_placebo": 0.01,
                     "rendement_moyen": 0.0, "sharpe": 0.0, "part_notee": 1.0},
    }}
    v = verdict(rapport)
    assert v["retenus"] == []
    motifs = {x["scoreur"]: x["motif"] for x in v["scoreurs"]}
    assert "placebo" in motifs["ic_seul"] and "DSR" in motifs["ic_seul"]
    assert "IC" in motifs["dsr_seul"]


def test_un_scoreur_qui_passe_TOUT_est_retenu():
    rapport = {"n_evenements": 200, "n_essais": 1, "mesures": {
        "bon": {"n": 200, "ic": 0.12, "dsr": 0.97, "p_placebo": 0.004,
                "rendement_moyen": 0.003, "sharpe": 1.1, "part_notee": 0.8},
    }}
    v = verdict(rapport)
    assert v["retenus"] == ["bon"]
    assert v["scoreurs"][0]["poids"] == 1.0
    assert "trois portes" in v["scoreurs"][0]["motif"]


def test_le_verdict_nomme_TOUJOURS_le_motif_du_refus():
    """Un refus sans motif ne se corrige pas — on le contourne."""
    rapport = {"n_evenements": 10, "n_essais": 1, "mesures": {
        "court": {"n": 10, "ic": 0.0, "dsr": 0.0, "p_placebo": 1.0,
                  "rendement_moyen": 0.0, "sharpe": 0.0, "part_notee": 1.0}}}
    assert "insuffisant" in verdict(rapport)["scoreurs"][0]["motif"]


def test_une_serie_QUASI_constante_ne_fabrique_pas_d_IC():
    """Le piège du « canal plat » (CLAUDE.md) : soixante fois 0.3 ont un écart-type de
    5e-17, pas zéro. Les rangs de ce bruit sont arbitraires, et l'IC mesuré valait 0,21
    pour un scoreur strictement constant."""
    from packages.research.alpha_incremental import _degenere
    ev = _evenements(60)
    assert evaluer("plat", ev, [0.3] * 60).ic == 0.0
    assert _degenere(np.array([0.3] * 60))
    assert _degenere(np.array([1.0, 1.0 + 1e-16, 1.0]))
    assert not _degenere(np.array([1.0, 2.0, 3.0]))


def test_des_rendements_quasi_constants_donnent_aussi_un_IC_nul():
    """Symétrique : un jeu où rien ne bouge ne peut pas prédire."""
    ev = [Evenement("A", "2026-01-01", "t", 0.001) for _ in range(60)]
    assert evaluer("x", ev, [float(i) for i in range(60)]).ic == 0.0


def test_le_plancher_de_p_valeur_tient_a_TOUTES_les_tailles():
    ev = _evenements(200, graine=31)
    oracle = [e.rendement for e in ev]
    for tirages in (50, 100, 500):
        p = placebo(ev, oracle, tirages=tirages)
        assert p >= 1.0 / (tirages + 1), f"{p} < plancher 1/{tirages + 1}"


def test_la_p_valeur_est_arrondie_VERS_LE_HAUT():
    """La seule direction dans laquelle une erreur d'arrondi peut coûter une fausse
    découverte est la baisse. On arrondit donc au-dessus, jamais au plus proche."""
    ev = _evenements(200, graine=37)
    oracle = [e.rendement for e in ev]
    for tirages in (50, 100, 500, 999):
        p = placebo(ev, oracle, tirages=tirages)
        plancher = 1.0 / (tirages + 1)
        assert p >= plancher, f"p={p} sous le plancher {plancher}"
        assert p <= plancher + 1e-6


# ─── Le banc refuse de parler trop tôt ─────────────────────────────────────────────────

def test_le_banc_exige_un_corpus_avant_de_conclure():
    """Une étude d'événement sur quelques dizaines d'observations ne conclut rien, et
    prétendre le contraire serait la pire sortie possible de ce banc."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
           / "alpha_nlp_lab.py").read_text(encoding="utf-8")
    assert "MIN_POUR_PARLER" in src
    assert "return 2" in src, "il doit SORTIR en erreur, pas afficher un tableau vide"


def test_le_banc_traduit_un_repli_NLP_en_ABSENCE_d_avis():
    """Un repli vaut 0 — « pas d'avis » — et surtout pas « neutre convaincu » : confondre
    les deux ferait compter une panne de LLM comme une classification."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
           / "alpha_nlp_lab.py").read_text(encoding="utf-8")
    assert "0.0 if s.repli else" in src


def test_le_banc_pondere_le_sentiment_par_la_CONFIANCE():
    """Un BULLISH à 0,3 de confiance ne doit pas peser autant qu'un BULLISH à 0,9."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
           / "alpha_nlp_lab.py").read_text(encoding="utf-8")
    assert "signe[s.sentiment] * s.confiance" in src


def test_un_scoreur_absent_ne_fait_pas_echouer_la_comparaison():
    """Sans fournisseur LLM, le banc compare le lexique à lui-même et le dit — plutôt que
    de refuser de tourner, ce qui empêcherait d'établir la ligne de base."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
           / "alpha_nlp_lab.py").read_text(encoding="utf-8")
    assert "aucun fournisseur LLM" in src and "lexique seul" in src
