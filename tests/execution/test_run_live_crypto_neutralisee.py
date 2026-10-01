"""`QUANT_NO_CRYPTO_LIVE` (défaut 1) est honoré par `run_live` LUI-MÊME.

Contexte (audit du 01/10, B1) : le garde-fou n'était lu que par
`scripts/cron_live.sh`, qui vide les clés crypto avant d'appeler `run_live.py`.
`make live-go` appelle le script directement : avec des clés Bitmart dans `.env`,
la place était instanciée en `dry_run=False` — Bitmart n'a pas de paper — et,
aucune cible ne portant `capital="bitmart"`, `_broker_targets` mettait tout le
détenu crypto à zéro, c'est-à-dire en LIQUIDATION.

Suivi P0 (#424) : le défaut dans `run_live` est aligné sur `cron_live.sh`
(`${QUANT_NO_CRYPTO_LIVE:-1}`) — paper-only sûr. Opt-in live crypto : `=0`.
"""

import importlib.util
import pathlib
from unittest.mock import MagicMock

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _environnement(monkeypatch):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")      # isole du calendrier NYSE
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    monkeypatch.delenv("QUANT_NO_CRYPTO_LIVE", raising=False)


def _run_live(monkeypatch):
    chemin = RACINE / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location("run_live", chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "_alpaca_ou_rien", lambda: None)   # pas de réseau Alpaca
    return m


class _Reponse:
    def __init__(self, status):
        self.status = status


class CourtierCrypto:
    """Doublure d'une place crypto RÉELLE : enregistre, n'exécute rien."""

    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.ordres: list[tuple] = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))
        return _Reponse("accepted")

    def close_position(self, sym):
        self.ordres.append(("close", sym, None))
        return True


class PlaceFactice:
    """Remplace `venues.venue_crypto()` : compte les instanciations."""

    nom = "Bitmart"

    def __init__(self):
        self.instances: list[CourtierCrypto] = []

    def broker(self, dry_run=True):
        b = CourtierCrypto(dry_run=dry_run)
        self.instances.append(b)
        return b


@pytest.fixture
def place(monkeypatch):
    p = PlaceFactice()
    monkeypatch.setattr("packages.execution.venues.venue_crypto", lambda: p)
    return p


DETENU_CRYPTO = {"BTC/USDT": 2_500.0}


def _passage_live(rl):
    """Un passage `--live --yes` sur la seule poche crypto : aucune cible, du détenu."""
    alpaca, crypto = rl._make_brokers(dry=False)
    assert alpaca is None
    sent, _, sold = rl._reconcile([], [("Bitmart", crypto, 10_000.0, DETENU_CRYPTO)],
                                  1.0, None, dry=False)
    return crypto, sent, sold


# ── défaut (absent) = bloqué, aligné cron_live.sh ──────────────────────────────

def test_defaut_bloque_la_place_crypto(monkeypatch, place, capsys):
    """Absent → défaut 1 → aucune place, même en --live."""
    rl = _run_live(monkeypatch)
    crypto, sent, sold = _passage_live(rl)
    assert crypto is None
    assert place.instances == []
    assert sent == 0 and sold == []
    assert "QUANT_NO_CRYPTO_LIVE actif" in capsys.readouterr().out
    assert rl.crypto_live_neutralisee() is True


@pytest.mark.parametrize("valeur", ["1", "true", "YES", " on "])
def test_avec_drapeau_aucune_place_crypto_n_est_instanciee(monkeypatch, place, valeur):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", valeur)
    rl = _run_live(monkeypatch)
    crypto, sent, sold = _passage_live(rl)
    assert crypto is None
    assert place.instances == []
    assert sent == 0 and sold == []


# ── opt-in : live crypto autorisé ──────────────────────────────────────────────

@pytest.mark.parametrize("valeur", ["0", "false", "off", "no"])
def test_opt_in_autorise_la_place_en_reel(monkeypatch, place, valeur):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", valeur)
    rl = _run_live(monkeypatch)
    assert rl.crypto_live_neutralisee() is False
    crypto, sent, sold = _passage_live(rl)
    assert len(place.instances) == 1 and crypto.dry_run is False
    assert ("close", "BTC/USDT", None) in crypto.ordres and sent == 1 and sold


def test_opt_in_zero_cree_broker_dry_run_false(monkeypatch):
    """QUANT_NO_CRYPTO_LIVE=0 : venue_crypto().broker(dry_run=False) est appelé."""
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", "0")
    monkeypatch.setenv("QUANT_CRYPTO_VENUE", "binance")
    rl = _run_live(monkeypatch)
    broker = object()
    fake = MagicMock()
    fake.nom = "Binance"
    fake.broker = MagicMock(return_value=broker)
    monkeypatch.setattr(rl, "_alpaca_ou_rien", lambda: "ALPACA")
    monkeypatch.setattr("packages.execution.venues.venue_crypto", lambda: fake)

    alpaca, crypto = rl._make_brokers(dry=False)

    assert alpaca == "ALPACA"
    assert crypto is broker
    fake.broker.assert_called_once_with(dry_run=False)


def test_valeur_vide_explicite_ne_neutralise_pas(monkeypatch):
    """Chaîne vide posée explicitement ≠ défaut (opt-out du défaut sûr)."""
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", "")
    assert _run_live(monkeypatch).crypto_live_neutralisee() is False


def test_le_drapeau_ne_change_rien_en_dry_run(monkeypatch, place):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", "1")
    rl = _run_live(monkeypatch)
    assert rl._make_brokers(dry=True) == (None, None)
    assert rl._make_brokers(dry=True, apercu=True) == (None, None)
    assert place.instances == []
