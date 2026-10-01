"""`QUANT_NO_CRYPTO_LIVE` est-il honoré par `run_live` LUI-MÊME ?

Contexte (audit du 01/10, B1) : le garde-fou n'était lu que par
`scripts/cron_live.sh`, qui vide les clés crypto avant d'appeler `run_live.py`.
`make live-go` appelle le script directement : avec des clés Bitmart dans `.env`,
la place était instanciée en `dry_run=False` — Bitmart n'a pas de paper — et,
aucune cible ne portant `capital="bitmart"`, `_broker_targets` mettait tout le
détenu crypto à zéro, c'est-à-dire en LIQUIDATION.

Ces tests figent les deux comportements : sans le drapeau, rien ne change ; avec, aucune
place crypto n'est instanciée et aucun ordre crypto ne peut partir.
"""

import importlib.util
import pathlib

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


# ── sans le drapeau : comportement INCHANGÉ (le défaut B1, documenté ici) ──────

def test_sans_drapeau_la_place_crypto_est_instanciee_en_reel(monkeypatch, place):
    rl = _run_live(monkeypatch)
    crypto, sent, sold = _passage_live(rl)
    assert len(place.instances) == 1 and crypto.dry_run is False
    assert ("close", "BTC/USDT", None) in crypto.ordres and sent == 1 and sold


# ── avec le drapeau : aucune place, aucun ordre crypto ───────────────────────────────

@pytest.mark.parametrize("valeur", ["1", "true", "YES", " on "])
def test_avec_drapeau_aucune_place_crypto_n_est_instanciee(monkeypatch, place, valeur):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", valeur)
    rl = _run_live(monkeypatch)
    crypto, sent, sold = _passage_live(rl)
    assert crypto is None
    assert place.instances == []                          # jamais construite
    assert sent == 0 and sold == []


@pytest.mark.parametrize("valeur", ["", "0", "false", "non"])
def test_une_valeur_non_affirmative_ne_neutralise_pas(monkeypatch, valeur):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", valeur)
    assert _run_live(monkeypatch).crypto_live_neutralisee() is False


def test_le_drapeau_ne_change_rien_en_dry_run(monkeypatch, place):
    monkeypatch.setenv("QUANT_NO_CRYPTO_LIVE", "1")
    rl = _run_live(monkeypatch)
    assert rl._make_brokers(dry=True) == (None, None)
    assert rl._make_brokers(dry=True, apercu=True) == (None, None)
    assert place.instances == []
