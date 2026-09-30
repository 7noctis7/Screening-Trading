"""SMCLXTP-A — zones SMC (Premium / Equilibrium / Discount) + pivots LuxAlgo, LONG et TP.

Traduction de l'indicateur Pine Script v6 de l'utilisateur. Une seule implémentation
sert au backtest, au paper et au ML : la parité entre les modes vient de là.

TROIS CORRECTIONS par rapport à la traduction fournie, chacune verrouillée par un test
(`tests/indicators/test_smc_lux_tp.py`) :
  1. LOOK-AHEAD. Un swing était daté à la barre du PIVOT, confirmé par la fenêtre centrée
     [i−L, i+L] : les zones d'une barre lisaient les L barres SUIVANTES (50 par défaut).
     Comme `ta.pivothigh(L, L)` en Pine, un pivot n'existe ici qu'à sa barre de
     CONFIRMATION, L barres après lui.
  2. ÉGALITÉS. `high == max(fenêtre)` déclarait un pivot à chaque barre d'une série
     plate. Extremum STRICT sur les voisins, la convention du dépôt
     (`market_structure.pivots_indexes`).
  3. ÉTAT INITIAL. Le moteur des pivots manqués partait d'un « dernier pivot = creux »
     fictif : le premier creux venu était déclaré TP manqué. L'état initial est « aucun ».

`ob_search_bars` et `ob_mitigation_mode` restent acceptés pour la compatibilité d'appel :
la traduction fournie ne les utilisait pas, et ils ne changent rien ici.

SÉMANTIQUE À CONNAÎTRE : un creux « manqué » se constate au moment où un DEUXIÈME sommet
consécutif est confirmé, soit L barres après ce sommet. Le signal LONG qu'il émet tombe
donc après un sommet, pas sur le creux. C'est fidèle au Pine ; c'est à mesurer
(`ml/meta_smc.py`), pas à supposer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from packages.indicators.registry import indicators

if TYPE_CHECKING:
    import pandas as pd

PART_ZONE = 0.05              # Premium = 5 % haut du range, Discount = 5 % bas (LuxAlgo)


def pivots_confirmes(high, low, longueur: int) -> tuple[np.ndarray, np.ndarray]:
    """(sommets, creux) : valeur du pivot à sa barre de CONFIRMATION, NaN ailleurs."""
    from numpy.lib.stride_tricks import sliding_window_view as fenetres
    h, lo = np.asarray(high, float), np.asarray(low, float)
    ph, pl = np.full(h.size, np.nan), np.full(h.size, np.nan)
    L = int(longueur)
    if L < 1 or h.size < 2 * L + 1:
        return ph, pl
    W, V = fenetres(h, 2 * L + 1), fenetres(lo, 2 * L + 1)
    cote_h = np.maximum(W[:, :L].max(axis=1), W[:, L + 1:].max(axis=1))
    cote_b = np.minimum(V[:, :L].min(axis=1), V[:, L + 1:].min(axis=1))
    est_h, est_b = W[:, L] > cote_h, V[:, L] < cote_b        # NaN → faux, jamais pivot
    confirmation = np.arange(W.shape[0]) + 2 * L              # centre + L barres
    ph[confirmation[est_h]] = W[est_h, L]
    pl[confirmation[est_b]] = V[est_b, L]
    return ph, pl


def dernier_connu(x: np.ndarray) -> np.ndarray:
    """Dernière valeur non-NaN à chaque barre (report vers l'avant, jamais l'inverse)."""
    idx = np.where(np.isnan(x), 0, np.arange(x.size))
    np.maximum.accumulate(idx, out=idx)
    return x[idx]


def zones(sommets: np.ndarray, creux: np.ndarray) -> dict[str, np.ndarray]:
    """Range = dernier sommet et dernier creux CONFIRMÉS, s'ils sont ordonnés."""
    top, bas = dernier_connu(sommets), dernier_connu(creux)
    with np.errstate(invalid="ignore"):
        ok = top > bas
    top, bas = np.where(ok, top, np.nan), np.where(ok, bas, np.nan)
    return {"range_top": top, "range_bottom": bas,
            "premium_bottom": (1 - PART_ZONE) * top + PART_ZONE * bas,
            "eq_mid": 0.5 * top + 0.5 * bas,
            "discount_top": (1 - PART_ZONE) * bas + PART_ZONE * top}


