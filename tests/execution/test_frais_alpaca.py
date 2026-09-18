"""Lire les frais RÉELS du courtier — sans dépendre du nom des classes du SDK.

CE QUI A ÉCHOUÉ (18/09). Le premier essai importait `GetAccountActivitiesRequest`
depuis `alpaca.trading.requests` : la classe n'existe pas dans la version installée,
l'import levait, et les frais restaient introuvables. L'identité du compte gardait donc
son trou de 810,30 $ alors que le chiffre était à portée d'appel.

On passe par la route REST `/account/activities`, qui est le contrat public d'Alpaca.
Ces tests exercent la lecture SANS le SDK : seul `_client.get` est simulé.
"""

from __future__ import annotations

from packages.execution.alpaca_broker import AlpacaBroker


class _Client:
    """Un client REST factice : rend des pages, et retient ce qu'on lui a demandé."""

    def __init__(self, pages):
        self.pages, self.appels = list(pages), []

    def get(self, path, params=None):
        self.appels.append((path, dict(params or {})))
        return self.pages.pop(0) if self.pages else []


def _broker(pages):
    b = AlpacaBroker.__new__(AlpacaBroker)      # sans __init__ : pas besoin du SDK
    b._client = _Client(pages)
    return b


def test_les_montants_en_DOLLARS_sont_sommes_par_type():
    b = _broker([[{"id": "1", "activity_type": "FEE", "net_amount": "-0.77"},
                  {"id": "2", "activity_type": "FEE", "net_amount": "-0.08"},
                  {"id": "3", "activity_type": "CFEE", "net_amount": "-3.00"}]])
    f = b.frais()
    assert f["disponible"] is True and f["n"] == 3
    assert f["par_type"] == {"FEE": -0.85, "CFEE": -3.0}
    assert f["total_usd"] == -3.85


def test_un_prelevement_EN_JETONS_est_compte_a_part_jamais_converti():
    """Une `CFEE` sans montant retire des JETONS. Lui donner un prix qu'on choisirait
    nous-mêmes fabriquerait un coût ; sa trace en dollars est déjà dans la valeur du
    portefeuille."""
    b = _broker([[{"id": "1", "activity_type": "CFEE", "symbol": "BTC/USD",
                   "qty": "-0.00003722"},
                  {"id": "2", "activity_type": "CFEE", "net_amount": "-2.63"}]])
    f = b.frais()
    assert f["total_usd"] == -2.63, "seul le dollar entre dans le total"
    assert f["n_en_nature"] == 1
    assert f["en_nature"][0]["symbole"] == "BTC/USD"


def test_la_PAGINATION_suit_le_dernier_identifiant_et_s_arrete():
    b = _broker([[{"id": "a", "activity_type": "FEE", "net_amount": "-1.0"}],
                 [{"id": "b", "activity_type": "FEE", "net_amount": "-2.0"}],
                 []])
    f = b.frais()
    assert f["total_usd"] == -3.0 and f["n"] == 2
    jetons = [p.get("page_token") for _, p in b._client.appels]
    assert jetons == [None, "a", "b"], "chaque page repart du dernier identifiant vu"


def test_un_jeton_qui_NE_BOUGE_PAS_arrete_la_boucle():
    """Une API qui rend toujours la même page ne doit pas nous faire tourner à l'infini
    — le défaut que `paginer` a déjà coûté à ce dépôt."""
    b = _broker([[{"id": "z", "activity_type": "FEE", "net_amount": "-1.0"}]] * 10)
    f = b.frais(pages_max=10)
    assert f["n"] == 2, "on s'arrête dès que l'identifiant de fin se répète"


def test_une_PANNE_en_cours_de_route_garde_ce_qui_a_ete_LU():
    """Perdre trois pages déjà lues parce que la quatrième a échoué transformerait une
    panne partielle en frais sous-estimés — sans que rien ne le dise."""
    class _Casse(_Client):
        def get(self, path, params=None):
            if self.appels:
                raise RuntimeError("API muette")
            return super().get(path, params)

    b = AlpacaBroker.__new__(AlpacaBroker)
    b._client = _Casse([[{"id": "1", "activity_type": "FEE", "net_amount": "-5.0"}]])
    f = b.frais()
    assert f["disponible"] is True and f["total_usd"] == -5.0


def test_une_panne_AVANT_toute_lecture_se_DIT():
    """Zéro frais et frais illisibles ne se ressemblent pas."""
    class _Muet:
        def get(self, path, params=None):
            raise RuntimeError("401 unauthorized")

    b = AlpacaBroker.__new__(AlpacaBroker)
    b._client = _Muet()
    f = b.frais()
    assert f["disponible"] is False and "401" in f["motif"]


def test_une_activite_rendue_en_OBJET_se_lit_comme_un_dict():
    """La route REST rend du JSON brut aujourd'hui. Une version du SDK qui le parserait
    en modèles ferait échouer un `.get()` — et l'échec serait SILENCIEUX : `frais`
    rendrait zéro dollar au lieu de lever, et un zéro de frais se lit « aucun frais
    prélevé ». C'est faux de 810,30 $ sur ce compte."""
    class _Acte:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    b = _broker([[_Acte(id="1", activity_type="FEE", net_amount="-0.77"),
                  _Acte(id="2", activity_type="CFEE", symbol="ETH/USD", qty="-0.03")],
                 []])
    f = b.frais()
    assert f["total_usd"] == -0.77
    assert f["n_en_nature"] == 1 and f["en_nature"][0]["symbole"] == "ETH/USD"
