"""HMM gaussien CAUSAL — régimes latents sans biais d'anticipation.

`vol_regime.py` ajuste son HMM (et ses terciles) sur TOUT l'échantillon, futur inclus, puis
appelle `predict`, qui renvoie la séquence de Viterbi **lissée** : P(S_t | toutes les données).
Sans conséquence tant que l'appel vient du live, fuite immédiate dès qu'on le câble dans une
boucle de backtest (finding F3). Ce module est la version utilisable en recherche.

Modèle : r_t | S_t = k ~ N(mu_k, sigma_k²), transitions P_ij = P(S_t = j | S_(t−1) = i).

Trois exigences, toutes implémentées :

1. **Fenêtre expansive** — à la date t, les paramètres proviennent d'un Baum-Welch ajusté sur
   [0, dernier point de ré-ajustement ≤ t]. Ré-ajustement périodique, jamais à chaque barre
   (coût et instabilité).
2. **Probabilité FILTRÉE** — récursion forward normalisée, P(S_t | r_1..r_t). Jamais la
   probabilité lissée ni Viterbi, qui regardent le futur.
3. **Étiquetage stable** — après CHAQUE ajustement, les états sont réordonnés par volatilité
   croissante. Sans cela l'EM permute les étiquettes d'un ajustement à l'autre et « stress »
   devient « calme » sans que rien ne le signale : le bug le plus fréquent des HMM en prod.

Propriété vérifiée par test : tronquer la série à t donne EXACTEMENT le même chemin filtré
sur [0, t] que la série complète (sentinelle de non-fuite, cf. `pit_guard.stable_prefix`).

numpy pur.
"""

from __future__ import annotations

import numpy as np

_FLOOR = 1e-12