def ratio_zone(close, premium_bottom: np.ndarray, discount_top: np.ndarray) -> np.ndarray:
    """(close − discount_top) / (premium_bottom − discount_top) : 0 en haut du Discount,
    1 en bas du Premium. Sans unité de prix, donc comparable entre titres."""
    den = premium_bottom - discount_top
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (np.asarray(close, float) - discount_top) / den
        return np.where(den > 0, r, np.nan)


def evenements(sommets: np.ndarray, creux: np.ndarray,
               manques: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(long, tp). Pivot régulier, ou pivot MANQUÉ : deux pivots de même nature
    consécutifs trahissent un pivot opposé entre eux, constaté au second."""
    n = sommets.size
    long_, tp = np.zeros(n, bool), np.zeros(n, bool)
    etat: str | None = None
    for i in np.flatnonzero(~np.isnan(sommets) | ~np.isnan(creux)):
        if not np.isnan(sommets[i]):
            tp[i] = True
            long_[i] |= manques and etat == "haut"
            etat = "haut"
        if not np.isnan(creux[i]):
            long_[i] = True
            tp[i] |= manques and etat == "bas"
            etat = "bas"
    return long_, tp


def calculer(high, low, close, *, swing_length: int = 50, pivot_length: int = 50,
             pivots_manques: bool = True) -> dict[str, np.ndarray]:
    """Toutes les sorties de SMCLXTP-A, alignées sur les barres, CAUSALES."""
    sommets, creux = pivots_confirmes(high, low, swing_length)
    z = zones(sommets, creux)
    ph, pl = ((sommets, creux) if pivot_length == swing_length
              else pivots_confirmes(high, low, pivot_length))
    long_, tp = evenements(ph, pl, pivots_manques)
    return {"swing_high": sommets, "swing_low": creux, **z,
            "smc_zone_ratio": ratio_zone(close, z["premium_bottom"], z["discount_top"]),
            "long_signal": long_, "take_profit_signal": tp}


class SMCLuxTPIndicator:
    """Interface de la traduction fournie (DataFrame OHLC → DataFrame enrichi)."""

    def __init__(self, swing_length: int = 50, ob_search_bars: int = 10,
                 ob_mitigation_mode: str = "High/Low", pivot_length: int = 50,
                 show_missed_pivots: bool = True) -> None:
        self.swing_length = swing_length
        self.ob_search_bars = ob_search_bars            # non utilisé (compatibilité)
        self.ob_mitigation_mode = ob_mitigation_mode    # non utilisé (compatibilité)
        self.pivot_length = pivot_length
        self.show_missed_pivots = show_missed_pivots

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        r = calculer(df["high"].to_numpy(float), df["low"].to_numpy(float),
                     df["close"].to_numpy(float), swing_length=self.swing_length,
                     pivot_length=self.pivot_length,
                     pivots_manques=self.show_missed_pivots)
        out = df.copy()
        for cle, serie in r.items():
            out[cle] = serie
        return out


class _SMCLXTP:
    """Adaptateur registre : barres → une série de SMCLXTP-A."""

    sortie = ""

    def __init__(self, swing_length: int = 50, pivot_length: int = 50,
                 show_missed_pivots: bool = True) -> None:
        self.params = {"swing_length": swing_length, "pivot_length": pivot_length,
                       "pivots_manques": show_missed_pivots}

    def compute(self, bars) -> list[float]:
        r = calculer([b.high for b in bars], [b.low for b in bars],
                     [b.close for b in bars], **self.params)
        return np.asarray(r[self.sortie], float).tolist()


@indicators.register("smc_zone_ratio")
class SMCZoneRatio(_SMCLXTP):
    name = sortie = "smc_zone_ratio"


@indicators.register("smclxtp_long")
class SMCLXTPLong(_SMCLXTP):
    name, sortie = "smclxtp_long", "long_signal"


@indicators.register("smclxtp_tp")
class SMCLXTPTakeProfit(_SMCLXTP):
    name, sortie = "smclxtp_tp", "take_profit_signal"
