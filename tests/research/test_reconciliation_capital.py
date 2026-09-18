"""« Réalisé + latent = capital réel ? » — non, et le site doit le DIRE, pas le cacher.

LA QUESTION POSÉE (18/09). Elle est légitime et sa réponse est non, pour une raison de
DIMENSION : un réalisé et un latent sont des VARIATIONS, le capital réel est un NIVEAU.
Leur somme vaut la variation du compte, jamais le compte. L'identité complète part du
capital INITIAL et comporte un terme qui manque toujours à l'intuition :
`latent(début)`, le gain non réalisé que portaient DÉJÀ les positions au premier
point de la courbe.

CE QUE CES TESTS TIENNENT. Que l'identité est posée sur le bon niveau, que le résidu
n'est jamais comblé, qu'une donnée absente se dit au lieu de passer pour un
rapprochement réussi, et que le panneau ne se lit pas comme le compte.
"""

from __future__ import annotations

from packages.research.reconciliation_capital import capital, reconcilier


def _points(v0: float, v1: float, t0="2026-06-22", t1="2026-09-17") -> list[dict]:
    return [{"t": t0, "v": v0}, {"t": t1, "v": v1}]


def _courbe(v0: float, v1: float, **kw) -> dict[str, list[dict]]:
    """Un seul compte — la forme attendue reste `{compte: points}`."""
    return {"alpaca": _points(v0, v1, **kw)}


def test_l_identite_part_du_CAPITAL_INITIAL_pas_de_zero():
    """Le cœur de la réponse. Sur un compte à 100 000 $ qui a gagné 500 $, « réalisé +
    latent » vaut 500 et non 100 500 : confondre les deux ferait paraître le compte
    vidé de 99,5 % dès qu'on essaie de rapprocher les chiffres."""
    r = reconcilier(_courbe(100_000.0, 100_500.0), realise=300.0, latent=200.0)
    assert r["attendu"] == 100_500.0
    assert r["residu"] == 0.0
    assert r["boucle"] is True


def test_le_residu_est_PUBLIE_jamais_comble():
    """Un rapprochement qui tombe juste parce qu'on y a mis un terme d'ajustement ne
    prouve rien. Ici l'écart reste entier, et le verdict le dit."""
    r = reconcilier(_courbe(99_593.81, 100_482.13), realise=-1790.60, latent=853.18)
    assert r["boucle"] is False
    attendu = 99_593.81 - 1790.60 + 853.18
    assert round(r["residu"], 2) == round(100_482.13 - attendu, 2)
    assert abs(r["residu"]) > r["seuil"]
    assert "latent(début)" in r["explication"]


def test_le_cas_MESURE_du_17_09_est_reproduit():
    """Les chiffres du terminal (`make diag-journal`) et ceux du site doivent venir du
    même calcul, sinon on débat de deux mesures au lieu d'une."""
    r = reconcilier(_courbe(99_593.81, 100_482.13), realise=-1790.60, latent=853.18)
    assert round(r["residu"], 0) == 1826.0          # ordre de grandeur du diag
    assert 0.01 < r["residu_part"] < 0.03           # ~1,8 % du capital


def test_sans_courbe_on_DIT_qu_on_ne_sait_pas():
    """Une réconciliation muette se lirait comme une réconciliation réussie — c'est le
    mode de défaillance que ce dépôt combat partout ailleurs."""
    r = reconcilier({}, realise=100.0, latent=50.0)
    assert r["disponible"] is False
    assert r["motif"]
    assert "boucle" not in r, "aucun verdict ne doit être rendu sans données"


def test_une_courbe_a_UN_POINT_ne_definit_aucune_variation():
    """Renvoyer zéro se lirait « le compte n'a pas bougé ». On l'écarte, et la fenêtre
    disparaît du rapprochement plutôt que d'y entrer à faux."""
    assert capital({"alpaca": [{"t": "2026-09-17", "v": 100.0}]})["fenetres"] == []


