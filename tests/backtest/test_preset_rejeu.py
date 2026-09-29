"""QML-001 — le backtest doit mesurer la règle de PRODUCTION, pas une cousine.

Trois implémentations du « preset » coexistaient : `preset_backtest` (les métriques),
`preset_equity_daily`/`preset_ledger` (la courbe du tableau de bord) et
`preset_latest_weights_explique` (ce que `make live` envoie). Elles différaient par
l'univers, les portes, le lag, la fréquence, la bande, le blackout et le plafond : aucun
chiffre publié ne décrivait le portefeuille tradé.

Le rejeu appelle LA fonction de production, à chaque date, sur les seules données connues
à cette date. Ces tests verrouillent les trois propriétés qui le rendent digne de ce nom :
équivalence avec la production, causalité, exécution APRÈS la décision.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar

DEBUT = datetime(2018, 1, 2, tzinfo=UTC)


def _jours_ouvres(n: int) -> list[datetime]:
    out, d = [], DEBUT
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _panel(n_titres: int = 24, n_jours: int = 420, graine: int = 3) -> dict:
    rng = np.random.default_rng(graine)
    jours = _jours_ouvres(n_jours)
    data = {}
    for k in range(n_titres):
        px = (20 + 15 * k) * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n_jours)))
        data[f"T{k:02d}"] = [Bar(f"T{k:02d}", "1d", j, p, p, p, p, 1e6)
                             for j, p in zip(jours, px, strict=True)]
    return data


def _jour(d: datetime) -> str:
    return d.date().isoformat()


# ---------------------------------------------------------------------------------------
# 1. ÉQUIVALENCE — le cœur du correctif.
# ---------------------------------------------------------------------------------------

def test_les_cibles_du_rejeu_sont_celles_de_la_production():
    """À chaque date de décision, la cible rejouée est EXACTEMENT ce que
    `preset_latest_weights_explique` rendait ce jour-là, sur les données de ce jour-là."""
    from packages.backtest.preset_rejeu import decisions, tronquer
    from packages.backtest.preset_weights import preset_latest_weights_explique

    data = _panel()
    params = {"dd_target": 0.25, "band": 0.03, "top_k": 12, "min_weight": 0.025}
    jours = [_jour(b.ts) for b in data["T00"]][300::40]
    rendu = decisions(data, jours, params)
    assert [d for d, _ in rendu] == jours
    for jour, cible in rendu:
        attendu, _ = preset_latest_weights_explique(tronquer(data, jour), {}, **params)
        assert cible == attendu, jour


def test_tronquer_ne_garde_que_le_passe_connu():
    from packages.backtest.preset_rejeu import tronquer

    data = _panel(n_titres=5, n_jours=50)
    jour = _jour(data["T00"][20].ts)
    t = tronquer(data, jour)
    assert all(_jour(b.ts) <= jour for barres in t.values() for b in barres)
    assert all(len(barres) == 21 for barres in t.values())


# ---------------------------------------------------------------------------------------
# 2. CAUSALITÉ — ajouter l'avenir ne réécrit pas le passé.
# ---------------------------------------------------------------------------------------

def test_ajouter_des_donnees_futures_ne_change_pas_le_passe():
    from packages.backtest.preset_rejeu import rejouer, tronquer

    data = _panel()
    jours = [_jour(b.ts) for b in data["T00"]]
    coupe = jours[380]
    complet = rejouer(data, pas=20, debut=jours[280])
    tronque = rejouer(tronquer(data, coupe), pas=20, debut=jours[280])
    assert complet["available"] and tronque["available"]
    communs = {d: v for d, v in zip(complet["dates"], complet["equity"], strict=True)}
    for d, v in zip(tronque["dates"], tronque["equity"], strict=True):
        assert communs[d] == pytest.approx(v, rel=1e-12), d


# ---------------------------------------------------------------------------------------
# 3. EXÉCUTION — au cours d'APRÈS la décision, jamais au cours qui l'a déclenchée.
# ---------------------------------------------------------------------------------------

def _prix(serie: dict[str, list[float]], jours: list[str]) -> dict:
    return {s: dict(zip(jours, v, strict=True)) for s, v in serie.items()}


def test_le_saut_du_jour_de_decision_n_est_pas_capture():
    """Une cible décidée au close J s'exécute au close J+1. Un saut de +50 % entre J−1 et J
    est l'information qui a pu motiver la décision : il n'est pas exécutable, il ne doit
    pas apparaître dans l'equity."""
    from packages.backtest.preset_rejeu import simuler

    jours = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"]
    px = _prix({"A": [100.0, 150.0, 150.0, 150.0]}, jours)
    res = simuler([("2020-01-02", {"A": 0.10})], px, jours, capital=100_000.0,
                  classes={"A": "equity"}, frais=False)
    # acheté au close du 03/01 (150) : aucun gain, le saut du 02/01 n'appartient à personne
    assert res["dates"][0] == "2020-01-03"
    assert res["equity"][-1] == pytest.approx(100_000.0)


