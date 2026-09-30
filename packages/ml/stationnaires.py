"""Indicateurs techniques → variables STATIONNAIRES pour le méta-modèle (AFML ch. 5).

Un modèle entraîné sur des niveaux (prix, SMA, ATR en dollars) apprend l'époque, pas
le signal : ces séries dérivent, leur distribution change d'un régime à l'autre. Chaque
transformation ici produit une variable sans unité et de distribution stable :
  * normalisée par l'ATR (distance, momentum, MACD exprimés en « ATR ») ;
  * ou en z-score glissant (RSI, volume, largeur de Bollinger, pente de volatilité).

Contrats (testés) :
  * CAUSAL : la valeur en t ne lit que les barres ≤ t — tronquer l'avenir ne la change pas ;
  * INVARIANT D'ÉCHELLE : multiplier les prix (ou les volumes) par k ne change rien ;
  * NaN pendant le préchauffage, jamais de remplissage vers l'arrière.

Ajouter une variable = une fonction décorée `@transformations.register("nom")` qui reçoit
le `Contexte` (séries de base calculées une fois) et rend un tableau aligné sur les barres.
`diagnostic` vérifie la stationnarité par ADF ; une variable qui échoue est à revoir,
pas à garder « parce qu'elle aide ».
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from packages.core.registry import Registry
from packages.indicators.registry import indicators

Transformation = Callable[["Contexte"], np.ndarray]
transformations: Registry[Transformation] = Registry("transformation stationnaire")

FENETRE_Z = 100            # z-score : ~5 mois de séances, assez pour une dispersion stable
CRITERE_ADF = -2.86        # 5 %, avec constante


@dataclass(frozen=True)
class Contexte:
    """Séries de base d'UNE série de barres, calculées une fois (toutes causales)."""

    close: np.ndarray
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray
    atr: np.ndarray            # ATR(14), NaN si ≤ 0
    rsi: np.ndarray            # RSI(14)
    fenetre_z: int = FENETRE_Z


def _serie(bars, nom: str, **kw) -> np.ndarray:
    return np.asarray(indicators.create(nom, **kw).compute(bars), float)


def contexte(bars, fenetre_z: int = FENETRE_Z) -> Contexte:
    atr = _serie(bars, "atr", period=14)
    return Contexte(close=np.array([b.close for b in bars], float),
                    high=np.array([b.high for b in bars], float),
                    low=np.array([b.low for b in bars], float),
                    volume=np.array([b.volume for b in bars], float),
                    atr=np.where(atr > 0, atr, np.nan), rsi=_serie(bars, "rsi", period=14),
                    fenetre_z=fenetre_z)


def zscore_glissant(x: np.ndarray, n: int) -> np.ndarray:
    """(x_t − moyenne) / écart-type des n valeurs finissant en t ; NaN si une valeur de la
    fenêtre manque ou si la dispersion est nulle (canal plat : pas de division par ~0)."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(x.size, np.nan)
    if x.size < n:
        return out
    W = sliding_window_view(np.asarray(x, float), n)
    m, sd = W.mean(axis=1), W.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = sd > 1e-12 * np.maximum(1.0, np.abs(m))
        out[n - 1:] = np.where(ok, (x[n - 1:] - m) / np.where(ok, sd, 1.0), np.nan)
    return out


def _decale(x: np.ndarray, k: int) -> np.ndarray:
    """x_{t−k} aligné sur t (NaN au début) — jamais x_{t+k}."""
    out = np.full(x.size, np.nan)
    out[k:] = x[:x.size - k]
    return out


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    a, out = 2.0 / (n + 1), np.full(x.size, np.nan)
    prec = np.nan
    for i, v in enumerate(x):
        if np.isfinite(v):
            prec = v if not np.isfinite(prec) else a * v + (1 - a) * prec
        out[i] = prec
    out[:n - 1] = np.nan
    return out


def _moyenne(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if x.size >= n:
        cs = np.concatenate([[0.0], np.cumsum(x)])
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


@transformations.register("rsi_z")
def rsi_z(ctx: Contexte) -> np.ndarray:
    """RSI(14) en z-score : un RSI de 70 n'a pas le même sens en tendance et en range."""
    return zscore_glissant(ctx.rsi, ctx.fenetre_z)


@transformations.register("ecart_sma20_atr")
def ecart_sma20_atr(ctx: Contexte) -> np.ndarray:
    """(Close − SMA20) / ATR : distance à la moyenne en unités de volatilité."""
    with np.errstate(invalid="ignore"):
        return (ctx.close - _moyenne(ctx.close, 20)) / ctx.atr