def test_le_panneau_ne_se_lit_pas_comme_le_COMPTE():
    """Le panneau montre les trades du robot ; le compte subit aussi l'import
    historique. Sans ce chiffre, un lecteur qui additionne ce qu'il voit à l'écran ne
    retombe jamais sur son compte — et rien ne lui dit pourquoi."""
    r = reconcilier(_courbe(100_000.0, 100_000.0), realise=-1790.60, latent=0.0,
                    realise_affiche=-10.82)
    assert r["realise_affiche"] == -10.82
    assert r["hors_panneau"] == -1779.78            # ce que le panneau NE montre pas
    assert r["realise"] == -1790.6


def test_des_fenetres_DIFFERENTES_sont_signalees():
    """Additionner deux périodes différentes rend un rapprochement faux sans que rien
    ne le dise. La poche crypto s'est arrêtée le 21/08, la poche actions non."""
    r = reconcilier({"alpaca": _points(99_593.81, 100_482.13),
                     "bitmart": _points(11.56, 0.10, t1="2026-08-21")},
                    realise=0.0, latent=0.0)
    assert r["memes_fenetres"] is False
    assert len(r["fenetres"]) == 2


def test_le_formatage_porte_sur_le_NOMBRE_jamais_sur_la_phrase():
    """L'espace fine ne remplace que le séparateur de MILLIERS. Le dépôt a déjà payé ce
    défaut une fois (`annotation_churn`) : un `replace(",", " ")` appliqué à la phrase
    entière effaçait aussi sa ponctuation, et le texte devenait illisible sans que rien
    n'échoue. On éprouve donc l'unité qui formate, et la phrase qui l'accueille."""
    from packages.research.reconciliation_capital import _montant

    assert _montant(10_000.0) == "+10 000.00"
    assert _montant(-1_814.28) == "-1 814.28"
    assert _montant(12.5) == "+12.50", "sans millier, rien à remplacer"

    r = reconcilier(_courbe(100_000.0, 110_000.0), realise=0.0, latent=0.0)
    assert "10 000" in r["explication"], "les milliers portent une espace fine"
    assert r["explication"].endswith("pas comblé ici."), "la phrase est intacte"


def test_une_courbe_NUE_au_lieu_d_un_dict_echoue_en_le_DISANT():
    """`{compte: points}` contre `points` : l'erreur est naturelle. Un `AttributeError`
    sur `.items()` ne dirait pas quoi corriger — et un silence serait pire."""
    import pytest

    with pytest.raises(TypeError, match="liste de points"):
        capital(_points(100.0, 110.0))


def test_la_VARIATION_du_compte_est_publiee_AVANT_tout_rapprochement():
    """CE QUI MANQUAIT AU PANNEAU (18/09). Il ouvrait sur l'identité et son résidu, donc
    la première chose lue était « écart NON expliqué +2 669 $ » — alors que la question
    posée était « je pars de 100 k, j'en ai 100 734, ça donne quoi ? ». Le résultat est
    un champ à part entière, pas une soustraction laissée au lecteur."""
    from packages.research.reconciliation_capital import reconcilier

    courbes = {"alpaca": [{"t": "2026-06-22", "v": 99_593.81},
                          {"t": "2026-09-18", "v": 100_734.30}],
               "bitmart": [{"t": "2026-06-22", "v": 11.56},
                           {"t": "2026-08-21", "v": 0.10}]}
    r = reconcilier(courbes, realise=-1_888.01, latent=347.98, realise_affiche=74.52)

    assert r["capital_initial"] == 99_605.37
    assert r["capital_final"] == 100_734.40
    assert r["variation"] == 1_129.03
    assert r["variation_part"] == 0.0113
    assert r["jours"] == 88
    assert "99 605.37" in r["resume"] and "+1 129.03" in r["resume"]


