"""On ANNOTE la courbe d'equity réelle, on ne la corrige pas.

Retrancher le churn reviendrait à publier une courbe qui n'a jamais existé : le compte a
bien encaissé ces allers-retours. Une performance « telle qu'elle aurait été sans notre
erreur » est une simulation — et elle porterait le nom d'un compte réel.

Ce que ces tests protègent avant tout, c'est la distinction entre TROIS états qui se
ressemblent à l'écran : non mesuré, mesuré et sain, mesuré et pollué. Confondre les deux
premiers, c'est lire un silence comme un feu vert — la confusion la plus coûteuse de ce
projet, déjà rencontrée sur les zéros qui ressemblaient à des absences.
"""

from packages.execution.annotation_churn import annotation

RAPPORT = {"depuis_cout": "2026-08-27", "pnl_churn": -620.13,
           "notionnel_churn": 594362.0, "jours_a_cout": ["j"] * 14}


# ─── Les trois états
# ───────────────────────────────────────────────────────────────────

def test_un_historique_illisible_se_distingue_d_un_churn_nul():
    """Sans les clés du courtier (la CI n'en a pas), on ne SAIT pas. Le dire autrement
    qu'« aucun churn » n'est pas une nuance de style : c'est la différence entre une
    mesure et une absence de mesure."""
    a = annotation(None)
    assert a["applicable"] is False and a["mesure"] is False
    assert "NON MESURÉ" in a["motif"]


def test_un_historique_lisible_et_sain_le_dit_positivement():
    a = annotation({"depuis_cout": None, "pnl_churn": 0.0})
    assert a["applicable"] is False and a["mesure"] is True
    assert "saine" in a["motif"] and "NON MESURÉ" not in a["motif"]


def test_une_courbe_polluee_dit_DEPUIS_QUAND_et_COMBIEN():
    a = annotation(RAPPORT)
    assert a["applicable"] is True and a["mesure"] is True
    assert a["depuis"] == "2026-08-27" and a["pnl"] == -620.13 and a["jours"] == 14
    assert "27/08/2026" in a["texte"]


# ─── Ce qu'on refuse d'inventer
# ────────────────────────────────────────────────────────

def test_sans_capital_aucun_point_de_performance_n_est_fabrique():
    """Convertir −620 $ en points exige de savoir SUR QUOI. Un dénominateur supposé
    fabriquerait un chiffre faux, d'autant plus crédible qu'il serait précis."""
    a = annotation(RAPPORT)
    assert a["points"] is None
    assert "point(s) de performance" not in a["texte"]


def test_un_capital_nul_ou_negatif_ne_produit_pas_une_division():
    for capital in (0, -1.0, None):
        assert annotation(RAPPORT, capital)["points"] is None


def test_avec_le_capital_les_points_sont_calcules_et_signes():
    a = annotation(RAPPORT, capital=100_000)
    assert a["points"] == -0.62
    assert "en moins" in a["texte"]


# ─── La série reste celle du compte
# ────────────────────────────────────────────────────

def test_l_annotation_DIT_que_la_serie_n_est_pas_corrigee():
    """Une annotation qui laisserait croire à une correction serait pire que rien."""
    assert "n'est PAS corrigée" in annotation(RAPPORT)["texte"]
    assert "ce que le compte a vraiment fait" in annotation(RAPPORT)["texte"]


def test_elle_nomme_la_consequence_pour_les_comparaisons():
    assert "modèle contre réel" in annotation(RAPPORT)["texte"]


# ─── Typographie : une règle appliquée trop loin devient une faute
# ─────────────────────

def test_le_formatage_francais_ne_mange_pas_la_ponctuation():
    """Une première version passait un `replace(",", " ")` sur la PHRASE entière, et
    effaçait donc aussi les virgules de ponctuation."""
    t = annotation(RAPPORT, capital=100_000)["texte"]
    assert "594 362 $" in t and "620,13 $" in t
    assert "concerné(s), " in t, "les virgules de la phrase doivent survivre"


def test_une_date_inattendue_ne_fait_pas_tomber_l_annotation():
    """L'annotation accompagne une courbe : pas le droit de la faire disparaître."""
    a = annotation({**RAPPORT, "depuis_cout": "pas-une-date"})
    assert a["applicable"] is True and "pas-une-date" in a["texte"]
