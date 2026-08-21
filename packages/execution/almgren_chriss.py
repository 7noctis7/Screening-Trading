"""Exécution optimale d'Almgren-Chriss — trajectoire de liquidation sous arbitrage
coût d'impact / risque de variance.

Le screener produit un BLOC à exécuter. Deux forces opposées :
  - exécuter vite = payer l'impact temporaire (coût d'urgence, certain) ;
  - exécuter lentement = subir la volatilité du prix pendant l'exécution (coût
    d'opportunité, aléatoire — c'est le RISQUE d'exécution, souvent oublié).

Modèle (Almgren & Chriss, 2000), liquidation de X titres en N intervalles de durée
tau = T/N, avec x_j = titres RESTANTS à t_j et n_j = x_(j-1) − x_j les trades :

  impact permanent   g(v) = gamma · v         (déplace durablement le prix)
  impact temporaire  h(v) = epsilon · sign(v) + eta · v      (payé sur CE trade)

  eta_tilde = eta − gamma·tau/2

  E[coût] = gamma·X²/2 + epsilon·somme|n_j| + (eta_tilde/tau)·somme n_j²
  Var[coût] = sigma² · tau · somme x_j²

  minimiser E + lambda·V  →  équation de récurrence dont la solution est

  kappa tel que  cosh(kappa·tau) = 1 + (lambda·sigma²/eta_tilde)·tau²/2

  x_j = X · sinh( kappa·(T − t_j) ) / sinh( kappa·T )

lambda = 0 redonne exactement la trajectoire linéaire (TWAP) ; lambda grand concentre
l'exécution au début (« front-loading »). 1/kappa est le TEMPS CARACTÉRISTIQUE de
liquidation : il ne dépend PAS de X — la taille change le coût, pas la forme optimale.

stdlib pure (math), testable hors-ligne.
"""

from __future__ import annotations

import math


def kappa_from_risk(lam: float, sigma: float, eta: float, gamma: float,
                    tau: float) -> dict:
    """Résout cosh(kappa·tau) = 1 + kappa_tilde²·tau²/2. Renvoie kappa et eta_tilde."""
    eta_t = eta - gamma * tau / 2.0
    if eta_t <= 0:
        return {"available": False,
                "reason": "eta_tilde <= 0 : intervalles trop longs devant l'impact "
                          "temporaire — réduire tau ou revoir la calibration"}
    if lam <= 0 or sigma <= 0:
        return {"available": True, "kappa": 0.0, "eta_tilde": eta_t}   # neutre au risque = TWAP
    k2 = lam * sigma ** 2 / eta_t
    arg = 1.0 + k2 * tau ** 2 / 2.0
    return {"available": True, "kappa": math.acosh(arg) / tau, "eta_tilde": eta_t,
            "kappa_tilde2": k2}


def trajectory(x_total: float, horizon: float, n_steps: int, sigma: float,
               eta: float, gamma: float = 0.0, lam: float = 0.0,
               epsilon: float = 0.0) -> dict:
    """Trajectoire optimale + coût espéré et variance.

    Args:
        x_total: quantité à exécuter (titres, signe ignoré — la forme est symétrique).
        horizon: durée totale autorisée, dans l'unité de temps de `sigma`.
        n_steps: nombre d'intervalles.
        sigma: volatilité du prix en MONNAIE par titre et par racine d'unité de temps.
        eta: impact temporaire (monnaie par titre, par titre-et-par-unité-de-temps).
        gamma: impact permanent (monnaie par titre, par titre échangé).
        lam: aversion au risque (0 = TWAP ; grand = exécution accélérée).
        epsilon: coût fixe par titre (demi-spread).
    """
    X = abs(float(x_total))
    if X <= 0 or n_steps < 1 or horizon <= 0:
        return {"available": False}
    tau = horizon / n_steps
    k = kappa_from_risk(lam, sigma, eta, gamma, tau)
    if not k.get("available"):
        return {"available": False, "reason": k["reason"]}
    kappa, eta_t = k["kappa"], k["eta_tilde"]
    if kappa <= 0:
        holdings = [X * (1.0 - j / n_steps) for j in range(n_steps + 1)]
    else:
        sh = math.sinh(kappa * horizon)
        holdings = [X * math.sinh(kappa * (horizon - j * tau)) / sh
                    for j in range(n_steps + 1)]
    holdings[-1] = 0.0                                    # liquidation complète imposée
    trades = [holdings[j - 1] - holdings[j] for j in range(1, n_steps + 1)]
    e_cost = (gamma * X ** 2 / 2.0
              + epsilon * sum(abs(t) for t in trades)
              + (eta_t / tau) * sum(t * t for t in trades))
    var = sigma ** 2 * tau * sum(x * x for x in holdings[1:])
    return {"available": True, "kappa": kappa, "tau": tau, "n_steps": n_steps,
            "half_life": (1.0 / kappa if kappa > 0 else float("inf")),
            "holdings": holdings, "trades": trades,
            "expected_cost": e_cost, "variance": var,
            "stdev": math.sqrt(max(var, 0.0)),
            "objective": e_cost + lam * var,
            "front_loading": round(trades[0] / (X / n_steps), 3),
            "is_twap": kappa == 0.0}


def efficient_frontier(x_total: float, horizon: float, n_steps: int, sigma: float,
                       eta: float, gamma: float = 0.0, epsilon: float = 0.0,
                       lams: list[float] | None = None) -> list[dict]:
    """Frontière efficiente d'exécution : (coût espéré, écart-type) pour plusieurs lambda.

    C'est l'objet à regarder, pas un lambda unique : il montre le prix, en bps, de chaque
    unité de risque d'exécution évitée. Le choix de lambda est une décision de risque, pas
    un paramètre à optimiser sur l'historique.
    """
    grid = lams if lams is not None else [0.0, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4]
    out = []
    for lam in grid:
        r = trajectory(x_total, horizon, n_steps, sigma, eta, gamma, lam, epsilon)
        if r.get("available"):
            out.append({"lam": lam, "expected_cost": r["expected_cost"],
                        "stdev": r["stdev"], "half_life": r["half_life"],
                        "front_loading": r["front_loading"]})
    return out


def cap_by_participation(trades: list[float], bar_volume: float,
                         pov: float = 0.10) -> dict:
    """Écrête la trajectoire au plafond de participation et dit si l'horizon tient.

    La trajectoire d'Almgren-Chriss ignore le carnet : rien n'y empêche un premier trade à
    300 % du volume de la barre. Le plafond POV est une contrainte DURE qui s'applique
    APRÈS l'optimisation ; s'il mord, l'horizon choisi est infaisable — il faut l'allonger,
    pas écrêter en silence.
    """
    cap = max(0.0, pov) * max(0.0, bar_volume)
    capped = [min(t, cap) for t in trades]
    residual = sum(trades) - sum(capped)
    return {"trades": capped, "cap": cap, "residual": residual,
            "feasible": residual <= 1e-9,
            "n_binding": sum(1 for t in trades if t > cap + 1e-12)}
