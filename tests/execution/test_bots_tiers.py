"""Les bots TIERS (« XIII indic ») : des benchmarks, jamais pilotés ni additionnés.

Ce que ces tests épinglent (cf. `packages/execution/bots_tiers`) :
  1. LECTURE SEULE — la lecture n'appelle aucune méthode d'ordre ; `run_live` ne
     connaît pas le module ;
  2. JAMAIS DANS LE TOTAL — `/api/portefeuille` les range sous `bots`, à part ;
  3. UN COMPTE SÉPARÉ OU RIEN — les clés du robot sont refusées, motif nommé ;
  4. un bot plus récent que le portefeuille démarre AU MILIEU du graphe, à la valeur
     du portefeuille ce jour-là, sans être prolongé vers l'arrière ;
  5. il apparaît sur le tableau de bord, dans « Mes comptes réels face aux indices ».
"""

import ast
import pathlib

import pytest

from packages.execution import bots_tiers
from packages.execution.bots_tiers import BOTS, lire, lire_tous

RACINE = pathlib.Path(__file__).resolve().parents[2]
XIII = BOTS[0]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "cle-robot")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret-robot")
    monkeypatch.setenv("ALPACA_XIII_API_KEY", "cle-xiii")
    monkeypatch.setenv("ALPACA_XIII_API_SECRET", "secret-xiii")


class CompteLectureSeule:
    """Lève sur TOUTE méthode d'ordre : un appel suffirait à faire échouer le test."""

    def __init__(self, bot=None):
        self.bot = bot

    def equity(self):
        return 25_000.0

    def positions_detailed(self):
        return [{"symbol": "AAPL", "qty": 10, "price": 200.0,
                 "market_value": 2_000.0, "pnl": 150.0, "pnl_pct": 0.08}]

    def portfolio_history(self):
        return [{"t": "2026-09-01", "v": 24_000.0}, {"t": "2026-09-30", "v": 25_000.0}]

    def __getattr__(self, nom):
        raise AssertionError(f"méthode non autorisée sur un bot tiers : {nom}")


def test_le_bot_xiii_est_declare_avec_ses_propres_cles():
    assert XIII.nom == "XIII indic"
    assert XIII.env_cle == "ALPACA_XIII_API_KEY"
    assert XIII.env_secret == "ALPACA_XIII_API_SECRET"


def test_lecture_seule_equity_positions_historique():
    d = lire(XIII, fabrique=CompteLectureSeule)
    assert d["ok"] and d["equity"] == 25_000.0 and d["error"] is None
    assert d["positions"][0]["symbol"] == "AAPL" and len(d["history"]) == 2


def test_sans_cles_le_bot_est_hors_perimetre(monkeypatch):
    monkeypatch.delenv("ALPACA_XIII_API_KEY")
    assert lire_tous(fabrique=CompteLectureSeule) == []
    d = lire(XIII, fabrique=CompteLectureSeule)
    assert not d["ok"] and "ALPACA_XIII_API_KEY" in d["error"]


def test_les_cles_du_robot_sont_refusees(monkeypatch):
    """Même compte = pas un benchmark, et run_live y solderait les lignes de XIII."""
    monkeypatch.setenv("ALPACA_XIII_API_KEY", "cle-robot")
    appels = []
    d = lire(XIII, fabrique=lambda b: appels.append(b) or CompteLectureSeule())
    assert not d["ok"] and "compte séparé" in d["error"] and appels == []


def test_un_compte_muet_est_nomme_pas_mis_a_zero():
    def panne(_):
        raise ConnectionError("timeout")
    d = lire(XIII, fabrique=panne)
    assert d["ok"] is False and d["equity"] is None and "timeout" in d["error"]


