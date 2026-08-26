"""Le garde-fou de séance est-il RÉELLEMENT dans le chemin des ordres ?

Constat du 26/08 sur le compte paper : cœur QQQ + huit lignes crypto + ZÉRO action,
et 28 % de cash exactement à la place du satellite actions. Les actions partent en
`TimeInForce.DAY` sans `extended_hours` ; hors séance elles ne peuvent pas se remplir.
La crypto (`GTC`, 24/7) passe toujours. Aucun contrôle d'horaires n'existait, et un
ordre qui ne peut pas se remplir ne laissait AUCUNE trace lisible.

Ces tests vérifient le CÂBLAGE, pas la logique du calendrier (couverte par
`test_market_calendar.py`) — c'est la distinction qui manquait la première fois :
une règle correcte mais non branchée ne protège rien.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _run_live():
    spec = importlib.util.spec_from_file_location(
        "run_live_seance", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Reponse:
    """Réponse courtier minimale. Depuis le 26/08 `run_live` LIT le statut renvoyé : une
    doublure qui renvoie None est classée « issue inconnue » et l'ordre n'est pas
    compté —
    ce qui est le comportement voulu, mais rendrait ces tests trompeurs."""

    def __init__(self, status):
        self.status = status


class CourtierFactice:
    def __init__(self):
        self.ordres = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))
        return _Reponse("accepted")     # un courtier RÉPOND toujours quelque chose

    def close_position(self, sym):
        self.ordres.append(("close", sym, None))
        return True                     # AlpacaBroker.close_position renvoie un booléen


def _cible(sym, poids, classe="equity"):
    return {"symbol": sym, "broker_symbol": sym, "weight_pct": poids,
            "capital": "alpaca", "asset_class": classe, "tradeable": True}


@pytest.fixture
def rl():
    return _run_live()


def _brokers(b):
    return [("Alpaca", b, 100_000.0, {})]


def test_action_reportee_quand_le_marche_est_ferme(rl, monkeypatch, capsys):
    """LE cas observé : hors séance, l'ordre action n'est PAS envoyé — et c'est dit."""
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    monkeypatch.setattr(rl, "_reconcile", rl._reconcile)      # module réellement chargé
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity":
                        asset_class == "crypto")
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 0 and b.ordres == []
    sortie = capsys.readouterr().out
    assert "REPORTÉ" in sortie
    assert "REPORTÉ(S) hors séance" in sortie      # le récapitulatif chiffré


def test_crypto_passe_meme_marche_actions_ferme(rl, monkeypatch):
    """La crypto se traite 24/7 : elle ne doit JAMAIS être reportée."""
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity":
                        asset_class == "crypto")
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("BTC/USD", 0.50, "crypto")],
                               _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


def test_action_passe_quand_le_marche_est_ouvert(rl, monkeypatch):
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity": True)
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


def test_echappatoire_explicite(rl, monkeypatch):
    """`QUANT_IGNORE_SESSION=1` envoie quand même — en connaissance de cause."""
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    import packages.execution.market_calendar as mc
    monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity": False)
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)], _brokers(b), 1.0, None, dry=False)
    assert sent == 1 and b.ordres


# --- issue de l'ordre : un rejet ne compte pas ------------------------------

class CourtierQuiRefuse(CourtierFactice):
    """Le courtier ACCEPTE l'appel (aucune exception) puis REJETTE l'ordre.

    C'est le cas réel qui était invisible : `sent += 1` dès l'absence d'exception
    comptait comme réussi un ordre que le courtier venait de refuser.
    """

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))
        return _Reponse("rejected")


def test_un_rejet_courtier_ne_compte_pas_comme_envoye(rl, monkeypatch, capsys):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    b = CourtierQuiRefuse()
    sent, opened, _ = rl._reconcile([_cible("AAA", 0.10)], _brokers(b), 1.0, None,
                                    dry=False)
    assert b.ordres, "l'ordre a bien été tenté"
    assert sent == 0, "un ordre REJETÉ ne doit pas être compté comme envoyé"
    assert opened == [], "un rejet ne doit pas être journalisé comme une ouverture"
    sortie = capsys.readouterr().out
    assert "REJETÉ" in sortie and "REFUSÉ(S) par le courtier" in sortie


def test_une_reponse_inexploitable_ne_compte_pas(rl, monkeypatch):
    """Un courtier qui ne répond rien ne prouve pas que l'ordre est parti."""
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")

    class Muet(CourtierFactice):
        def submit_notional(self, sym, side, montant):
            self.ordres.append(("notional", sym, montant))
            return None

    sent, _, _ = rl._reconcile([_cible("AAA", 0.10)], _brokers(Muet()), 1.0, None,
                               dry=False)
    assert sent == 0
