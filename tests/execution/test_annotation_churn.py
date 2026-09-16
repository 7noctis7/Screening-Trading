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

# Les clés qui comptent sont celles du churn PAR DOUBLON — pas celles du churn total.
# Le 23/06 portait un aller-retour sur un jour à UN SEUL passage : l'inclure daterait la
# double planification de neuf semaines trop tôt.
RAPPORT = {"depuis_doublon_cout": "2026-08-27", "pnl_doublon": -618.57,
           "pnl_hors_doublon": -1.56, "notionnel_churn": 594362.0,
           "jours_a_doublon_cout": ["j"] * 13}


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
    a = annotation({"depuis_doublon_cout": None, "pnl_doublon": 0.0})
    assert a["applicable"] is False and a["mesure"] is True
    assert "saine" in a["motif"] and "NON MESURÉ" not in a["motif"]


def test_une_courbe_polluee_dit_DEPUIS_QUAND_et_COMBIEN():
    a = annotation(RAPPORT)
    assert a["applicable"] is True and a["mesure"] is True
    assert a["depuis"] == "2026-08-27" and a["pnl"] == -618.57
    assert a["jours"] == 13
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
    assert "594 362 $" in t and "618,57 $" in t
    assert "concerné(s), " in t, "les virgules de la phrase doivent survivre"


def test_une_date_inattendue_ne_fait_pas_tomber_l_annotation():
    """L'annotation accompagne une courbe : pas le droit de la faire disparaître."""
    a = annotation({**RAPPORT, "depuis_doublon_cout": "pas-une-date"})
    assert a["applicable"] is True and "pas-une-date" in a["texte"]


# ─── La date de pollution : celle des DOUBLONS, pas du premier aller-retour
# ────────────

def test_un_aller_retour_sur_un_jour_A_UN_SEUL_PASSAGE_ne_date_rien():
    """LE DÉFAUT DU 16/09, et il portait une affirmation PUBLIQUE. Le 23/06 porte un
    aller-retour de −1,56 $ sur un jour à un seul passage : du va-et-vient
    intra-passage,
    pas deux robots qui se défont. L'annotation le datait pourtant du 23/06 — attribuant
    à la double planification neuf semaines qu'elle n'a pas causées, et condamnant à
    tort
    toutes les mesures de la période."""
    from packages.execution.passages import rapport

    def o(d, sym, side, qty, px):
        return {"date": d, "symbol": sym, "side": side, "qty": qty, "price": px}

    ordres = [
        o("2026-06-23T15:55:12Z", "A", "buy", 1, 100),    # un seul passage…
        o("2026-06-23T15:55:20Z", "A", "sell", 1, 98),    # …mais un A/R
        o("2026-08-27T21:52:11Z", "B", "buy", 1, 100),    # deux passages…
        o("2026-08-27T23:56:34Z", "B", "sell", 1, 90),    # …qui se contredisent
    ]
    r = rapport(ordres)
    assert r["depuis_cout"] == "2026-06-23", "le premier A/R tout court"
    assert r["depuis_doublon_cout"] == "2026-08-27", "le premier A/R DE DOUBLON"
    assert annotation(r)["depuis"] == "2026-08-27"


def test_le_churn_HORS_doublon_est_dit_separement():
    """Le taire ferait croire que tout le va-et-vient vient de la double planification —
    et le corriger un jour laisserait un écart inexpliqué."""
    t = annotation(RAPPORT)["texte"]
    assert "INTRA-passage" in t and "1,56 $" in t
    assert annotation(RAPPORT)["pnl_hors_doublon"] == -1.56


def test_un_churn_hors_doublon_NEGLIGEABLE_n_encombre_pas_la_phrase():
    t = annotation({**RAPPORT, "pnl_hors_doublon": 0.0})["texte"]
    assert "INTRA-passage" not in t
