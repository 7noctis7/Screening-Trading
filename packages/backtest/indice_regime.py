"""QML-009(a) : indice de marché EXOGÈNE pour la porte de régime (drapeau).

LE DÉFAUT. La porte de régime (`regime_mult` : pic, MM200, pente) lit
`indice_marche(A)`, l'indice équipondéré du PANIER que la porte doit justement
protéger. Il est endogène : les 12 noms retenus sont ceux du meilleur momentum,
donc leur indice monte quand ils montent, et la porte juge le risque de la
sélection par la sélection elle-même. Un indice de marché (QQQ, SPY) dit si LE
MARCHÉ est en régime défavorable, indépendamment de ce qu'on détient.

DRAPEAU. `QUANT_REGIME_INDICE=QQQ` (ou SPY) active l'indice exogène ; vide =
comportement historique, au chiffre près. Il s'applique à
`preset_latest_weights_explique`, donc à la production (`make live`) ET au rejeu
(`make preset-replay`) : on compare les deux réglages sur la même règle avant
d'en activer un.

    make preset-replay                              # référence
    QUANT_REGIME_INDICE=QQQ make preset-replay      # variante

POINT-IN-TIME. Seules des clôtures ≤ à la date du panel sont lues : report du
DERNIER cours connu, jamais de remplissage vers l'arrière. Si la série couvre
moins de 95 % des dates du panel, on retombe sur l'indice du panier, et le
diagnostic le DIT.
"""

from __future__ import annotations

import os
from bisect import bisect_right

import numpy as np

from packages.backtest.panel import _jour

ENV = "QUANT_REGIME_INDICE"
COUVERTURE_MIN = 0.95


def symbole_configure() -> str | None:
    """Symbole de l'indice exogène, ou None si le drapeau est absent (défaut)."""
    s = os.environ.get(ENV, "").strip().upper()
    return s or None


def _clotures(data: dict, symbole: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for b in data.get(symbole) or []:
        j, c = _jour(b), getattr(b, "close", None)
        if j and c is not None and c == c and c > 0:
            out[j] = float(c)
    return out


def indice_exogene(data: dict, dates: list[str], symbole: str) -> np.ndarray | None:
    """Clôtures de `symbole` alignées sur `dates` (dernier cours connu ≤ date).

    None si la série manque ou couvre moins de `COUVERTURE_MIN` des dates."""
    px = _clotures(data, symbole)
    if not px or not dates:
        return None
    jours = sorted(px)
    out = np.full(len(dates), np.nan)
    for i, d in enumerate(dates):
        k = bisect_right(jours, d)
        if k:
            out[i] = px[jours[k - 1]]
    exactes = sum(1 for d in dates if d in px) / len(dates)
    if exactes < COUVERTURE_MIN or not np.isfinite(out).all():
        return None
    return out


def choisir_indice(data: dict, dates: list[str], A, d, symbole: str | None = None):
    """Indice de la porte de régime : exogène si configuré ET exploitable, sinon
    panier équipondéré."""
    from packages.backtest.preset_helpers import indice_marche
    sym = symbole if symbole is not None else symbole_configure()
    if sym:
        ext = indice_exogene(data, dates, sym)
        if ext is not None:
            d.note("indice de régime", f"{sym} (exogène, QML-009a)")
            return ext
        d.note("indice de régime", f"⚠️  {sym} absent ou couverture < "
                                   f"{COUVERTURE_MIN:.0%} → panier équipondéré")
    return indice_marche(A)
