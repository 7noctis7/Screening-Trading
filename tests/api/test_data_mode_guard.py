"""Le mode de données est un CONTRAT, pas une chaîne comparée au jugé.

Régression historique : `_load_prices` renvoie « réel (YAHOO.db) » / « mixte (…) » / « synthetic »,
mais trois gardes testaient `mode == "real"`. Toujours faux, sans erreur ni log : le nettoyage des
titres périmés, la gate d'audit PwC du snapshot et son rapport d'affichage étaient éteints en
production alors que le code laissait croire l'inverse. Ces tests figent le prédicat ET le fait
que les libellés produits par le chargeur le satisfont.
"""
from apps.api.snapshot import is_real_mode


def test_libelle_reel_reconnu():
    # Les libellés RÉELLEMENT produits par _load_prices en mode réel.
    assert is_real_mode("réel (YAHOO.db)")
    assert is_real_mode("réel (YAHOO.db + maj market.db)")
    assert is_real_mode("réel")


def test_mixte_et_synthetique_refuses():
    # Mixte = au moins un titre en repli synthétique → on ne certifie pas « réel ».
    assert not is_real_mode("mixte (180 réels / 200 via YAHOO.db)")
    assert not is_real_mode("synthetic")


def test_absence_de_mode_refusee():
    assert not is_real_mode(None)
    assert not is_real_mode("")


def test_la_chaine_real_ne_suffit_plus():
    """Le bug d'origine : « real » (anglais, sans accent) n'est JAMAIS produit par le chargeur.

    On garde le cas explicite pour que quiconque réintroduirait la comparaison anglaise voie
    immédiatement qu'elle ne correspond à aucun libellé réel.
    """
    assert not is_real_mode("real")


def test_les_libelles_du_chargeur_sont_couverts():
    """Aucun libellé ne doit exister hors des trois familles connues."""
    produits = ["synthetic", "réel (YAHOO.db)", "mixte (12 réels / 200 via YAHOO.db)"]
    reconnus = [m for m in produits if is_real_mode(m)]
    assert reconnus == ["réel (YAHOO.db)"]


# --- Certifier « tout est réel » ≠ « puis-je comparer des dates » ------------------------

def test_le_nettoyage_des_perimes_accepte_le_mode_MIXTE():
    """Le 07/09 : le VPS tourne en « mixte », le nettoyage ne s'exécutait donc jamais et des
    titres arrêtés depuis des mois restaient dans l'univers — BK au 18 juin, CA au 26 mai.
    Refuser « mixte » est juste pour CERTIFIER ; c'est faux pour comparer des horodatages."""
    from apps.api.snapshot import contient_des_prix_reels
    assert contient_des_prix_reels("mixte (779 réels / 929 via market.db)")
    assert contient_des_prix_reels("réel (YAHOO.db)")


def test_le_nettoyage_refuse_le_synthetique_et_l_absence():
    """Sur des prix inventés, « périmé » n'a aucun sens : les dates aussi sont fabriquées."""
    from apps.api.snapshot import contient_des_prix_reels
    assert not contient_des_prix_reels("synthetic")
    assert not contient_des_prix_reels(None)
    assert not contient_des_prix_reels("")


def test_les_deux_predicats_restent_DISTINCTS():
    """S'ils convergeaient, on aurait de nouveau une seule réponse pour deux questions."""
    from apps.api.snapshot import contient_des_prix_reels, is_real_mode
    mixte = "mixte (12 réels / 200 via YAHOO.db)"
    assert contient_des_prix_reels(mixte) and not is_real_mode(mixte)
