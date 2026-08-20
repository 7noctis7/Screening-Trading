"""Débruitage de la covariance par théorie des matrices aléatoires (Marčenko-Pastur).

Problème : avec n actifs et T observations, la covariance empirique a un rapport n/T qui
détermine sa fiabilité. Pour n/T proche de 1, la MAJORITÉ des valeurs propres est du pur
bruit — et l'optimiseur (moyenne-variance, ERC, min-var) charge précisément les directions
de plus petite valeur propre, c'est-à-dire les mieux estimées par le hasard. D'où
l'explosion des poids et le turnover.

Marčenko-Pastur : pour une matrice de corrélation de VARIABLES INDÉPENDANTES, le spectre
converge vers un support borné

    lambda_± = sigma² · ( 1 ± sqrt(n/T) )²

Toute valeur propre à l'intérieur de [lambda_−, lambda_+] est indistinguable du bruit.
La procédure (López de Prado, *Machine Learning for Asset Managers*, ch. 2) :

  1. passer en CORRÉLATION (trace = n, indispensable : la loi MP est adimensionnelle) ;
  2. estimer sigma² du bruit par point fixe (le bulk doit contenir n − k valeurs propres) ;
  3. garder les k valeurs propres > lambda_+ (les VRAIS facteurs) ;
  4. remplacer les n − k autres par leur MOYENNE — « constant residual eigenvalue »,
     qui préserve la trace, donc la variance totale, et rend la matrice bien conditionnée ;
  5. revenir en covariance, puis appliquer le shrinkage de Ledoit-Wolf par-dessus.

Débruitage et shrinkage ne s'opposent pas : le premier corrige la STRUCTURE du spectre,
le second contracte vers une cible. L'ordre correct est débruiter PUIS contracter.

Numpy pur, testable hors-ligne.
"""

from __future__ import annotations

import numpy as np


def mp_edges(n: int, t: int, sigma2: float = 1.0) -> tuple[float, float]:
    """Bornes du support de Marčenko-Pastur : (lambda_moins, lambda_plus)."""
    if n <= 0 or t <= 0:
        return (0.0, 0.0)
    q = n / t
    root = np.sqrt(q)
    return (float(sigma2 * (1.0 - root) ** 2), float(sigma2 * (1.0 + root) ** 2))


def spectral_gap_k(eigvals, k_max: int) -> int:
    """k retenu par le plus grand écart RELATIF lambda_i / lambda_(i+1), borné par `k_max`.

    Complément indispensable au seuil MP : quand quelques facteurs absorbent l'essentiel de
    la trace, les variances idiosyncratiques deviennent hétérogènes, le bulk s'élargit
    au-delà du support MP et le seuil SUR-DÉTECTE. L'écart spectral, lui, reste net.
    """
    lam = np.sort(np.asarray(eigvals, dtype=float))[::-1]
    kmax = int(min(max(k_max, 0), lam.size - 1))
    if kmax <= 0:
        return 0
    ratios = [lam[i] / max(lam[i + 1], 1e-12) for i in range(kmax)]
    return int(np.argmax(ratios)) + 1


def n_signal_eigenvalues(eigvals, n: int, t: int, max_iter: int = 20) -> dict:
    """Nombre k de facteurs distinguables du bruit : seuil MP, puis écart spectral.

    sigma² n'est pas 1 dès qu'il existe de vrais facteurs : ils absorbent une part de la
    trace. On itère : k_mp = #{lambda > lambda_+(sigma²)} puis sigma² = moyenne du bulk.
    `k_mp` est une BORNE SUPÉRIEURE (elle sur-détecte sous hétérogénéité) ; `k` retenu est
    l'écart spectral le plus marqué en deçà de cette borne.
    """
    lam = np.sort(np.asarray(eigvals, dtype=float))[::-1]
    lam = np.clip(lam, 0.0, None)
    if lam.size == 0 or t <= 1:
        return {"available": False}
    sigma2, k = 1.0, 0
    for _ in range(max_iter):
        _, hi = mp_edges(n, t, sigma2)
        k_new = int((lam > hi).sum())
        k_new = min(k_new, n - 1)                    # au moins une v.p. dans le bulk
        bulk = lam[k_new:]
        s_new = float(bulk.mean()) if bulk.size else sigma2
        if k_new == k and abs(s_new - sigma2) < 1e-10:
            k, sigma2 = k_new, s_new
            break
        k, sigma2 = k_new, s_new
    lo, hi = mp_edges(n, t, sigma2)
    k_gap = spectral_gap_k(lam, k)
    return {"available": True, "k": int(k_gap), "k_mp": int(k), "sigma2": round(sigma2, 6),
            "lambda_plus": round(hi, 6), "lambda_minus": round(lo, 6),
            "q": round(n / t, 4), "eigenvalues": [round(float(x), 6) for x in lam[:10]]}


