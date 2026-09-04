"""Le fill d'ouverture vient des ACHATS EXÉCUTÉS, pas de la position du courtier.

Ce que ces tests verrouillent (cause mesurée le 03/09 : 30 symboles sur 87 couverts
à moitié ou moins dans le journal) : `_journal_opens` lisait la POSITION juste après
l'envoi de l'ordre. Si elle n'était pas encore rafraîchie, l'achat n'était jamais
journalisé ; et
quand elle l'était, elle portait la quantité TOTALE et le prix de revient MOYEN — pas
l'achat du jour. Les fills, eux, existent après coup et portent l'opération réelle.
"""

from __future__ import annotations

import importlib

from packages.execution.live_journal import agreger_achats

run_live = importlib.import_module("scripts.run_live")


class _Courtier:
    def __init__(self, ordres, positions):
        self._o, self._p = ordres, positions

    def orders(self, limit: int = 100):
        return self._o[:limit]

    def positions_detailed(self):
        return self._p


class _CourtierMuet(_Courtier):
    def orders(self, limit: int = 100):
        raise RuntimeError("API indisponible")


def test_agregation_vwap_du_jour():
    """Deux achats du même actif sous deux conventions → une clé, un VWAP pondéré."""
    j, veille = "2026-09-03T", "2026-09-02T"
    ordres = [
        {"symbol": "AVAX/USDC", "side": "buy", "qty": 100, "price": 20.0,
         "date": j + "10:00:00Z"},
        {"symbol": "AVAXUSD", "side": "buy", "qty": 50, "price": 26.0,
         "date": j + "14:00:00Z"},
        {"symbol": "AVAX/USDC", "side": "sell", "qty": 30, "price": 25.0,
         "date": j + "15:00:00Z"},
        {"symbol": "AVAX/USDC", "side": "buy", "qty": 999, "price": 30.0,
         "date": veille + "10:00:00Z"},
    ]
    out = agreger_achats(ordres, "2026-09-03")
    assert set(out) == {"AVAX"}
    assert out["AVAX"]["qty"] == 150.0
    assert abs(out["AVAX"]["avg_price"] - 22.0) < 1e-9      # (100×20 + 50×26) / 150


def test_fills_prioritaires_sur_la_position():
    """La position dit 1 000 @ 12 $ (cumul) ; l'achat du jour est 40 @ 15 $."""
    br = _Courtier(
        [{"symbol": "PATH", "side": "buy", "qty": 40, "price": 15.0,
          "date": "2026-09-03T16:00:00Z"}],
        [{"symbol": "PATH", "qty": 1000.0, "avg_price": 12.0}],
    )
    brokers = (("Alpaca", br), ("Bitmart", None))
    fills = run_live._fills_achats(brokers, "2026-09-03")
    repli = run_live._positions_repli(brokers)
    assert fills[("Alpaca", "PATH")] == {"qty": 40.0, "avg_price": 15.0}
    assert repli[("Alpaca", "PATH")]["qty"] == 1000.0   # le repli suit, il ne prime pas


def test_fill_trouve_meme_sans_position_rafraichie():
    """Le cas qui perdait l'achat : ordre exécuté, position encore vide."""
    br = _Courtier(
        [{"symbol": "SOL/USDC", "side": "buy", "qty": 3, "price": 200.0,
          "date": "2026-09-03T09:00:00Z"}],
        [],
    )
    fills = run_live._fills_achats((("Bitmart", br),), "2026-09-03")
    assert fills == {("Bitmart", "SOL"): {"qty": 3.0, "avg_price": 200.0}}


def test_courtier_muet_ne_supprime_pas_l_autre():
    """Un courtier en panne ne doit pas faire disparaître les fills du second."""
    muet = _CourtierMuet([], [])
    ok = _Courtier(
        [{"symbol": "QQQ", "side": "buy", "qty": 2, "price": 500.0,
          "date": "2026-09-03T18:00:00Z"}],
        [],
    )
    fills = run_live._fills_achats((("Bitmart", muet), ("Alpaca", ok)), "2026-09-03")
    assert fills == {("Alpaca", "QQQ"): {"qty": 2.0, "avg_price": 500.0}}


def test_repli_canonique_comme_les_fills():
    """Les deux sources doivent partager la MÊME clé, sinon le repli est introuvable."""
    br = _Courtier([], [{"symbol": "AVAX/USDC", "qty": 7.0, "avg_price": 21.0}])
    repli = run_live._positions_repli((("Bitmart", br),))
    fills = run_live._fills_achats(
        (("Bitmart", _Courtier(
            [{"symbol": "AVAXUSD", "side": "buy", "qty": 7, "price": 21.0,
              "date": "2026-09-03T10:00:00Z"}], [])),),
        "2026-09-03")
    assert set(repli) == set(fills) == {("Bitmart", "AVAX")}


def test_rien_de_lisible_ne_produit_aucun_fill():
    """Aucun achat, aucune position → dict vide. On n'invente pas un lot."""
    br = _Courtier([{"symbol": "QQQ", "side": "sell", "qty": 1, "price": 500.0,
                     "date": "2026-09-03T18:00:00Z"}], [])
    assert run_live._fills_achats((("Alpaca", br),), "2026-09-03") == {}
    assert run_live._positions_repli((("Alpaca", br),)) == {}