def test_les_composantes_RECONSTITUENT_exactement_la_variation():
    """LA RÉPONSE À « ÇA NE MATCH PAS ». 331 trades à +0,23 $ ne font pas la
    variation du compte parce que trois autres lignes existent — l'import, le
    latent, le résidu — et qu'elles sont plus grosses. Lue dans ce sens,
    l'identité n'a aucun reste."""
    from packages.research.reconciliation_capital import reconcilier

    courbes = {"a": [{"t": "2026-01-01", "v": 10_000.0},
                     {"t": "2026-03-01", "v": 11_000.0}]}
    r = reconcilier(courbes, realise=200.0, latent=50.0,
                    realise_affiche=30.0, flux=100.0)

    assert r["explique"] == 350.0                      # réalisé + latent + flux
    assert r["explique"] + r["residu"] == r["variation"] == 1_000.0
    assert r["realise_affiche"] + r["hors_panneau"] == r["realise"]


def test_un_NIVEAU_ne_porte_pas_de_signe_dans_le_resume():
    """« +100 734,40 $ » de capital se lit comme un gain de cent mille dollars. Le signe
    appartient aux variations, pas aux niveaux."""
    from packages.research.reconciliation_capital import reconcilier

    r = reconcilier({"a": [{"t": "2026-01-01", "v": 1_000.0},
                           {"t": "2026-01-31", "v": 900.0}]}, realise=0.0, latent=0.0)
    assert r["resume"].startswith("Le compte est passé de 1 000.00 $ à 900.00 $")
    assert "-100.00" in r["resume"] and "-10.00%" in r["resume"]


def test_une_date_illisible_donne_une_duree_ABSENTE_pas_zero():
    """« en 0 jours » tromperait sur la fenêtre ; une durée absente se voit."""
    from packages.research.reconciliation_capital import reconcilier

    r = reconcilier({"a": [{"t": None, "v": 100.0}, {"t": "pas-une-date", "v": 110.0}]},
                    realise=0.0, latent=0.0)
    assert r["jours"] is None
    assert "jours" not in r["resume"]


def test_la_SOURCE_du_point_de_depart_est_publiee():
    """LE DÉFAUT DU 18/09, révélé en comparant au courtier. `equity_history` enregistre
    un point par jour À CHAQUE BUILD : son premier point est le jour où l'on a COMMENCÉ
    À MESURER, pas l'ouverture du compte. Un rendement calculé depuis cette base répond
    à « depuis que je regarde », pas « depuis que j'ai déposé » — et si la mesure a
    démarré après une baisse, la base est BASSE et le pourcentage FLATTÉ."""
    courbes = {"alpaca": _points(100_000.0, 101_000.0)}
    certain = reconcilier(courbes, realise=0.0, latent=0.0,
                          sources={"alpaca": "courtier"})
    incertain = reconcilier(courbes, realise=0.0, latent=0.0,
                            sources={"alpaca": "enregistrement local"})

    assert certain["depart_certain"] is True
    assert certain["fenetres"][0]["source"] == "courtier"
    assert incertain["depart_certain"] is False
    assert incertain["fenetres"][0]["source"] == "enregistrement local"


def test_sans_source_declaree_le_depart_n_est_PAS_tenu_pour_certain():
    """Le silence ne vaut pas garantie : une source inconnue se traite comme incertaine,
    jamais comme le courtier."""
    r = reconcilier({"alpaca": _points(100.0, 110.0)}, realise=0.0, latent=0.0)
    assert r["fenetres"][0]["source"] == "inconnue"
    assert r["depart_certain"] is False


def test_UNE_poche_locale_suffit_a_rendre_le_depart_incertain():
    """Le capital est une SOMME : si une seule poche part d'une base approximative, le
    total en hérite. Un « presque certain » se lirait comme certain."""
    r = reconcilier({"alpaca": _points(100_000.0, 101_000.0),
                     "bitmart": _points(11.56, 0.10, t1="2026-08-21")},
                    realise=0.0, latent=0.0,
                    sources={"alpaca": "courtier", "bitmart": "enregistrement local"})
    assert r["depart_certain"] is False