def _corr_from_cov(cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    std = np.sqrt(np.clip(np.diag(cov), 1e-300, None))
    return cov / np.outer(std, std), std


def denoise_corr(corr: np.ndarray, t: int) -> dict:
    """Débruite une matrice de CORRÉLATION par valeur propre résiduelle constante."""
    C = np.asarray(corr, dtype=float)
    n = C.shape[0]
    if n < 2 or t < 2:
        return {"available": False}
    vals, vecs = np.linalg.eigh(C)
    order = np.argsort(vals)[::-1]
    vals, vecs = np.clip(vals[order], 0.0, None), vecs[:, order]
    diag = n_signal_eigenvalues(vals, n, t)
    if not diag.get("available"):
        return {"available": False}
    k = diag["k"]
    new = vals.copy()
    if k < n:
        new[k:] = float(vals[k:].sum() / (n - k))    # préserve la trace = n
    C2 = vecs @ np.diag(new) @ vecs.T
    d = np.sqrt(np.clip(np.diag(C2), 1e-300, None))  # re-normalise la diagonale à 1
    C2 = C2 / np.outer(d, d)
    return {"available": True, "corr": C2, "k": k, "k_mp": diag["k_mp"], "n": n, "t": int(t),
            "sigma2": diag["sigma2"], "lambda_plus": diag["lambda_plus"],
            "cond_before": round(float(vals[0] / max(vals[-1], 1e-12)), 2),
            "cond_after": round(float(new[0] / max(new[-1], 1e-12)), 2)}


def detone(corr: np.ndarray, n_factors: int = 1) -> np.ndarray:
    """Retire les `n_factors` premières composantes (le « ton du marché »).

    À réserver au CLUSTERING et aux études de structure : sur une matrice détonée, la
    corrélation moyenne chute et un optimiseur y verrait une diversification qui n'existe
    pas. Ne JAMAIS dimensionner un portefeuille sur une matrice détonée.
    """
    C = np.asarray(corr, dtype=float)
    n = C.shape[0]
    vals, vecs = np.linalg.eigh(C)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    k = max(0, min(int(n_factors), n - 1))
    Cd = C - vecs[:, :k] @ np.diag(vals[:k]) @ vecs[:, :k].T
    d = np.sqrt(np.clip(np.diag(Cd), 1e-300, None))
    return Cd / np.outer(d, d)


def effective_rank(eigvals) -> float:
    """Rang effectif (entropie spectrale) : nombre de directions réellement portées."""
    lam = np.clip(np.asarray(eigvals, dtype=float), 0.0, None)
    s = lam.sum()
    if s <= 0:
        return 0.0
    p = lam / s
    p = p[p > 0]
    return float(np.exp(-(p * np.log(p)).sum()))


def denoise_covariance(returns_matrix, shrink: bool = True) -> dict:
    """Chaîne complète : covariance empirique → débruitage MP → shrinkage Ledoit-Wolf.

    `returns_matrix` : n × T (lignes = actifs). Renvoie la covariance stabilisée et le
    diagnostic complet — c'est ce diagnostic, pas la matrice, qui dit si l'échantillon
    autorise une optimisation : q = n/T > 0,5 et k = 1 signifie « une seule direction
    fiable », donc aucune optimisation transversale n'a de sens.
    """
    A = np.asarray(returns_matrix, dtype=float)
    if A.ndim != 2 or A.shape[0] < 2 or A.shape[1] < 3:
        return {"available": False}
    n, t = A.shape
    cov = np.cov(A)
    corr, std = _corr_from_cov(cov)
    den = denoise_corr(corr, t)
    if not den.get("available"):
        return {"available": False}
    cov_out = den["corr"] * np.outer(std, std)
    delta = None
    if shrink:
        try:
            from packages.data.engine import ledoit_wolf_shrinkage
            _, delta = ledoit_wolf_shrinkage(A)          # intensité mesurée sur les données
            corr_t = np.full((n, n), float(np.mean(den["corr"][~np.eye(n, dtype=bool)])))
            np.fill_diagonal(corr_t, 1.0)
            cov_out = ((1 - delta) * den["corr"] + delta * corr_t) * np.outer(std, std)
        except Exception:                                # noqa: BLE001 — shrinkage optionnel
            delta = None
    vals = np.linalg.eigvalsh(cov_out)[::-1]
    return {"available": True, "cov": cov_out, "n": n, "t": t,
            "q": round(n / t, 4), "k_signal": den["k"], "k_mp": den["k_mp"],
            "sigma2_noise": den["sigma2"],
            "lambda_plus": den["lambda_plus"],
            "cond_before": den["cond_before"], "cond_after": den["cond_after"],
            "effective_rank": round(effective_rank(vals), 2),
            "lw_delta": (round(float(delta), 4) if delta is not None else None),
            "verdict": ("OK" if den["k"] >= 2 and n / t < 0.5 else
                        "FRAGILE — échantillon trop court ou une seule direction fiable")}
