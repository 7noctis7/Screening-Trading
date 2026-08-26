"""Un ordre ENVOYÉ n'est pas un ordre EXÉCUTÉ.

`run_live` faisait `sent += 1` dès que l'appel courtier ne levait pas d'exception,
sans jamais lire ce que le courtier avait RÉPONDU. Alpaca accepte un ordre puis peut
le rejeter : le compteur annonçait des ordres partis alors que rien n'était passé.
C'est ce trou qui a laissé le satellite actions vide sans une ligne de journal.
"""

import pytest

from packages.core.models import Order, OrderStatus, Side
from packages.execution.order_outcome import (
    EN_COURS,
    INCONNU,
    REJETE,
    REMPLI,
    classer,
    compte_comme_envoye,
    motif_rejet,
    resume,
)


class Rep:
    """Réponse courtier duck-typée."""

    def __init__(self, status, **kw):
        self.status = status
        for k, v in kw.items():
            setattr(self, k, v)


class Enum:
    """Imite un enum alpaca-py, qui s'imprime « OrderStatus.FILLED »."""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"OrderStatus.{self.value.upper()}"


# --- les quatre issues ------------------------------------------------------

@pytest.mark.parametrize("statut", ["filled", "partially_filled"])
def test_rempli(statut):
    assert classer(Rep(statut)) == REMPLI


@pytest.mark.parametrize("statut", ["rejected", "canceled", "expired", "suspended"])
def test_rejete(statut):
    assert classer(Rep(statut)) == REJETE


@pytest.mark.parametrize("statut", ["new", "accepted", "pending_new", "held"])
def test_en_cours(statut):
    """Cas NORMAL à la soumission d'un ordre au marché : exiger « rempli » ici
    produirait une fausse alerte à chaque ordre."""
    assert classer(Rep(statut)) == EN_COURS


@pytest.mark.parametrize("res", [None, Rep(""), Rep("chose_inconnue"), object()])
def test_inconnu(res):
    assert classer(res) == INCONNU


# --- LE point du module -----------------------------------------------------

def test_un_rejet_ne_compte_pas_comme_envoye():
    """Compter un rejet comme un envoi est exactement ce qui rendait le défaut
    invisible."""
    assert compte_comme_envoye(Rep("rejected")) is False
    assert compte_comme_envoye(Rep("accepted")) is True
    assert compte_comme_envoye(Rep("filled")) is True


def test_une_issue_inconnue_ne_compte_pas_non_plus():
    """Ni succès ni échec — et surtout pas à compter comme un succès."""
    assert compte_comme_envoye(None) is False
    assert compte_comme_envoye(Rep("")) is False


# --- compatibilité avec les courtiers RÉELS du dépôt ------------------------

def test_vocabulaire_interne_bitmart_et_binance():
    """Bitmart et Binance renvoient un `Order` avec `OrderStatus.SUBMITTED`. L'oublier
    aurait classé INCONNU tous les ordres crypto, donc cessé de les compter."""
    o = Order("BTC/USD", Side.LONG, 0.0, None)
    o.status = OrderStatus.SUBMITTED
    assert classer(o) == EN_COURS and compte_comme_envoye(o) is True
    o.status = OrderStatus.REJECTED
    assert classer(o) == REJETE and compte_comme_envoye(o) is False


def test_close_position_renvoie_un_booleen():
    """`AlpacaBroker.close_position` renvoie True/False, pas un ordre. Sans ce cas,
    toute liquidation aurait été classée INCONNUE — le correctif aurait créé le
    défaut inverse de celui qu'il corrige."""
    assert classer(True) == REMPLI and compte_comme_envoye(True) is True
    assert classer(False) == REJETE and compte_comme_envoye(False) is False


def test_enum_alpaca_est_lu_correctement():
    """« OrderStatus.FILLED » ne doit pas être pris pour un statut inconnu."""
    assert classer(Rep(Enum("filled"))) == REMPLI
    assert classer(Rep(Enum("rejected"))) == REJETE


def test_reponse_en_dictionnaire():
    assert classer({"status": "rejected"}) == REJETE
    assert classer({"status": "filled"}) == REMPLI


# --- lisibilité -------------------------------------------------------------

def test_motif_de_rejet_est_repris_tel_quel():
    r = Rep("rejected", reject_reason="insufficient buying power")
    assert "insufficient buying power" in motif_rejet(r)
    assert "insufficient buying power" in resume(r)


def test_aucun_motif_invente():
    """On n'invente pas d'explication quand le courtier n'en donne pas."""
    assert motif_rejet(Rep("rejected")) == ""


def test_resume_distingue_les_issues():
    assert "REJETÉ" in resume(Rep("rejected"))
    assert "rempli" in resume(Rep("filled"))
    assert "non confirmé" in resume(Rep("accepted"))
    assert "INCONNUE" in resume(None)


def test_classer_ne_leve_jamais():
    """Un diagnostic ne doit pas casser l'exécution."""
    class Piege:
        @property
        def status(self):
            raise RuntimeError("boum")

    try:
        classer(Piege())
    except RuntimeError:
        pytest.fail("classer() a laissé remonter une exception")
