"""QML-024 — les garde-fous comparent des equity de MÊME périmètre.

L'historique `equity_history` avait deux écrivains : le snapshot ({alpaca, binance} — dès
qu'UN courtier répondait, testnet compris, donc fausse monnaie) et `run_live`
({alpaca, bitmart}). Le kill-switch drawdown et le disjoncteur sommaient toutes les clés :
un pic gonflé par un solde testnet, ou un point amputé d'un courtier muet, suffisait à
déclencher (ou masquer) un garde-fou.
"""

import pytest


def _hist():
    return [
        {"date": "2026-09-20", "alpaca": 100_000.0},
        {"date": "2026-09-21", "alpaca": 101_000.0, "binance": 60_000.0},   # testnet, faux pic
        {"date": "2026-09-22", "alpaca": 100_500.0},
    ]


def test_courbe_comparable_ne_somme_que_le_perimetre_demande():
    from packages.execution.equity_history import courbe_comparable
    assert courbe_comparable(_hist(), {"alpaca"}) == [100_000.0, 101_000.0, 100_500.0]
    # un point qui n'a pas TOUTES les clés du périmètre est écarté, jamais compté pour zéro
    assert courbe_comparable(_hist(), {"alpaca", "binance"}) == [161_000.0]


def test_le_faux_pic_testnet_ne_declenche_plus_le_kill_switch(monkeypatch):
    from packages.execution import equity_history, live_guards
    monkeypatch.setattr(equity_history, "_load", _hist)
    avant = live_guards.dd_kill_switch(100_400.0, None, None)                  # ancien appel
    apres = live_guards.dd_kill_switch(100_400.0, None, None, cles={"alpaca"})
    assert avant == 0.0          # 100 400 / 161 000 − 1 = −37,6 % : faux déclenchement
    assert apres == 1.0          # même périmètre : −0,6 %, rien à couper


def test_le_disjoncteur_compare_la_veille_au_meme_perimetre():
    from packages.execution.coupe_circuit import variation_du_jour
    h = [{"date": "2000-01-01", "alpaca": 100_000.0, "binance": 60_000.0}]
    assert variation_du_jour(99_000.0, h) == pytest.approx(-61_000.0)          # ancien
    assert variation_du_jour(99_000.0, h, cles={"alpaca"}) == pytest.approx(-1_000.0)


def test_record_ignore_un_releve_sans_alpaca(tmp_path, monkeypatch):
    from packages.execution import equity_history
    monkeypatch.setattr(equity_history, "_F", tmp_path / "eq.json")
    equity_history.record({"alpaca": 0.0, "binance": 5_000.0}, today="2026-09-25")
    assert equity_history._load() == []            # un relevé amputé n'entre pas
    equity_history.record({"alpaca": 100_000.0}, today="2026-09-25")
    assert equity_history._load() == [{"date": "2026-09-25", "alpaca": 100_000.0}]
