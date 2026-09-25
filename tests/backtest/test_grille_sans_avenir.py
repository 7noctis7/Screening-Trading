"""QML-012 — la grille de dates d'un backtest ne dépend pas des cotations FUTURES.

`aligner_par_date` gardait les dates cotées par ≥ 80 % de TOUS les titres de l'échantillon.
Des introductions postérieures abaissaient donc la couverture de tout le passé : mesuré le
25/09, ajouter des IPO faisait démarrer le backtest en 2019 au lieu de 2015 (5 pas au lieu
de 48, Sharpe 1,20 au lieu de 1,71) — sur les MÊMES rendements passés. La couverture se
mesure désormais parmi les titres VIVANTS à la date (introduits et pas encore radiés).
"""

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar

D0 = datetime(2015, 1, 5, tzinfo=UTC)


def _jours(n):
    out, d = [], D0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _panel(n_titres=40, n=1400, ipo_frac=0.3, ipo_a=0.85, graine=1):
    rng = np.random.default_rng(graine)
    jours = _jours(n)
    data = {}
    for k in range(n_titres):
        cal = jours[int(n * ipo_a):] if k < int(n_titres * ipo_frac) else jours
        px = 50 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(cal))))
        data[f"S{k:02d}"] = [Bar(f"S{k:02d}", "1d", d, p, p, p, p, 1e6)
                             for d, p in zip(cal, px, strict=True)]
    return data


def _tronquer(data, fin):
    return {s: [b for b in bars if b.ts <= fin] for s, bars in data.items()
            if any(b.ts <= fin for b in bars)}


def test_la_grille_passee_ne_change_pas_quand_l_avenir_arrive():
    from packages.backtest.panel import aligner_par_date
    data = _panel()
    coupe = _jours(1400)[1000]
    _, complet, _, _ = aligner_par_date(data, list(data))
    _, tronque, _, _ = aligner_par_date(_tronquer(data, coupe), list(_tronquer(data, coupe)))
    j = coupe.date().isoformat()
    assert [d for d in complet if d <= j] == tronque


def test_le_backtest_demarre_au_meme_endroit_avec_ou_sans_ipo_futures():
    from packages.backtest.preset_backtest import preset_backtest
    avec = preset_backtest(_panel())
    sans = preset_backtest({s: b for s, b in _panel().items() if b[0].ts == D0})
    assert avec["panel"]["debut"] == sans["panel"]["debut"] == D0.date().isoformat()


def test_un_calendrier_uniforme_ne_change_pas():
    """Propriété d'équivalence : sans introduction ni radiation, la grille est inchangée."""
    from packages.backtest.panel import aligner_par_date
    data = _panel(ipo_frac=0.0)
    _, dates, A, _ = aligner_par_date(data, list(data))
    assert len(dates) == 1400 and np.isfinite(A).all()
