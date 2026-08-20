"""Loi fondamentale de la gestion active — souffle EFFECTIF et IR décomposé.

Grinold & Kahn : IR = IC · √BR. Clarke-de Silva-Thorley ajoutent le **coefficient de
transfert** : IR = IC · √BR · TC, où TC mesure ce qui SURVIT aux contraintes
(plafonds de poids, bandes de non-trading, gross piloté par la vol…).

Le piège institutionnel n°1 est de compter BR = N × T. Deux signaux corrélés en coupe
ne sont pas deux paris ; un signal lent (autocorrélé) rejoué chaque semaine n'est pas
52 paris par an. On calcule donc un souffle EFFECTIF :

  N_eff = N / (1 + (N − 1) · rho_cross)        (corrélation moyenne des signaux en coupe)
  T_eff = T · (1 − rho_time) / (1 + rho_time)  (autocorrélation du signal entre décisions)
  BR_eff = N_eff · T_eff

Fonctions PURES (numpy), testables hors-ligne. Mandat données réelles : `None` en entrée
→ résultat marqué UNCALIBRATED, jamais de chiffre inventé.
"""

from __future__ import annotations

import numpy as np


def autocorr(series, lag: int = 1) -> float:
    """Autocorrélation d'ordre `lag` (0 si dégénérée). Sert à mesurer rho_time."""
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    if x.size <= lag + 1:
        return 0.0
    a, b = x[:-lag], x[lag:]
    sa, sb = a.std(), b.std()
    if sa <= 0 or sb <= 0:
        return 0.0
    return float(np.clip(np.corrcoef(a, b)[0, 1], -0.999, 0.999))


def mean_pairwise_corr(panel) -> float:
    """Corrélation moyenne hors-diagonale d'un panel n × T (n signaux, T dates)."""
    M = np.asarray(panel, dtype=float)
    if M.ndim != 2 or M.shape[0] < 2 or M.shape[1] < 3:
        return 0.0
    keep = np.isfinite(M).all(axis=1) & (M.std(axis=1) > 0)
    M = M[keep]
    if M.shape[0] < 2:
        return 0.0
    C = np.corrcoef(M)
    n = C.shape[0]
    off = (C.sum() - np.trace(C)) / (n * (n - 1))
    return float(np.clip(off, -0.999, 0.999))


def effective_names(n_names: int, rho_cross: float) -> float:
    """N_eff = N / (1 + (N−1)·rho). rho ≤ 0 est ramené à 0 (prudence : jamais de bonus)."""
    n = max(0, int(n_names))
    if n <= 1:
        return float(n)
    rho = float(max(0.0, min(0.999, rho_cross)))
    return float(n / (1.0 + (n - 1) * rho))


def effective_periods(n_periods: int, rho_time: float) -> float:
    """T_eff = T · (1−rho)/(1+rho) — un signal persistant rejoue le MÊME pari."""
    t = max(0, int(n_periods))
    if t <= 1:
        return float(t)
    rho = float(max(0.0, min(0.999, rho_time)))
    return float(t * (1.0 - rho) / (1.0 + rho))


def effective_breadth(n_names: int, n_periods: int, rho_cross: float = 0.0,
                      rho_time: float = 0.0) -> dict:
    """Souffle effectif BR_eff = N_eff · T_eff + facteur de sur-comptage vs N·T naïf."""
    n_eff = effective_names(n_names, rho_cross)
    t_eff = effective_periods(n_periods, rho_time)
    naive = float(max(0, n_names) * max(0, n_periods))
    br = n_eff * t_eff
    return {"n_eff": round(n_eff, 3), "t_eff": round(t_eff, 3),
            "breadth_eff": round(br, 3), "breadth_naive": naive,
            "overcount": round(naive / br, 2) if br > 0 else float("inf")}


def transfer_coefficient(alpha_scores, weights) -> float:
    """TC = corrélation(alphas souhaités, poids RÉELLEMENT pris).

    Mesure la perte due aux contraintes (cap, bande, gross, long-only, blackout).
    TC = 1 → portefeuille non contraint ; TC = 0,4 → 60 % de l'IR théorique est perdu
    AVANT même de parler d'alpha. C'est le diagnostic le moins cher du projet.
    """
    a = np.asarray(alpha_scores, dtype=float)
    w = np.asarray(weights, dtype=float)
    m = np.isfinite(a) & np.isfinite(w)
    a, w = a[m], w[m]
    if a.size < 3 or a.std() <= 0 or w.std() <= 0:
        return 0.0
    return float(np.clip(np.corrcoef(a, w)[0, 1], -1.0, 1.0))


