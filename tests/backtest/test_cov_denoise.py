"""M1 branché au preset : diagnostic TOUJOURS calculé, débruitage JAMAIS par défaut.

Données synthétiques (autorisé : valider la MATH, pas calibrer — cf. CLAUDE.md).
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from packages.backtest.cov_risk import (
    cov_annual,
    cov_diag_annual,
    cov_diagnostic,
    cov_for_step,
    summarize,
)
from packages.backtest.preset_backtest import preset_backtest, preset_latest_weights


@dataclass
class Bar:
    ts: datetime
    close: float


def _series(n, drift, vol, seed):
    import random
    rng = random.Random(seed)
    px, out, t0 = 100.0, [], datetime(2020, 1, 1, tzinfo=UTC)
    for i in range(n):
        px *= math.exp(drift / 252 + vol / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _data(n=400, k=12):
    return {f"S{i}": _series(n, 0.02 + 0.03 * (i % 6), 0.18 + 0.02 * (i % 4), seed=i)
            for i in range(k)}


def _un_facteur(n=400, k=12, idio=0.02):
    """Univers piloté par UN seul facteur commun → une seule direction exploitable."""
    rng = np.random.default_rng(7)
    f = rng.normal(0, 0.012, n)
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    out = {}
    for j in range(k):
        r = f + rng.normal(0, idio * 0.012, n)
        px = 100.0 * np.exp(np.cumsum(r))
        out[f"F{j}"] = [Bar(t0 + timedelta(days=i), float(px[i])) for i in range(n)]
    return out


# ---------------- non-régression : le défaut ne bouge PAS ----------------------
def test_defaut_identique_au_flag_explicitement_desactive():
    data = _data()
    a = preset_backtest(data, top_k=8)
    b = preset_backtest(data, top_k=8, cov_denoise=False)
    assert a["preset"]["sharpe"] == b["preset"]["sharpe"]
    assert a["curves"]["preset"] == b["curves"]["preset"]


def test_le_diagnostic_est_purement_observationnel(monkeypatch):
    """Même si le diagnostic RMT échoue, les chiffres publiés sont EXACTEMENT les mêmes."""
    data = _data()
    attendu = preset_backtest(data, top_k=8)["curves"]["preset"]

    def _ko(_win):
        raise RuntimeError("diagnostic indisponible")

    monkeypatch.setattr("packages.backtest.cov_risk.cov_diagnostic", _ko, raising=True)
    # cov_for_step ne doit pas laisser l'échec du diagnostic contaminer le résultat
    try:
        obtenu = preset_backtest(data, top_k=8)["curves"]["preset"]
    except RuntimeError:
        raise AssertionError("un diagnostic KO ne doit jamais casser le backtest") from None
    assert obtenu == attendu


# ---------------- le diagnostic répond à « signal ou bruit ? » -----------------
def test_diagnostic_publie_dans_la_sortie():
    r = preset_backtest(_data(), top_k=8)
    d = r["cov_diag"]
    assert d["available"] and d["denoised"] is False
    assert d["n_steps"] > 0 and 0.0 <= d["q_median"] <= 1.0
    assert d["k_signal_min"] <= d["k_signal_median"] <= d["k_signal_max"]
    assert d["n_degraded"] == 0                      # débruitage OFF ⇒ aucune dégradation
    assert "verdict" in d


def test_univers_a_un_facteur_est_signale_puis_degrade():
    data = _un_facteur()
    obs = preset_backtest(data, top_k=8)             # observation seule
    assert obs["cov_diag"]["k_signal_median"] < 2
    assert "UNE SEULE DIRECTION" in obs["cov_diag"]["verdict"]
    assert obs["cov_diag"]["n_degraded"] == 0        # on n'a rien changé

    actif = preset_backtest(data, top_k=8, cov_denoise=True)
    assert actif["cov_diag"]["degraded_pct"] > 0     # repli inverse-vol effectif
    assert actif["cov_diag"]["denoised"] is True


def test_debruitage_actif_change_le_resultat():
    """Sur des marches aléatoires INDÉPENDANTES, aucune direction commune n'est estimable :
    le débruitage replie donc sur l'inverse-vol à chaque pas — et la courbe change."""
    data = _data()
    base = preset_backtest(data, top_k=8)
    rmt = preset_backtest(data, top_k=8, cov_denoise=True)
    assert base.get("available") and rmt.get("available")
    assert base["curves"]["preset"] != rmt["curves"]["preset"]
    assert base["cov_diag"]["k_signal_median"] < 2
    assert rmt["cov_diag"]["degraded_pct"] == 100.0


# ---------------- la porte d'entrée unique ------------------------------------
def test_cov_for_step_off_renvoie_la_covariance_historique():
    win = np.random.default_rng(0).normal(0, 0.01, (8, 120))
    cov, diag, deg = cov_for_step(win, denoise=False)
    assert deg is False
    assert np.allclose(cov, cov_annual(win))
    assert diag["q"] == round(8 / 120, 4)


def test_repli_diagonal_supprime_toute_correlation_estimee():
    rng = np.random.default_rng(1)
    f = rng.normal(0, 0.012, 200)
    win = np.array([f + rng.normal(0, 2e-4, 200) for _ in range(8)])
    cov, diag, deg = cov_for_step(win, denoise=True)
    assert deg is True and diag["k_signal"] < 2
    hors_diag = cov[~np.eye(8, dtype=bool)]
    assert np.allclose(hors_diag, 0.0)               # aucune corrélation affirmée
    assert np.allclose(np.diag(cov), np.diag(cov_diag_annual(win)))


def test_diagnostic_ne_leve_jamais():
    assert cov_diagnostic(np.zeros((1, 5)))["available"] is False
    assert cov_diagnostic(np.zeros((4, 2)))["available"] is False
    assert summarize([], 0, False)["available"] is False


# ---------------- rail production ---------------------------------------------
def test_rail_prod_defaut_inchange_et_flag_operationnel():
    data = _data(n=500)
    base = preset_latest_weights(data, top_k=8)
    assert base == preset_latest_weights(data, top_k=8, cov_denoise=False)
    rmt = preset_latest_weights(data, top_k=8, cov_denoise=True)
    assert rmt and abs(sum(rmt.values())) <= 1.0 + 1e-9
    assert all(v > 0 for v in rmt.values())
