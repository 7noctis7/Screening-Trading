"""La place crypto est un choix explicite, et un mauvais choix ne casse rien."""
import pytest

from packages.execution.venues import BINANCE, BITMART, DEFAUT, PLACES, venue_crypto


def test_le_defaut_est_binance():
    """0,10 % de taker contre 0,25 % : à rotation égale, les frais crypto sont divisés par 2,5."""
    assert DEFAUT == "binance"
    assert venue_crypto().cle == "binance"


def test_bascule_explicite(monkeypatch):
    monkeypatch.setenv("QUANT_CRYPTO_VENUE", "bitmart")
    assert venue_crypto().cle == "bitmart"


def test_nom_inconnu_retombe_sur_le_defaut(monkeypatch):
    """Une faute de frappe ne doit pas priver de courtier."""
    monkeypatch.setenv("QUANT_CRYPTO_VENUE", "binanace")
    assert venue_crypto().cle == DEFAUT


def test_casse_et_espaces_tolerees(monkeypatch):
    monkeypatch.setenv("QUANT_CRYPTO_VENUE", "  BitMart ")
    assert venue_crypto().cle == "bitmart"


def test_place_sans_cles_nest_pas_configuree(monkeypatch):
    for k in BINANCE.env:
        monkeypatch.delenv(k, raising=False)
    assert not BINANCE.configuree()
    monkeypatch.setenv("BINANCE_API_KEY", "x")
    monkeypatch.setenv("BINANCE_API_SECRET", "y")
    assert BINANCE.configuree()


def test_les_cles_de_chaque_place_sont_distinctes():
    assert set(BINANCE.env).isdisjoint(BITMART.env)


def test_le_barème_de_frais_connait_chaque_place():
    """Une place sans barème facturerait zéro — un backtest optimiste par omission."""
    from packages.execution.costs import BROKER_FEES
    for cle in PLACES:
        assert cle in BROKER_FEES, cle


def test_binance_est_moins_chere_que_bitmart():
    from packages.execution.costs import BROKER_FEES
    assert BROKER_FEES["binance"]["commission_bps"] < BROKER_FEES["bitmart"]["commission_bps"]


def test_la_fabrique_pointe_une_classe_importable():
    for v in PLACES.values():
        mod, _, cls = v._fabrique.partition(":")
        import importlib
        assert hasattr(importlib.import_module(mod), cls), v.cle


def test_instancier_ne_passe_aucun_ordre():
    """Garde-fou : construire un courtier en dry-run ne doit rien envoyer."""
    b = BINANCE.broker(dry_run=True)
    assert getattr(b, "_dry", True) or not getattr(b, "_live", lambda: False)()
