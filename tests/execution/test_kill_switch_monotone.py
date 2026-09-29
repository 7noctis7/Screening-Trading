"""QML-007 — un garde-fou BLOQUE ou PLAFONNE les achats ; il ne vend jamais.

Avant : `reduce = 0` (drawdown réel ≤ −15 %, disjoncteur armé, veto TV) GELAIT le compte sans
rien vendre, tandis que `0 < reduce < 1` (simple alerte TV « reduce ») multipliait les cibles
et VENDAIT. Plus le signal était grave, moins on se désengageait — et le message affichait
« exposition forcée à 0 » pendant que rien n'était vendu.

Décision (utilisateur, 25/09) : GEL PARTOUT. Un garde-fou ne crée aucune vente ; il empêche
d'acheter au-delà de `cible × reduce`. Les ventes DÉCIDÉES PAR LA STRATÉGIE (cible sous le
détenu) continuent de partir : elles réduisent le risque, les bloquer l'augmenterait.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "1.0")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "1.0")


def _rl():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Rep:
    status = "accepted"


class _Courtier:
    def __init__(self):
        self.ordres = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append((sym, side.name, round(montant, 2)))
        return _Rep()

    def close_position(self, sym):
        self.ordres.append((sym, "CLOSE", None))
        return True


def _cible(s, w):
    return {"symbol": s, "broker_symbol": s, "weight_pct": w, "capital": "alpaca",
            "asset_class": "equity", "tradeable": True}


@pytest.mark.parametrize("reduce", [1.0, 0.5, 0.01, 0.0])
def test_un_garde_fou_ne_vend_jamais(reduce):
    """Détenu 5 000 $ sous une cible de 10 000 $ : aucune vente, quel que soit `reduce`."""
    rl = _rl()
    tgt, _ = rl._broker_targets([_cible("AAA", 0.10)], "Alpaca", 100_000.0, reduce,
                                {"AAA": 5_000.0})
    assert tgt["AAA"]["val"] >= 5_000.0 - 1e-9


def test_la_cible_decroit_avec_la_gravite():
    rl = _rl()
    vals = [rl._broker_targets([_cible("AAA", 0.10)], "Alpaca", 100_000.0, r, {})[0]["AAA"]["val"]
            for r in (1.0, 0.5, 0.01, 0.0)]
    assert vals == sorted(vals, reverse=True) and vals[-1] == 0.0


def test_une_vente_de_strategie_passe_meme_sous_kill_switch():
    """Détenu 20 000 $ pour une cible de 10 000 $ : la stratégie allège, garde-fou ou non."""
    rl = _rl()
    for r in (1.0, 0.0):
        tgt, _ = rl._broker_targets([_cible("AAA", 0.10)], "Alpaca", 100_000.0, r,
                                    {"AAA": 20_000.0})
        assert tgt["AAA"]["val"] == pytest.approx(10_000.0)


def test_reduce_nul_n_achete_rien_mais_laisse_sortir():
    rl = _rl()
    b = _Courtier()
    rl._reconcile([_cible("NEW", 0.10), _cible("OLD", 0.05)],
                  [("Alpaca", b, 100_000.0, {"OLD": 20_000.0, "OUT": 3_000.0})],
                  0.0, None, dry=False)
    envoyes = {o[0]: o[1] for o in b.ordres}
    assert "NEW" not in envoyes                    # aucun achat sous kill-switch
    assert envoyes.get("OLD") == "SHORT"           # allègement de stratégie : 20 000 → 5 000
    assert envoyes.get("OUT") == "CLOSE"           # hors-cible : soldé
