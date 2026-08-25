"""IBKR verrouillé sur compte DÉMO. Trois verrous, un seul suffit pour refuser.

L'exigence est explicite : le bot doit pouvoir trader sur un compte DEMO d'Interactive Brokers,
et **pas** sur un compte réel. Ces tests fixent le contrat de refus, pas seulement le contrat
d'acceptation — un garde-fou ne se teste que par ce qu'il bloque.
"""

import pytest

from packages.core.models import Side
from packages.execution.ibkr_broker import (CompteReelRefuse, IBKRBroker, PORTS_DEMO, PORTS_REELS,
                                            configuree, verifier_compte, verifier_port)


class PasserelleFactice:
    """Imite `ib_insync.IB` : connexion, comptes gérés, déconnexion. N'exécute rien."""

    def __init__(self, comptes: list[str]):
        self._comptes = comptes
        self.connecte = False
        self.deconnexions = 0

    def connect(self, hote, port, clientId=0):
        self.connecte = True

    def managedAccounts(self):
        return self._comptes

    def disconnect(self):
        self.connecte = False
        self.deconnexions += 1

    def accountSummary(self, compte=None):
        class L:
            tag, value = "NetLiquidation", "1000000"
        return [L()]

    def positions(self, compte=None):
        return []

    def trades(self):
        return []

    def openOrders(self):
        return []


# --- VERROU 1 : LE PORT ----------------------------------------------------------------------

@pytest.mark.parametrize("port", sorted(PORTS_REELS))
def test_un_port_reel_est_refuse_avant_toute_connexion(port):
    passerelle = PasserelleFactice(["DU1234567"])
    with pytest.raises(CompteReelRefuse) as e:
        IBKRBroker(port=port, connecteur=passerelle)
    assert "RÉEL" in str(e.value)
    assert passerelle.connecte is False, "aucune connexion ne doit être tentée"


@pytest.mark.parametrize("port", sorted(PORTS_DEMO))
def test_les_ports_papier_passent(port):
    b = IBKRBroker(port=port, connecteur=PasserelleFactice(["DU1234567"]))
    assert b.is_paper is True and b.port == port


def test_un_port_inconnu_n_est_pas_presume_sur_mais_n_est_pas_disqualifiant():
    """Il n'est pas refusé — c'est l'identifiant de compte qui tranche derrière lui."""
    assert verifier_port(9999).demo is True
    with pytest.raises(CompteReelRefuse):
        IBKRBroker(port=9999, connecteur=PasserelleFactice(["U1234567"]))


# --- VERROU 2 : L'IDENTIFIANT DE COMPTE (le décisif) -----------------------------------------

@pytest.mark.parametrize("compte", ["U1234567", "F1234567", "X999", "1234567"])
def test_un_compte_reel_rompt_la_connexion(compte):
    """Le port peut être reconfiguré dans TWS : se fier à lui seul donnerait un garde-fou qu'on
    croit armé. L'identifiant renvoyé par la passerelle, lui, ne se falsifie pas d'ici."""
    passerelle = PasserelleFactice([compte])
    with pytest.raises(CompteReelRefuse):
        IBKRBroker(port=7497, connecteur=passerelle)
    assert passerelle.deconnexions == 1, "la session doit être fermée AVANT de lever"


def test_un_identifiant_vide_est_refuse():
    """Inconnu ≠ sûr : ne pas savoir à quel compte on parle interdit tout ordre."""
    assert verifier_compte("").demo is False
    with pytest.raises(CompteReelRefuse):
        IBKRBroker(port=7497, connecteur=PasserelleFactice([]))


@pytest.mark.parametrize("compte", ["DU1234567", "DF7654321", "du1234567"])
def test_les_comptes_demo_passent(compte):
    b = IBKRBroker(port=7497, connecteur=PasserelleFactice([compte]))
    assert b.compte == compte and verifier_compte(compte).demo is True


def test_DU_ne_doit_pas_etre_lu_comme_U():
    """« DU » commence par « D », pas par « U » : tester le préfixe réel en premier laisserait
    passer tous les comptes papier — ou refuserait tout. L'ordre du test porte le sens."""
    assert verifier_compte("DU1").demo is True
    assert verifier_compte("U1").demo is False


# --- VERROU 3 : OPT-IN EXPLICITE --------------------------------------------------------------

def test_ibkr_est_desactive_par_defaut(monkeypatch):
    monkeypatch.delenv("QUANT_IBKR_ENABLE", raising=False)
    assert configuree() is False
    monkeypatch.setenv("QUANT_IBKR_ENABLE", "0")
    assert configuree() is False
    monkeypatch.setenv("QUANT_IBKR_ENABLE", "1")
    assert configuree() is True


# --- AUCUN CHEMIN VERS LE RÉEL ----------------------------------------------------------------

def test_aucun_argument_n_autorise_un_compte_reel():
    """Contrat central : il n'existe ni paramètre, ni variable d'environnement qui ouvre le
    réel. Passer en réel exigerait de modifier le fichier — donc un geste tracé dans git."""
    import inspect

    sig = inspect.signature(IBKRBroker.__init__)
    interdits = ("live", "real", "reel", "paper", "production")
    assert not [p for p in sig.parameters if any(i in p.lower() for i in interdits)]


def test_le_module_ne_lit_aucune_variable_qui_ouvrirait_le_reel():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2]
           / "packages" / "execution" / "ibkr_broker.py").read_text(encoding="utf-8")
    for motif in ("QUANT_IBKR_LIVE", "QUANT_IBKR_REAL", "allow_live", "force_live"):
        assert motif not in src


def test_l_emission_d_ordres_est_refusee_explicitement():
    """Le courtier est LISIBLE mais pas encore ÉMETTEUR. Un refus explicite vaut mieux qu'une
    quantité approximative : IBKR raisonne en quantité, pas en montant."""
    b = IBKRBroker(port=7497, connecteur=PasserelleFactice(["DU1234567"]))
    with pytest.raises(NotImplementedError, match="quantité"):
        b.submit_notional("AAPL", Side.LONG, 1000.0)
    with pytest.raises(NotImplementedError):
        b.close_position("AAPL")


def test_le_garde_est_rejoue_avant_chaque_ordre():
    """La vérification à la connexion ne suffit pas : une passerelle peut être relancée sur un
    autre compte pendant que le processus tourne."""
    b = IBKRBroker(port=7497, connecteur=PasserelleFactice(["DU1234567"]))
    b.compte = "U9999999"                       # la passerelle a basculé sur le réel
    with pytest.raises(CompteReelRefuse):
        b.submit_notional("AAPL", Side.LONG, 1000.0)


# --- LECTURE ET DIAGNOSTIC --------------------------------------------------------------------

def test_lecture_de_l_equity():
    b = IBKRBroker(port=7497, connecteur=PasserelleFactice(["DU1234567"]))
    assert b.equity() == 1_000_000.0


def test_le_diagnostic_masque_l_identifiant_et_dit_les_verrous():
    b = IBKRBroker(port=7497, connecteur=PasserelleFactice(["DU1234567"]))
    d = b.diagnostic()
    assert d["demo"] is True and d["emetteur"] is False
    assert "DU1234567" not in d["compte"] and d["compte"].endswith("…")
    assert len(d["verrous"]) == 2 and "papier" in d["verrous"][0]
