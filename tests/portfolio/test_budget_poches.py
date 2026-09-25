"""QML-023 — la part crypto est un BUDGET DÉCLARÉ, pas un accident de renormalisation.

Les deux poches (actions + cœur QQQ, et crypto) étaient routées sur le seul capital Alpaca,
chacune dimensionnée comme si elle avait tout le compte, puis `run_live._broker_targets`
ramenait leur somme à 100 %. Mesuré : la cible « QQQ 50 % » tombait à 31-42 % et la crypto
montait à 25-56 %, selon les volatilités des deux poches. `QUANT_CRYPTO_PCT` était documenté
et lu nulle part. Décision (utilisateur, 25/09) : budget déclaré, 15 % par défaut.
"""

import pytest


def test_parts_declarees_respectees():
    from packages.portfolio.budget_poches import repartir
    actions = {"QQQ": 0.50, "AAA": 0.30, "BBB": 0.20}
    crypto = {"BTC/USD": 0.60, "ETH/USD": 0.40}               # poids DANS la poche
    a, c = repartir(actions, crypto, 0.15)
    assert a["QQQ"] == pytest.approx(0.50 * 0.85)
    assert sum(c.values()) == pytest.approx(0.15)
    assert sum(a.values()) + sum(c.values()) <= 1.0 + 1e-12   # plus de renormalisation cachée


def test_une_poche_crypto_sous_investie_garde_son_cash():
    """Une poche crypto à 40 % de gross (cible de vol) n'utilise que 40 % de son budget :
    le reste reste en cash, il ne remonte PAS dans les actions."""
    from packages.portfolio.budget_poches import repartir
    a, c = repartir({"QQQ": 1.0}, {"BTC/USD": 0.40}, 0.15)
    assert c["BTC/USD"] == pytest.approx(0.06) and a["QQQ"] == pytest.approx(0.85)


def test_sans_crypto_les_actions_gardent_tout_le_compte():
    from packages.portfolio.budget_poches import repartir
    a, c = repartir({"QQQ": 0.5, "AAA": 0.5}, {}, 0.15)
    assert a == {"QQQ": 0.5, "AAA": 0.5} and c == {}


def test_budget_nul_coupe_la_crypto():
    from packages.portfolio.budget_poches import repartir
    a, c = repartir({"QQQ": 0.5}, {"BTC/USD": 1.0}, 0.0)
    assert c == {} and a == {"QQQ": 0.5}


@pytest.mark.parametrize("brut,attendu", [(None, 0.15), ("", 0.15), ("0.25", 0.25),
                                          ("abc", 0.15), ("-1", 0.0), ("2", 1.0)])
def test_lecture_de_l_environnement(monkeypatch, brut, attendu):
    from packages.portfolio.budget_poches import part_crypto
    if brut is None:
        monkeypatch.delenv("QUANT_CRYPTO_PCT", raising=False)
    else:
        monkeypatch.setenv("QUANT_CRYPTO_PCT", brut)
    assert part_crypto() == pytest.approx(attendu)