def test_le_module_n_importe_rien_qui_passe_des_ordres():
    arbre = ast.parse(pathlib.Path(bots_tiers.__file__).read_text(encoding="utf-8"))
    importes = {n.module for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom)}
    assert importes <= {"__future__", "collections.abc", "dataclasses",
                        "packages.execution.alpaca_broker"}, importes
    run_live = (RACINE / "scripts" / "run_live.py").read_text(encoding="utf-8")
    assert "bots_tiers" not in run_live, "le chemin d'ordres ignore les bots tiers"


def test_portefeuille_range_le_bot_A_PART_du_total():
    from apps.api.portefeuille import agreger, bloc_bot
    robot = {"nom": "Alpaca", "configure": True, "ok": True, "equity": 100_000.0,
             "positions": [{"symbol": "QQQ", "market_value": 50_000.0, "pnl": 10.0}]}
    total = agreger([robot])
    bot = bloc_bot(lire(XIII, fabrique=CompteLectureSeule))
    assert total["equity_total"] == 100_000.0 and total["n_positions"] == 1
    assert bot["equity"] == 25_000.0 and bot["latent"] == 150.0
    assert [p["symbole"] for p in bot["positions"]] == ["AAPL"]


def test_bloc_d_un_bot_muet_ne_publie_aucun_chiffre():
    from apps.api.portefeuille import bloc_bot
    b = bloc_bot({"cle": "xiii", "nom": "XIII indic", "ok": False, "error": "timeout",
                  "equity": 0.0, "positions": [{"symbol": "X", "market_value": 1.0}]})
    assert b["equity"] is None and b["positions"] == [] and b["motif"] == "timeout"


def test_un_bot_plus_recent_demarre_au_milieu_du_graphe():
    from packages.portfolio.comparaison_benchmark import (
        aligner,
        aligner_depuis_son_debut,
    )
    pf = [{"t": "2026-08-01", "v": 100_000.0}, {"t": "2026-09-01", "v": 110_000.0},
          {"t": "2026-09-30", "v": 121_000.0}]
    dates, vals = ["2026-09-01", "2026-09-30"], [20_000.0, 22_000.0]
    assert aligner(pf, dates, vals) == []                  # un indice serait écarté
    s = aligner_depuis_son_debut(pf, dates, vals)
    assert s == [{"t": "2026-09-01", "v": 110_000.0},
                 {"t": "2026-09-30", "v": 121_000.0}]


def test_le_tableau_de_bord_compare_le_bot_aux_comptes_et_aux_indices():
    from apps.api.snapshot import _account_compare
    alp = [{"t": "2026-09-01", "v": 100.0}, {"t": "2026-09-30", "v": 105.0}]
    xiii = [{"t": "2026-09-01", "v": 50.0}, {"t": "2026-09-30", "v": 55.0}]
    out = _account_compare(alp, [], [], [], [], [], bots={"XIII indic": xiii})
    assert {"Alpaca (réel)", "XIII indic"} <= set(out["series"])
    k = {r["name"]: r for r in out["kpis"]}
    assert k["XIII indic"]["return"] == pytest.approx(0.10)
    assert k["Alpaca (réel)"]["return"] == pytest.approx(0.05)    # pas d'addition


def test_la_courbe_de_mes_positions_ajoute_le_bot_et_sa_date(monkeypatch):
    from apps.api import performance
    monkeypatch.setattr(bots_tiers, "lire_tous", lambda *a, **k: [
        {"nom": "XIII indic", "ok": True, "history": [
            {"t": "2026-09-01", "v": 20_000.0}, {"t": "2026-09-30", "v": 22_000.0}]}])
    serie = [{"t": "2026-08-01", "v": 100_000.0}, {"t": "2026-09-01", "v": 110_000.0},
             {"t": "2026-09-30", "v": 121_000.0}]
    res = {"serie": serie, "benchmarks": {}, "performances": {}, "ecartees": []}
    performance._ajouter_bots(serie, res)
    assert res["bots_depuis"] == {"XIII indic": "2026-09-01"}
    assert res["performances"]["XIII indic"]["variation_pct"] == pytest.approx(0.10)
