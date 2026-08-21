"""Déflation du DSR : le seuil doit être FALSIFIABLE, pas inatteignable par construction.

Régression majeure corrigée le 2026-08-20 : `sr_std` était calculé sur des Sharpe
ANNUALISÉS puis comparé à un Sharpe PAR PÉRIODE, ce qui plaçait le seuil à ~1,72 par
barre — un Sharpe annualisé de 27 en quotidien. Aucun candidat ne pouvait passer, et les
rejets n'étaient donc pas des verdicts de marché mais un artefact d'unités.
"""

import math

import pytest

from packages.portfolio.psr import deflated_sharpe_ratio
from packages.research.ledger import (append_record, deflation_diagnostic,
                                      deflation_params)


@pytest.fixture()
def ledger(tmp_path):
    return tmp_path / "hypotheses.jsonl"


def _ecrire(path, records):
    for r in records:
        append_record(r, path=path)


def test_sharpes_annualises_sans_periodicite_sont_EXCLUS(ledger):
    """Périodicité inconnue ⇒ exclu, jamais deviné : on replie sur l'H0 de Bailey."""
    _ecrire(ledger, [{"facteur": f"f{i}", "sharpe": s}
                     for i, s in enumerate([0.2, 1.9, 2.1, 2.44, 2.66])])
    n, sr_std = deflation_params(ledger)
    assert n == 5 and sr_std is None
    d = deflation_diagnostic(ledger)
    assert d["records_exclus_periodicite_inconnue"] == 5
    assert d["records_periodicite_connue"] == 0 and d["repli_bailey"] is True


def test_le_seuil_redevient_atteignable(ledger):
    """LA régression : avec l'ancien calcul, un excellent Sharpe donnait DSR ≈ 0."""
    _ecrire(ledger, [{"facteur": f"f{i}", "sharpe": s}
                     for i, s in enumerate([0.2, 1.9, 2.1, 2.44, 2.66])])
    n, sr_std = deflation_params(ledger, min_trials=15)
    sr_ann, n_obs, ppy = 1.5, 89, 12                      # mensuel, ~7 ans
    dsr = deflated_sharpe_ratio(sr_ann / math.sqrt(ppy), n_obs, n_trials=n, sr_std=sr_std)
    assert dsr > 0.5                                       # franchissable

    ancien = 0.972                                         # sr_std annualisé d'alors
    dsr_bug = deflated_sharpe_ratio(sr_ann / math.sqrt(ppy), n_obs, n_trials=n,
                                    sr_std=ancien)
    assert dsr_bug < 0.01                                  # …et ne l'était pas


def test_un_mauvais_sharpe_reste_rejete(ledger):
    """Le correctif ne doit pas rendre le gate permissif : 0,3 annualisé reste rejeté."""
    _ecrire(ledger, [{"facteur": f"f{i}", "sharpe": s} for i, s in enumerate([1.0, 2.0])])
    n, sr_std = deflation_params(ledger, min_trials=15)
    assert deflated_sharpe_ratio(0.30 / math.sqrt(12), 89, n_trials=n, sr_std=sr_std) < 0.5


def test_sharpe_period_explicite_est_utilise(ledger):
    _ecrire(ledger, [{"facteur": "a", "sharpe_period": 0.05},
                     {"facteur": "b", "sharpe_period": 0.15},
                     {"facteur": "c", "sharpe_period": 0.10}])
    n, sr_std = deflation_params(ledger)
    assert n == 3 and sr_std == pytest.approx(0.05, abs=1e-9)
    assert deflation_diagnostic(ledger)["records_periodicite_connue"] == 3


def test_conversion_par_periods_per_year(ledger):
    """sharpe annualisé + periods_per_year ⇒ converti, donc utilisable."""
    _ecrire(ledger, [{"facteur": "a", "sharpe": 3.464, "periods_per_year": 12},
                     {"facteur": "b", "sharpe": 1.732, "periods_per_year": 12}])
    n, sr_std = deflation_params(ledger)
    assert sr_std == pytest.approx(abs(3.464 - 1.732) / math.sqrt(12) / math.sqrt(2), rel=1e-3)
    assert deflation_diagnostic(ledger)["repli_bailey"] is False


def test_les_relances_du_meme_facteur_ne_gonflent_pas_N(ledger):
    _ecrire(ledger, [{"facteur": "breakout", "sharpe_period": 0.05} for _ in range(10)])
    assert deflation_params(ledger)[0] == 1               # 10 runs = 1 hypothèse
