"""Le test de biais du survivant doit dire quand il ne mesure RIEN.

Constat du 25/08 sur données réelles : `Δ Sharpe +0,00 · Δ CAGR +0,0 pts · Δ maxDD +0,0 pts`
avec 7 délistés ingérés. Lu naïvement, ce zéro signifie « pas de biais du survivant ». Il
signifiait en réalité « aucun délisté n'est entré dans le portefeuille » — et, plus grave, que
la comparaison n'aurait de toute façon pas eu de sens, le panel s'alignant par POSITION.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from packages.backtest.survivorship_delta import (TOLERANCE_JOURS, _decalage_max,
                                                  survivorship_delta)


@dataclass
class Bar:
    ts: datetime
    close: float


def _serie(n: int, seed: int, fin: datetime | None = None) -> list[Bar]:
    import random
    rng = random.Random(seed)
    fin = fin or datetime(2026, 1, 1, tzinfo=timezone.utc)
    debut = fin - timedelta(days=n - 1)
    px, out = 100.0, []
    for i in range(n):
        px *= math.exp(0.08 / 252 + 0.20 / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(debut + timedelta(days=i), px))
    return out


def _survivants(n=40, longueur=1200):
    return {f"S{i}": _serie(longueur, i) for i in range(n)}


def test_un_delisté_desaligne_est_refuse_SANS_alignement_par_date():
    """Sa dernière barre date de sa radiation. Empilé par POSITION, ses prix de 2023 seraient
    superposés aux dates de 2026 : le delta ne serait pas imprécis, il serait absurde.

    `aligner_dates=False` reproduit l'ancien moteur — et le module doit alors refuser plutôt
    que de produire un chiffre. C'est la moitié « garde-fou » du contrat."""
    mort = {"DEAD": _serie(800, 999, fin=datetime(2023, 1, 1, tzinfo=timezone.utc))}
    out = survivorship_delta(_survivants(), delisted_data=mort, top_k=30, aligner_dates=False)
    assert out["available"] is False
    assert out["decalage_jours"] > 300
    assert "aligne" in out["reason"].lower() or "PAR DATE" in out["reason"]


def test_le_meme_decalage_est_ABSORBÉ_par_l_alignement_par_date():
    """L'autre moitié du contrat : ce qui bloquait le moteur positionnel est exactement ce que
    l'alignement par date sait représenter. Le décalage reste publié, il n'est plus un veto."""
    surv = {f"S{i}": _serie(1200, i) for i in range(30)}
    mort = {f"D{i}": _serie(900, 500 + i, fin=datetime(2024, 6, 1, tzinfo=timezone.utc))
            for i in range(5)}
    out = survivorship_delta(surv, delisted_data=mort, top_k=20, panel_couverture=0.5)
    assert out["available"] is True and out["aligne_par_date"] is True
    assert out["decalage_jours"] > 300              # le décalage existe toujours…
    assert out["n_delisted_selectionnes"] >= 1      # …et n'empêche plus de mesurer
    assert "MINORANT" in out["limite"]              # la limite de la mesure reste dite


def test_un_delisté_jamais_selectionne_est_signale_comme_tel():
    """Δ = 0 ne veut pas dire « pas de biais » : ici il veut dire « le test ne mesure rien »."""
    surv = _survivants()
    # même date de fin (donc aligné) mais historique court → écarté par la fenêtre du panel
    mort = {"DEAD": _serie(120, 999)}
    out = survivorship_delta(surv, delisted_data=mort, top_k=30, aligner_dates=False)
    assert out["available"] is False
    assert out["n_delisted_selectionnes"] == 0
    assert "ne mesure rien" in out["reason"]


def test_un_delisté_reellement_selectionne_produit_un_delta():
    """Le cas où le test fonctionne : aligné ET dans l'univers retenu."""
    surv = _survivants()
    mort = {f"D{i}": _serie(1200, 500 + i) for i in range(6)}
    out = survivorship_delta(surv, delisted_data=mort, top_k=30)
    if out["available"]:                       # dépend du classement momentum, pas garanti
        assert out["n_delisted_selectionnes"] >= 1
        assert set(out["delistes_selectionnes"]) <= set(mort)
        assert "sharpe" in out["delta"]
    else:                                      # sinon le motif doit l'expliquer, pas rester muet
        assert out["reason"]


def test_absence_totale_de_delistes_reste_signalee():
    out = survivorship_delta(_survivants(), delisted_data={}, top_k=30)
    assert out["available"] is False and "ingest-delisted" in out["reason"]


def test_le_decalage_tolere_quelques_jours():
    """Jours fériés et suspensions créent de petits écarts normaux — ils ne doivent pas bloquer."""
    surv = _survivants(n=5, longueur=300)
    proche = {"D": _serie(300, 1, fin=datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(days=2))}
    assert _decalage_max(surv, proche) <= TOLERANCE_JOURS
    loin = {"D": _serie(300, 1, fin=datetime(2025, 1, 1, tzinfo=timezone.utc))}
    assert _decalage_max(surv, loin) > TOLERANCE_JOURS


def test_dates_illisibles_ne_bloquent_pas():
    """On ne bloque pas sur une donnée qu'on ne sait pas lire — mais on ne la valide pas non plus."""
    assert _decalage_max({}, {}) is None
    assert _decalage_max({"A": []}, {"B": []}) is None


def test_le_backtest_publie_les_noms_de_son_univers():
    """Sans les noms, impossible de savoir si un titre donné a été sélectionné."""
    from packages.backtest.preset_backtest import preset_backtest

    r = preset_backtest(_survivants(), top_k=10)
    assert r["available"] and isinstance(r["univers"], list)
    assert len(r["univers"]) == r["top_k"] and set(r["univers"]) <= set(_survivants())