def test_l_equity_suit_les_cours_apres_l_execution():
    from packages.backtest.preset_rejeu import simuler

    jours = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"]
    px = _prix({"A": [100.0, 100.0, 100.0, 120.0]}, jours)
    res = simuler([("2020-01-01", {"A": 0.10}), ("2020-01-03", {"A": 0.10})], px, jours,
                  capital=100_000.0, classes={"A": "equity"}, frais=False)
    # 10 000 $ achetés à 100, valorisés 120 au 06/01 → +2 000 $. Le rééquilibrage du 06/01
    # revend 1 800 $ vers la cible (10 % de 102 000) : sans frais, l'equity n'en bouge pas.
    assert res["equity"][-1] == pytest.approx(102_000.0)


# ---------------------------------------------------------------------------------------
# 4. LES MÊMES RÈGLES D'ORDRE QUE `run_live`.
# ---------------------------------------------------------------------------------------

def test_la_bande_et_le_plancher_sont_ceux_de_la_production():
    """Écart sous la bande (0,5 % du capital) → aucun ordre ; cible sous le plancher de
    ligne (1 000 $) → rien n'est ouvert. Mêmes seuils que `run_live`, via `decider`."""
    from packages.backtest.preset_rejeu import simuler

    jours = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"]
    px = _prix({"A": [100.0] * 4, "B": [50.0] * 4}, jours)
    res = simuler([("2020-01-01", {"A": 0.10, "B": 0.005}),
                   ("2020-01-02", {"A": 0.102})], px, jours,
                  capital=100_000.0, classes={"A": "equity", "B": "equity"}, frais=False)
    assert res["n_ordres"] == 1           # A ouvert ; B sous plancher ; +0,2 % sous la bande


def test_le_portail_de_risque_plafonne_comme_en_production():
    """Une cible de 50 % sur un titre isolé est réduite par `order_gate` (ordre ≤ 15 %)."""
    from packages.backtest.preset_rejeu import simuler

    jours = ["2020-01-01", "2020-01-02", "2020-01-03"]
    px = _prix({"A": [100.0] * 3}, jours)
    res = simuler([("2020-01-01", {"A": 0.50})], px, jours, capital=100_000.0,
                  classes={"A": "equity"}, frais=False)
    assert res["poids_final"]["A"] == pytest.approx(0.15)


def test_les_frais_sont_deduits():
    from packages.backtest.preset_rejeu import simuler

    jours = ["2020-01-01", "2020-01-02", "2020-01-03"]
    px = _prix({"A": [100.0] * 3}, jours)
    res = simuler([("2020-01-01", {"A": 0.10})], px, jours, capital=100_000.0,
                  classes={"A": "equity"}, frais=True)
    assert res["frais"] > 0
    assert res["equity"][-1] == pytest.approx(100_000.0 - res["frais"])


# ---------------------------------------------------------------------------------------
# 5. LES CHIFFRES PUBLIÉS DISENT CE QU'ILS NE MESURENT PAS.
# ---------------------------------------------------------------------------------------

def test_les_sorties_publiees_declarent_ne_pas_mesurer_la_production():
    """Tant que tableau de bord et métriques ne sortent pas du rejeu, ils doivent le DIRE :
    un chiffre qui décrit une autre règle que celle tradée ne doit pas passer pour elle."""
    from packages.backtest.preset_backtest import (
        preset_backtest,
        preset_equity_daily,
        preset_ledger,
    )

    data = _panel(n_titres=30, n_jours=600)
    for sortie in (preset_backtest(data), preset_equity_daily(data), preset_ledger(data)):
        assert sortie["available"]
        assert sortie["mesure_la_production"] is False
        assert "preset-replay" in sortie["mesure_production"]
