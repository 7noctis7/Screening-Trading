"""Une liquidation de crypto ne doit pas être bloquée par le calendrier des ACTIONS.

Constat en production le 27/08, sortie brute :

    AAVEUSD  Alpaca  cible 0$  détenu 2541$  Δ -2541$   ⏸ REPORTÉ — hors séance

Chaîne causale. Les CIBLES portent « AAVE/USD » ; les POSITIONS rendues par Alpaca
portent « AAVEUSD », sans séparateur. Une position à SOLDER n'a par définition pas de
ligne cible : `_broker_targets` la crée avec `{"o": None}`. Le code lisait alors
`(o or {}).get("asset_class") or "equity"` → « equity » pour TOUTE liquidation
hors-univers. La porte de séance NYSE bloquait donc un actif qui se négocie 24/7.

Gravité : c'est un DÉSENGAGEMENT. Le portail de risque ne bloque jamais une réduction
d'exposition (« [ok] désengagement — jamais bloqué par le portail ») ; le calendrier ne
doit pas le faire par méprise. Et rien ne met les ordres reportés en file d'attente :
le report se serait reproduit à l'identique chaque nuit.
"""

import pytest

from packages.execution.market_calendar import is_open
from packages.execution.routing import classe_actif


@pytest.mark.parametrize("symbole", ["AAVEUSD", "BTCUSD", "SHIBUSD", "USDCUSD"])
def test_le_format_POSITION_du_courtier_est_reconnu_crypto(symbole):
    """Le format sans séparateur — celui qui a causé le bug."""
    assert classe_actif(symbole) == "crypto"


@pytest.mark.parametrize("symbole", ["BTC/USD", "PEPE/USD", "ETH-USD"])
def test_le_format_CIBLE_reste_reconnu(symbole):
    assert classe_actif(symbole) == "crypto"


@pytest.mark.parametrize("symbole", ["TSLA", "AAPL", "QQQ", "T", "BK"])
def test_les_actions_restent_des_actions(symbole):
    assert classe_actif(symbole) == "equity"


def test_un_ticker_action_finissant_par_USD_n_est_PAS_crypto():
    """Le garde-fou qui évite le faux positif : la base doit être dans la whitelist
    Alpaca. Sans cette condition, toute action au ticker finissant par « USD »
    deviendrait crypto et échapperait à la porte de séance — l'erreur inverse, et
    celle-là enverrait un ordre qui ne peut pas se remplir."""
    assert classe_actif("XYZUSD") == "equity"


def test_une_classe_explicite_est_respectee():
    """Quand la ligne cible porte l'information, elle fait autorité : on ne devine
    pas."""
    assert classe_actif("QQQ", "etf") == "etf"
    assert classe_actif("N_IMPORTE_QUOI", "crypto") == "crypto"


def test_une_classe_inconnue_retombe_sur_l_inference():
    """`asset_class` vide ou fantaisiste ne doit pas court-circuiter la détection."""
    assert classe_actif("AAVEUSD", "") == "crypto"
    assert classe_actif("AAVEUSD", "???") == "crypto"


def test_le_bug_de_production_est_ferme():
    """Le test de bout en bout : AAVEUSD doit être négociable hors séance NYSE.

    Rouge avec l'ancien défaut `or "equity"`, vert avec l'inférence.
    """
    ac = classe_actif("AAVEUSD", "")
    assert is_open(asset_class=ac), "une liquidation crypto reste bloquée hors séance"


def test_une_action_reste_bien_bloquee_hors_seance():
    """Contrepartie : le correctif ne doit pas ouvrir une porte qui doit rester fermée.

    Un ordre actions hors séance part en TimeInForce.DAY sans extended_hours — il ne
    PEUT pas se remplir. Le reporter est la bonne réponse.
    """
    from datetime import datetime, timedelta, timezone
    minuit_ny = datetime(2026, 8, 27, 6, 0, tzinfo=timezone(timedelta(hours=2)))
    assert not is_open(minuit_ny, asset_class=classe_actif("TSLA"))
    assert is_open(minuit_ny, asset_class=classe_actif("AAVEUSD"))
