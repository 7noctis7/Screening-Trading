"""QML-008 — l'IC transversal compare des titres À LA MÊME DATE.

`mesurer` indexait chaque série par sa POSITION : `bars[t]` d'un titre introduit en 2020 et
`bars[t]` d'un titre coté depuis 2015 sont deux dates distinctes, de même qu'une crypto
(7 j/7) et une action (5 j/7). La « coupe transversale » corrélait des scores et des
rendements de périodes différentes. Or c'est cette mesure qui autorise « Conviction ».
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.core.models import Bar

D0 = datetime(2018, 1, 1, tzinfo=UTC)
H = 21


def _panel(graine=0, n=20, jours=900):
    rng = np.random.default_rng(graine)
    out = {}
    for k in range(n):
        debut = 0 if k < 12 else int(rng.integers(50, 300))       # introductions décalées
        px = 50 * np.exp(np.cumsum(rng.normal(0, 0.015, jours - debut)))
        out[f"S{k:02d}"] = [Bar(f"S{k:02d}", "1d", D0 + timedelta(days=debut + i),
                                p, p, p, p, 1e6) for i, p in enumerate(px)]
    return out


class _Resultat:
    def __init__(self, s, score):
        self.symbol, self.score, self.passed = s, score, True


class _OracleDate:
    """Score = rendement FUTUR réel à H séances de grille, lu PAR DATE dans le panel complet.
    Si la mesure aligne bien les dates, l'IC vaut 1 à chaque date."""

    def __init__(self, complet, grille):
        self.px = {s: {b.ts.date().isoformat(): b.close for b in bars}
                   for s, bars in complet.items()}
        self.grille = grille

    def screen(self, panel, t=10**9, fundamentals=None, include_rejected=False):
        out = []
        for s, bars in panel.items():
            j = bars[-1].ts.date().isoformat()
            k = self.grille.index(j) if j in self.grille else None
            if k is None or k + H >= len(self.grille) or self.grille[k + H] not in self.px[s]:
                continue
            out.append(_Resultat(s, self.px[s][self.grille[k + H]] / self.px[s][j] - 1))
        return out


def test_un_oracle_par_date_donne_un_ic_de_un_malgre_les_introductions_decalees():
    from packages.backtest.preset_rejeu import calendrier
    from packages.research.screening_ic import mesurer
    p = _panel()
    res = mesurer(p, _OracleDate(p, calendrier(p)), horizon=H)
    assert res["available"] and res["axe"] == "dates"
    assert res["ic_moyen"] == pytest.approx(1.0, abs=1e-9)


def test_un_titre_qui_ne_cote_pas_ce_jour_n_est_pas_note():
    from packages.research.screening_ic import panel_a_la_date
    p = _panel()
    tardif = next(s for s, b in p.items() if b[0].ts > D0 + timedelta(days=60))
    avant = (p[tardif][0].ts - timedelta(days=5)).date().isoformat()
    assert tardif not in panel_a_la_date(p, avant)
