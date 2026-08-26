"""Les poids de PRODUCTION ne doivent pas dépendre du CALENDRIER de cotation.

Constat du 26/08 : `preset_latest_weights` — la fonction qui pilote `make live` —
empilait les séries POSITIONNELLEMENT (`fenetre_commune`) alors que le backtest
était passé à l'alignement par date en #341. Production et backtest ne mesuraient
donc pas la même chose.

Sur un panier mêlant actions (5 séances/semaine) et crypto (7 j/7), les colonnes
des deux familles portaient des dates différentes — jusqu'à trois ans d'écart sur
onze ans. La covariance de l'ERC, l'indice de marché de la porte de régime et le
tilt momentum étaient tous calculés sur ce mélange.

PROTOCOLE. Deux familles aux économies STRICTEMENT identiques (même dérive et même
volatilité ANNUELLES), différant seulement par leur calendrier. Toute préférence
systématique de l'une pour l'autre est alors un artefact, par construction. La
qualité est tirée au hasard pour que la sélection d'univers reste neutre.

Mesuré : rapport médian de poids par ligne 0,88 avant migration, 0,97 après.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from packages.backtest.preset_backtest import preset_latest_weights

DEBUT = datetime(2021, 1, 1, tzinfo=timezone.utc)
FIN = datetime(2026, 8, 26, tzinfo=timezone.utc)
DRIFT_AN, VOL_AN = 0.12, 0.35


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _serie(seed: int, jours_ouvres: bool) -> list:
    rng = np.random.default_rng(seed)
    dates, d = [], DEBUT
    while d <= FIN:
        if not jours_ouvres or d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    par_an = 252.0 if jours_ouvres else 365.0    # MÊME économie, calendrier différent
    px = 100 * np.cumprod(
        1 + rng.normal(DRIFT_AN / par_an, VOL_AN / np.sqrt(par_an), len(dates)))
    return [Bar(dates[i], *(4 * [float(px[i])]), 1e6) for i in range(len(dates))]


def _panier(essai: int, n: int = 10):
    data, acmap = {}, {}
    for i in range(n):
        data[f"ACT{i:02d}"] = _serie(1000 * essai + i, True)
        acmap[f"ACT{i:02d}"] = "equity"
        data[f"CRY{i:02d}"] = _serie(1000 * essai + 500 + i, False)
        acmap[f"CRY{i:02d}"] = "crypto"
    return data, acmap


def _rapport_poids_par_ligne(essai: int):
    """Poids moyen d'une ligne crypto / d'une ligne action. Neutre = 1,0."""
    data, acmap = _panier(essai)
    rng = np.random.default_rng(essai)
    qual = {s: float(rng.random()) for s in data}     # sélection neutre
    w = preset_latest_weights(data, qual, asset_classes=acmap, top_k=12,
                              min_weight=0.0)
    nc = sum(1 for s in w if s.startswith("CRY"))
    na = sum(1 for s in w if s.startswith("ACT"))
    if not nc or not na:
        return None
    wc = sum(v for s, v in w.items() if s.startswith("CRY"))
    wa = sum(v for s, v in w.items() if s.startswith("ACT"))
    return (wc / nc) / (wa / na)


def test_pas_de_preference_systematique_pour_un_calendrier():
    """Le rapport médian doit rester proche de 1.

    La borne est LARGE (±20 %) : on cherche un biais STRUCTUREL, pas à figer une
    valeur numérique — l'échantillon reste bruité.
    """
    r = [x for x in (_rapport_poids_par_ligne(e) for e in range(8)) if x is not None]
    assert len(r) >= 5, "trop peu de tirages exploitables pour conclure"
    med = float(np.median(r))
    assert 0.80 <= med <= 1.20, f"biais de calendrier : mediane {med:.2f} vs 1,00"


def test_le_panel_de_production_est_aligne_par_date():
    """Verrou structurel : production et backtest, même famille d'alignement.

    On inspecte les IMPORTS effectifs du module, pas son texte : le nom de
    l'ancienne fonction reste cité dans la docstring qui explique la migration,
    et un test qui grepperait la source casserait sur cette mention historique.
    """
    import ast
    import inspect

    from packages.backtest import preset_weights
    arbre = ast.parse(inspect.getsource(preset_weights))
    importes = {a.name for n in ast.walk(arbre)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "aligner_sans_trous" in importes, "la production n'aligne plus par date"
    assert "fenetre_commune" not in importes, "retour a l'empilement positionnel"


def test_production_reste_calculable_sur_un_panier_homogene():
    """Non-régression : sur un panier d'un seul calendrier, rien ne casse."""
    data = {f"ACT{i:02d}": _serie(7000 + i, True) for i in range(12)}
    acmap = {s: "equity" for s in data}
    rng = np.random.default_rng(3)
    w = preset_latest_weights(data, {s: float(rng.random()) for s in data},
                              asset_classes=acmap, top_k=10)
    assert w and all(v > 0 for v in w.values())
    assert sum(w.values()) <= 1.0 + 1e-9              # jamais de levier