def _gauss(x: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Densités d'émission (T × K), plancher numérique pour éviter les zéros absorbants."""
    z = (x[:, None] - mu[None, :]) / sd[None, :]
    return np.maximum(np.exp(-0.5 * z * z) / (sd[None, :] * np.sqrt(2 * np.pi)), _FLOOR)


def _forward(B: np.ndarray, A: np.ndarray, pi: np.ndarray) -> tuple[np.ndarray, float]:
    """Récursion avant NORMALISÉE → (probabilités filtrées T × K, log-vraisemblance)."""
    T, K = B.shape
    alpha = np.zeros((T, K))
    loglik = 0.0
    a = pi * B[0]
    c = a.sum() or _FLOOR
    alpha[0] = a / c
    loglik += np.log(c)
    for t in range(1, T):
        a = (alpha[t - 1] @ A) * B[t]
        c = a.sum() or _FLOOR
        alpha[t] = a / c
        loglik += np.log(c)
    return alpha, float(loglik)


def _backward(B: np.ndarray, A: np.ndarray) -> np.ndarray:
    T, K = B.shape
    beta = np.ones((T, K))
    for t in range(T - 2, -1, -1):
        b = A @ (B[t + 1] * beta[t + 1])
        beta[t] = b / (b.sum() or _FLOOR)
    return beta


def baum_welch(x, k: int = 2, n_iter: int = 60, tol: float = 1e-6,
               seed: int = 0) -> dict:
    """Estimation EM des paramètres. Les états sont réordonnés par volatilité croissante."""
    r = np.asarray(x, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 20 * k:
        return {"available": False, "status": "UNCALIBRATED", "n": int(r.size)}
    qs = np.quantile(r, np.linspace(0.15, 0.85, k))         # init déterministe par quantiles
    mu = np.asarray(qs, dtype=float)
    sd = np.full(k, max(float(r.std(ddof=1)), 1e-8))
    A = np.full((k, k), 0.1 / max(1, k - 1))
    np.fill_diagonal(A, 0.9)
    pi = np.full(k, 1.0 / k)
    prev = -np.inf
    for _ in range(n_iter):
        B = _gauss(r, mu, sd)
        alpha, ll = _forward(B, A, pi)
        beta = _backward(B, A)
        g = alpha * beta
        g /= np.maximum(g.sum(axis=1, keepdims=True), _FLOOR)      # postérieurs lissés
        xi = np.zeros((k, k))
        for t in range(r.size - 1):
            m = (alpha[t][:, None] * A) * (B[t + 1] * beta[t + 1])[None, :]
            xi += m / max(m.sum(), _FLOOR)
        A = xi / np.maximum(xi.sum(axis=1, keepdims=True), _FLOOR)
        pi = g[0] / max(g[0].sum(), _FLOOR)
        w = np.maximum(g.sum(axis=0), _FLOOR)
        mu = (g * r[:, None]).sum(axis=0) / w
        var = (g * (r[:, None] - mu[None, :]) ** 2).sum(axis=0) / w
        sd = np.sqrt(np.maximum(var, 1e-16))
        if abs(ll - prev) < tol:
            break
        prev = ll
    order = np.argsort(sd)                                   # ÉTIQUETAGE STABLE : vol croissante
    return {"available": True, "k": k, "mu": mu[order], "sd": sd[order],
            "A": A[np.ix_(order, order)], "pi": pi[order],
            "loglik": float(prev), "n": int(r.size)}


def filtered_probabilities(x, params: dict) -> np.ndarray:
    """P(S_t | r_1..r_t) — la SEULE probabilité utilisable en décision."""
    r = np.asarray(x, dtype=float)
    B = _gauss(r, params["mu"], params["sd"])
    alpha, _ = _forward(B, params["A"], params["pi"])
    return alpha


def viterbi(x, params: dict) -> np.ndarray:
    """Séquence d'états la plus probable — LISSÉE, donc NON CAUSALE.

    Réservée à l'ANALYSE a posteriori (raconter une crise passée). L'utiliser comme signal
    de trading est un look-ahead pur : chaque état y dépend de toute la série.
    """
    r = np.asarray(x, dtype=float)
    B = _gauss(r, params["mu"], params["sd"])
    logA = np.log(np.maximum(params["A"], _FLOOR))
    d = np.log(np.maximum(params["pi"], _FLOOR)) + np.log(B[0])
    psi = np.zeros((r.size, params["k"]), dtype=int)
    for t in range(1, r.size):
        m = d[:, None] + logA
        psi[t] = m.argmax(axis=0)
        d = m.max(axis=0) + np.log(B[t])
    path = np.zeros(r.size, dtype=int)
    path[-1] = int(d.argmax())
    for t in range(r.size - 2, -1, -1):
        path[t] = psi[t + 1, path[t + 1]]
    return path


def causal_regime_path(x, k: int = 2, min_train: int = 250,
                       refit_every: int = 21, seed: int = 0) -> dict:
    """Chemin de régime SANS FUITE : fenêtre expansive + probabilité filtrée.

    À chaque date t ≥ `min_train`, les paramètres viennent du dernier ré-ajustement ANTÉRIEUR
    (grille ancrée au début de la série, donc stable par troncature) et la probabilité est
    filtrée sur [0, t]. Renvoie l'état filtré et la probabilité de l'état le plus volatil.
    """
    r = np.asarray(x, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < min_train + refit_every:
        return {"available": False, "status": "UNCALIBRATED", "n": int(n)}
    states = np.full(n, -1, dtype=int)
    p_stress = np.full(n, np.nan)
    params = None
    for t in range(min_train, n):
        if (t - min_train) % refit_every == 0 or params is None:
            fit = baum_welch(r[:t], k=k, seed=seed)          # PASSÉ STRICT
            params = fit if fit.get("available") else params
        if params is None:
            continue
        alpha = filtered_probabilities(r[:t + 1], params)
        states[t] = int(alpha[-1].argmax())
        p_stress[t] = float(alpha[-1, -1])                   # dernier état = vol la plus haute
    return {"available": True, "k": k, "states": states, "p_stress": p_stress,
            "min_train": min_train, "refit_every": refit_every,
            "last_state": int(states[-1]), "last_p_stress": float(p_stress[-1])}


def hysteresis(p_stress, enter: float = 0.70, exit_: float = 0.40) -> np.ndarray:
    """Filtre à hystérésis : entrer en stress à `enter`, n'en sortir qu'à `exit_`.

    Un seuil unique produit des allers-retours d'exposition exactement quand les coûts
    d'exécution explosent. L'asymétrie est délibérée : sortir vite, rentrer lentement.
    """
    p = np.asarray(p_stress, dtype=float)
    out = np.zeros(p.size, dtype=int)
    on = False
    for i, v in enumerate(p):
        if not np.isfinite(v):
            out[i] = int(on)
            continue
        if on and v < exit_:
            on = False
        elif (not on) and v > enter:
            on = True
        out[i] = int(on)
    return out
