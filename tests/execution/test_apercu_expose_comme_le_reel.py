"""L'aperçu (`make live`, dry-run) juge chaque achat contre l'exposition APRÈS les ventes.

Constaté le 25/09 sur le compte paper : l'aperçu annonçait sept achats « REFUSÉ
[exposition_brute] — déjà atteint ». En dry-run, la boucle sortait AVANT de retrancher les
ventes de l'exposition simulée : le portail voyait le compte encore plein de ce qu'il allait
vendre. En réel, les ventes partent d'abord (`ordre_de_traitement`) et libèrent la place ;
l'aperçu annonçait donc des refus que le passage réel ne ferait pas.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "1.00")
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "1.00")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "1.00")


def _rl():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _cible(s, w):
    return {"symbol": s, "broker_symbol": s, "weight_pct": w, "capital": "alpaca",
            "asset_class": "equity", "tradeable": True}


def test_l_apercu_ne_refuse_pas_un_achat_finance_par_une_vente(capsys):
    rl = _rl()
    detenu = {"OLD": 100_000.0}                    # compte plein, OLD sort de la cible
    rl._reconcile([_cible("NEW", 0.50)], [("Alpaca", object(), 100_000.0, detenu)],
                  1.0, None, dry=True)
    sortie = capsys.readouterr().out
    assert "REFUSÉ" not in sortie
    assert "aperçu (acheter)" in sortie and "aperçu (solder)" in sortie
