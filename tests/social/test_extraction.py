"""Une étiquette fausse est pire qu'un « je ne sais pas ».

`UNKNOWN` se voit, se compte, et pousse à regarder le message. Une étiquette plausible
`UNKNOWN` se voit, se compte, et pousse à relire le message. Une étiquette plausible
D'où la règle appliquée partout ici : au moindre doute, `UNKNOWN` ou `None`.

Le défaut le plus coûteux est trouvé par le premier test : les lookarounds de la
frontière de mot ne portaient que sur la PREMIÈRE alternative de l'alternance, faute de
groupe non capturant. « Longtemps » se lisait donc « long », et un message d'observation
héritait d'une direction d'achat que personne n'avait écrite.
"""
from __future__ import annotations

from packages.social.extraction import classification, direction, ticker
from packages.social.modele import Classification as C
from packages.social.modele import Direction


def test_un_mot_qui_COMMENCE_par_long_n_est_pas_une_direction():
    """RÉGRESSION : sans groupe non capturant, « Longtemps » devenait LONG."""
    assert direction("Longtemps que je regarde ce graphique") is None
    assert direction("Je passe LONG") is Direction.LONG


def test_les_deux_sens_cites_ne_departagent_PAS():
    assert direction("long et short se valent ici") is None


def test_aucun_sens_cite_vaut_None_pas_neutre():
    assert direction("Le marché consolide") is None


def test_la_paire_explicite_prime_et_donne_les_deux_champs():
    assert ticker("achat BTCUSDT maintenant") == ("BTC", "BTCUSDT")


def test_DEUX_actifs_cites_ne_donnent_AUCUN_ticker():
    """On ne choisit pas à la place de l'auteur : deux actifs, donc aucun retenu."""
    assert ticker("je compare BTC et ETH") == (None, None)
    assert ticker("BTCUSDT vs ETHUSDT") == (None, None)


def test_le_nom_en_toutes_lettres_est_reconnu():
    assert ticker("Bitcoin tient bien")[0] == "BTC"
    assert ticker("Ethereum casse son support")[0] == "ETH"


def test_le_cashtag_est_reconnu():
    assert ticker("$SOL en forme")[0] == "SOL"


def test_la_regle_la_plus_SPECIFIQUE_gagne():
    """« Je remonte mon stop » est une mise à jour — le dire perdrait l'essentiel."""
    assert classification("Je remonte mon stop à l'entrée") is C.MOVE_STOP
    assert classification("Annulation du signal, invalidé") is C.CANCEL_SIGNAL
    assert classification("TP1 atteint sur la position") is C.TAKE_PROFIT_UPDATE


def test_un_signal_se_reconnait_a_ses_niveaux():
    assert classification("Entrée 64000, SL 61000, TP1 68000") is C.TRADE_SIGNAL


def test_rien_ne_correspond_donne_UNKNOWN_et_non_un_fourre_tout():
    """`EDUCATIONAL` irait pour n'importe quoi — et ferait disparaître le doute."""
    assert classification("Bonjour à tous") is C.UNKNOWN