@transformations.register("ecart_sma200_atr")
def ecart_sma200_atr(ctx: Contexte) -> np.ndarray:
    """(Close − SMA200) / ATR, en z-score : l'écart brut à la MM200 dérive en tendance."""
    with np.errstate(invalid="ignore"):
        return zscore_glissant((ctx.close - _moyenne(ctx.close, 200)) / ctx.atr,
                               ctx.fenetre_z)


@transformations.register("macd_hist_atr")
def macd_hist_atr(ctx: Contexte) -> np.ndarray:
    """Histogramme MACD(12, 26, 9) / ATR : le MACD en dollars croît avec le prix."""
    ligne = _ema(ctx.close, 12) - _ema(ctx.close, 26)
    with np.errstate(invalid="ignore"):
        return (ligne - _ema(ligne, 9)) / ctx.atr


@transformations.register("rendement5_atr")
def rendement5_atr(ctx: Contexte) -> np.ndarray:
    """Variation sur 5 barres / ATR : momentum court en unités de volatilité."""
    with np.errstate(invalid="ignore"):
        return (ctx.close - _decale(ctx.close, 5)) / ctx.atr


@transformations.register("pente_volatilite_z")
def pente_volatilite_z(ctx: Contexte) -> np.ndarray:
    """Pente de la volatilité relative, log(ATR/Close)_t − log(ATR/Close)_{t−10}, en
    z-score : la vol qui s'étend ou se comprime, indépendamment de son niveau."""
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.log(ctx.atr / ctx.close)
    return zscore_glissant(lv - _decale(lv, 10), ctx.fenetre_z)


@transformations.register("largeur_bollinger_z")
def largeur_bollinger_z(ctx: Contexte) -> np.ndarray:
    """log(largeur des bandes de Bollinger(20, 2) / SMA20) en z-score (compression)."""
    from numpy.lib.stride_tricks import sliding_window_view
    sd = np.full(ctx.close.size, np.nan)
    if ctx.close.size >= 20:
        sd[19:] = sliding_window_view(ctx.close, 20).std(axis=1, ddof=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return zscore_glissant(np.log(4 * sd / _moyenne(ctx.close, 20)), ctx.fenetre_z)


@transformations.register("volume_z")
def volume_z(ctx: Contexte) -> np.ndarray:
    """log(volume) en z-score : un volume anormal, quelle que soit la taille du titre."""
    with np.errstate(invalid="ignore", divide="ignore"):
        lv = np.where(ctx.volume > 0, np.log(np.where(ctx.volume > 0, ctx.volume, 1.0)),
                      np.nan)
    return zscore_glissant(lv, ctx.fenetre_z)


@transformations.register("position_range_20")
def position_range_20(ctx: Contexte) -> np.ndarray:
    """(Close − plus bas 20) / (plus haut 20 − plus bas 20) ∈ [0, 1] (stochastique)."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(ctx.close.size, np.nan)
    if ctx.close.size >= 20:
        hh = sliding_window_view(ctx.high, 20).max(axis=1)
        ll = sliding_window_view(ctx.low, 20).min(axis=1)
        e = hh - ll
        with np.errstate(invalid="ignore", divide="ignore"):
            out[19:] = np.where(e > 0, (ctx.close[19:] - ll) / np.where(e > 0, e, 1.0),
                                np.nan)
    return out


def construire(bars, noms: list[str] | None = None,
               fenetre_z: int = FENETRE_Z) -> dict[str, np.ndarray]:
    """Variables stationnaires alignées sur `bars` (toutes, ou celles de `noms`)."""
    ctx = contexte(bars, fenetre_z)
    return {n: np.asarray(transformations.get(n)(ctx), float)
            for n in (noms or transformations.names())}


def matrice(feats: dict[str, np.ndarray], idx) -> tuple[np.ndarray, list[str]]:
    """X aux indices d'événements (lignes = événements, colonnes = variables)."""
    noms = sorted(feats)
    idx = np.asarray(idx, int)
    return np.column_stack([feats[n][idx] for n in noms]), noms


def diagnostic(feats: dict[str, np.ndarray], crit: float = CRITERE_ADF) -> dict[str, dict]:
    """ADF par variable (valeurs finies) : stationnaire si stat < `crit`. Une série trop
    courte ou constante renvoie `stationnaire: None` (UNCALIBRATED), jamais True."""
    from packages.ml.features import adf_stat
    out = {}
    for n, x in feats.items():
        stat = adf_stat(x[np.isfinite(x)])
        ok = None if not np.isfinite(stat) else bool(stat < crit)
        out[n] = {"adf": stat, "stationnaire": ok, "n": int(np.isfinite(x).sum())}
    return out