def expected_ir(ic: float, breadth: float, tc: float = 1.0) -> float:
    """IR attendu = IC · √BR · TC (annualisé si BR est compté sur un an)."""
    if breadth <= 0:
        return 0.0
    return float(ic * np.sqrt(breadth) * tc)


def ic_required(target_ir: float, breadth: float, tc: float = 1.0) -> float | None:
    """IC minimal pour atteindre `target_ir`. Sert de test de réalité AVANT de coder.

    Un IC requis > 0,10 sur des données quotidiennes publiques = signal d'alarme :
    la littérature situe l'IC d'un facteur robuste entre 0,02 et 0,06.
    """
    if breadth <= 0 or tc <= 0:
        return None
    return float(target_ir / (np.sqrt(breadth) * tc))


def alpha_from_ic(vol, ic: float, z) -> np.ndarray:
    """Alpha de Grinold : alpha_i = volatilité_i · IC · z_i (z = score standardisé).

    Convertit un RANG en rendement attendu, seule forme utilisable par un optimiseur.
    Le z est écrêté à ±3 (les queues du score ne sont pas des queues de rendement).
    """
    v = np.asarray(vol, dtype=float)
    s = np.clip(np.asarray(z, dtype=float), -3.0, 3.0)
    return v * float(ic) * s


def ic_at_horizon(ic0: float, half_life: float, horizon: float) -> float:
    """Décroissance de l'IC : IC(h) = IC0 · exp(−ln2 · h / demi-vie) (mêmes unités).

    Sert à ré-échelonner un signal quand on passe de 1 h à Daily/Weekly : ce n'est pas
    le z-score qu'on change, c'est l'IC qui le multiplie (cf. `alpha_from_ic`).
    """
    if half_life <= 0 or horizon < 0:
        return 0.0
    return float(ic0 * np.exp(-np.log(2.0) * horizon / half_life))


def optimal_horizon(half_life: float) -> float:
    """Horizon de détention qui MAXIMISE l'IC, à partir de la demi-vie du signal.

    Si l'alpha instantané décroît en exp(−t/theta), le rendement espéré cumulé sur h croît
    en (1 − exp(−h/theta)) tandis que l'écart-type du rendement croît en √h. L'IC(h) suit
    donc (1 − exp(−u)) / √u avec u = h/theta ; l'annulation de la dérivée donne
    2·u·exp(−u) = 1 − exp(−u), soit u* ≈ 1,2564 et **h* ≈ 1,81 × demi-vie**.

    Détenir moins longtemps = payer des coûts pour une fraction de l'alpha ; détenir plus
    longtemps = diluer un signal éteint dans du bruit.
    """
    if half_life <= 0:
        return 0.0
    return float(1.2564 * half_life / np.log(2.0))


def ir_report(ic: float | None, n_names: int, n_periods: int, rho_cross: float = 0.0,
              rho_time: float = 0.0, tc: float | None = None) -> dict:
    """Rapport complet. IC ou TC non mesuré → status UNCALIBRATED (aucun chiffre inventé)."""
    br = effective_breadth(n_names, n_periods, rho_cross, rho_time)
    if ic is None or tc is None:
        return {"available": False, "status": "UNCALIBRATED", **br,
                "hint": "mesurer l'IC (rank-corr signal↔rendement futur) et le TC "
                        "(corr alphas↔poids réels) sur données réelles avant tout verdict"}
    ir = expected_ir(ic, br["breadth_eff"], tc)
    ir_naive = expected_ir(ic, br["breadth_naive"], 1.0)
    return {"available": True, **br, "ic": round(float(ic), 4), "tc": round(float(tc), 4),
            "ir_expected": round(ir, 3), "ir_naive_overstated": round(ir_naive, 3),
            "overstatement_x": round(ir_naive / ir, 2) if ir > 0 else float("inf")}
