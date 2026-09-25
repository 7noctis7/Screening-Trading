"""Règles d'allocation du banc d'exploration — CAUSALES par construction.

Chaque règle reçoit la matrice de prix complète mais n'en lit que `A[:, :t+1]` : la
tranche est faite AVANT tout calcul, si bien qu'aucun indicateur ne peut toucher une barre
future, même par erreur d'indice. Les fenêtres sont exprimées en JOURS DE BOURSE puis
converties en barres via `par_an` : « momentum 12 mois » garde le même sens en 1h, 4h
ou quotidien.

Une règle = sélection × pondération × overlay :
  sélection   tout · mom_12_1 · mom_6_1 · basse_vol · tendance_mm200
  pondération egal · inv_vol · erc
  overlay     aucun · vol_cible_15 · regime_mm200
"""

from __future__ import annotations

import numpy as np

SELECTIONS = ("tout", "mom_12_1", "mom_6_1", "basse_vol", "tendance_mm200")
PONDERATIONS = ("egal", "inv_vol", "erc")
OVERLAYS = ("aucun", "vol_cible_15", "regime_mm200")
FENETRE_VOL = 63                      # jours de bourse (≈ 3 mois)


def barres(jours: float, par_an: float) -> int:
    """Jours de bourse → nombre de barres au timeframe courant."""
    return max(2, int(round(jours * par_an / 252.0)))


def _rendements(P: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        r = P[:, 1:] / P[:, :-1] - 1.0
    return np.where(np.isfinite(r), r, np.nan)


def _vol(P: np.ndarray, par_an: float) -> np.ndarray:
    """Volatilité récente par actif ; NaN si moins de 80 % de la fenêtre est cotée."""
    n = barres(FENETRE_VOL, par_an)
    r = _rendements(P[:, -(n + 1):])
    ok = np.isfinite(r).sum(axis=1) >= 0.8 * n
    with np.errstate(invalid="ignore"):
        v = np.nanstd(r, axis=1, ddof=1)
    return np.where(ok & (v > 0), v, np.nan)


def _retour(P: np.ndarray, debut: int, fin: int) -> np.ndarray:
    """P[t-fin] / P[t-debut] - 1 (debut > fin, en barres avant la dernière)."""
    if P.shape[1] <= debut:
        return np.full(P.shape[0], np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        return P[:, -1 - fin] / P[:, -1 - debut] - 1.0


def _meilleurs(score: np.ndarray, vivants: np.ndarray, k: int) -> np.ndarray:
    ok = vivants & np.isfinite(score)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return idx
    return idx[np.argsort(-score[idx], kind="stable")[:k]]


def _selection(P: np.ndarray, nom: str, k: int, par_an: float) -> np.ndarray:
    vivants = np.isfinite(P[:, -1])
    if nom == "tout":
        return np.flatnonzero(vivants)
    if nom in ("mom_12_1", "mom_6_1"):
        mois = 12 if nom == "mom_12_1" else 6
        score = _retour(P, barres(21 * mois, par_an), barres(21, par_an))
        return _meilleurs(score, vivants, k)
    if nom == "basse_vol":
        return _meilleurs(-_vol(P, par_an), vivants, k)
    if nom == "tendance_mm200":
        n = barres(200, par_an)
        if P.shape[1] < n:
            return np.array([], dtype=int)
        with np.errstate(invalid="ignore"):
            ecart = P[:, -1] / np.nanmean(P[:, -n:], axis=1) - 1.0
        return _meilleurs(np.where(ecart > 0, ecart, np.nan), vivants, k)
    raise ValueError(f"sélection inconnue : {nom}")


def _ponderation(P: np.ndarray, idx: np.ndarray, nom: str, par_an: float) -> np.ndarray:
    if idx.size == 0:
        return np.zeros(0)
    if nom == "egal":
        return np.full(idx.size, 1.0 / idx.size)
    vol = _vol(P[idx], par_an)
    if nom == "inv_vol" or idx.size == 1:
        inv = np.where(np.isfinite(vol), 1.0 / np.where(np.isfinite(vol), vol, 1.0), 0.0)
        return inv / inv.sum() if inv.sum() > 0 else np.full(idx.size, 1.0 / idx.size)
    if nom == "erc":
        from packages.portfolio.optimize import equal_risk_contribution
        r = _rendements(P[idx, -(barres(FENETRE_VOL, par_an) + 1):])
        r = np.nan_to_num(r, nan=0.0)
        w = np.asarray(equal_risk_contribution(np.cov(r) + 1e-12 * np.eye(idx.size)))
        return w / w.sum() if w.size and w.sum() > 0 else np.full(idx.size, 1.0 / idx.size)
    raise ValueError(f"pondération inconnue : {nom}")


def _exposition(P: np.ndarray, w: np.ndarray, nom: str, par_an: float) -> float:
    if nom == "aucun" or not w.any():
        return 1.0
    if nom == "vol_cible_15":
        n = barres(FENETRE_VOL, par_an)
        r = np.nan_to_num(_rendements(P[:, -(n + 1):]), nan=0.0)
        port = w @ r
        if port.size < 2 or port.std(ddof=1) <= 0:
            return 1.0
        return float(min(1.0, 0.15 / (port.std(ddof=1) * np.sqrt(par_an))))
    if nom == "regime_mm200":
        from packages.backtest.preset_helpers import indice_marche
        n = barres(200, par_an)
        if P.shape[1] < n:
            return 1.0                                  # pas encore de MM : pas de verdict
        # Indice sur la seule fenêtre de la MM : la comparaison dernier/moyenne est
        # invariante à la base, et l'on évite de rechaîner tout l'historique à chaque date.
        ind = indice_marche(P[:, -n:])
        return 1.0 if ind[-1] >= ind[-n:].mean() else 0.0
    raise ValueError(f"overlay inconnu : {nom}")


def poids_a_la_date(A: np.ndarray, t: int, regle: dict, par_an: float) -> np.ndarray:
    """Poids cibles décidés au close `t`, sur les seules barres 0..t. Somme ≤ 1 (cash)."""
    P = np.asarray(A, float)[:, :t + 1]                 # la tranche d'abord : causalité
    k = int(regle.get("top_k", 10))
    idx = _selection(P, regle.get("selection", "tout"), k, par_an)
    w = np.zeros(P.shape[0])
    if idx.size == 0:
        return w
    w[idx] = _ponderation(P, idx, regle.get("ponderation", "egal"), par_an)
    return w * _exposition(P, w, regle.get("overlay", "aucun"), par_an)
