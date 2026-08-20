"""Orthogonalisation des signaux — isoler l'alpha idiosyncratique (Paleologo).

`ranking/engine.py` neutralise par démoyennage sectoriel. C'est le niveau 1 : il retire la
MOYENNE du secteur, pas l'EXPOSITION au marché, à la taille, à la value ou au momentum. Un
screener qui s'arrête là classe des bêtas et les appelle alpha.

Trois outils, du plus simple au plus juste :
  - `robust_z`      : standardisation résistante aux queues épaisses (médiane/MAD) ;
  - `qr_orthogonalize` : résidualisation SÉQUENTIELLE de signaux (Gram-Schmidt via QR,
                     numériquement stable — ne jamais coder Gram-Schmidt à la main) ;
  - `neutralize`    : PROJECTION de l'alpha orthogonalement aux loadings factoriels,
                     dans une métrique de pondération W.

Piège central : neutraliser l'alpha ne neutralise PAS le portefeuille. Si l'optimiseur en
aval utilise une covariance qui contient les mêmes facteurs, il réintroduira les
expositions. La contrainte doit être posée DANS l'optimiseur : |B' w| <= epsilon.
`factor_exposure` sert précisément à le vérifier après coup.

numpy pur.
"""

from __future__ import annotations

import numpy as np

_MAD_TO_SIGMA = 0.6744897501960817          # quantile normal à 75 % : MAD → écart-type


def robust_z(values, clip: float = 3.0) -> np.ndarray:
    """z robuste = 0,6745·(x − médiane)/MAD, écrêté. NaN → 0 (neutre)."""
    x = np.asarray(values, dtype=float)
    finite = np.isfinite(x)
    if finite.sum() < 2:
        return np.zeros_like(x)
    v = x[finite]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    scale = mad / _MAD_TO_SIGMA if mad > 0 else float(v.std(ddof=1))
    out = np.zeros_like(x)
    if scale <= 0:
        return out
    out[finite] = np.clip((v - med) / scale, -clip, clip)
    return out


def group_z(values, groups, min_size: int = 10, clip: float = 3.0) -> np.ndarray:
    """z robuste INTRA-GROUPE, avec repli global sous `min_size`.

    Un groupe de deux noms produit mécaniquement ±1 : du bruit promu en signal. Le repli
    n'est pas une commodité, c'est ce qui empêche de fabriquer de l'information.
    """
    x = np.asarray(values, dtype=float)
    g = np.asarray(groups)
    out = robust_z(x, clip)
    for key in np.unique(g):
        m = g == key
        if m.sum() >= min_size:
            out[m] = robust_z(x[m], clip)
    return out


def qr_orthogonalize(signals) -> np.ndarray:
    """Résidualisation séquentielle de signaux (n × K, colonnes = signaux, ordre = priorité).

    Renvoie des colonnes orthogonales de même échelle que les originales. **L'ordre est un
    choix** : la première colonne conserve toute la variance partagée. Ce choix relève d'un
    ADR, jamais d'une boucle implicite.

    Les colonnes sont CENTRÉES au préalable — sans cela l'orthogonalité au sens du produit
    scalaire ne coïncide pas avec la décorrélation, et « résidualiser » laisserait passer la
    composante constante (équivalent d'une régression sans constante).
    """
    S = np.asarray(signals, dtype=float)
    if S.ndim != 2 or S.shape[0] < 2:
        return S
    S = np.nan_to_num(S)
    S = S - S.mean(axis=0, keepdims=True)
    Q, R = np.linalg.qr(S)
    scale = np.sign(np.diag(R)) * np.linalg.norm(S, axis=0)
    return Q * scale


def neutralize(alpha, loadings, weights=None) -> np.ndarray:
    """alpha_resid = alpha − B·(B'WB)⁻¹·B'W·alpha  (projection W-orthogonale aux facteurs).

    `loadings` : n × K (bêta marché, taille, value, momentum, indicatrices sectorielles…).
    `weights` : vecteur de pondération n (inverse de la variance spécifique, ou racine de
    capitalisation). None = pondération uniforme.
    """
    a = np.nan_to_num(np.asarray(alpha, dtype=float))
    B = np.nan_to_num(np.asarray(loadings, dtype=float))
    if B.ndim == 1:
        B = B.reshape(-1, 1)
    if B.shape[0] != a.size or B.shape[1] == 0:
        return a
    w = np.ones(a.size) if weights is None else np.clip(
        np.nan_to_num(np.asarray(weights, dtype=float)), 1e-12, None)
    BW = B.T * w
    G = BW @ B
    try:
        coef = np.linalg.solve(G + 1e-12 * np.eye(G.shape[0]), BW @ a)
    except np.linalg.LinAlgError:
        coef = np.linalg.pinv(G) @ (BW @ a)
    return a - B @ coef


def factor_exposure(vector, loadings, weights=None) -> np.ndarray:
    """B'W·v — expositions factorielles d'un alpha OU d'un vecteur de poids.

    Appliqué aux POIDS RÉELS après optimisation, c'est le contrôle qui prouve que la
    neutralisation a survécu à l'optimiseur.
    """
    v = np.nan_to_num(np.asarray(vector, dtype=float))
    B = np.nan_to_num(np.asarray(loadings, dtype=float))
    if B.ndim == 1:
        B = B.reshape(-1, 1)
    w = np.ones(v.size) if weights is None else np.asarray(weights, dtype=float)
    return (B.T * w) @ v


def combine_signals(z_matrix, ics, corr=None, shrink: float = 0.2) -> dict:
    """Combinaison optimale : w ∝ Omega⁻¹·ic, IC_combiné = √(ic'·Omega⁻¹·ic).

    `Omega` = corrélation DES SIGNAUX entre eux (estimée si None). La moyenne pondérée à la
    main correspond à Omega = I, c'est-à-dire à l'hypothèse que momentum et trend ne se
    ressemblent pas — fausse. Le rétrécissement de Omega vers l'identité n'est pas une
    précaution : c'est la condition de stabilité hors échantillon.
    """
    Z = np.nan_to_num(np.asarray(z_matrix, dtype=float))   # n × K
    ic = np.asarray(ics, dtype=float)
    k = Z.shape[1]
    if ic.size != k or k == 0:
        return {"available": False}
    O = np.corrcoef(Z, rowvar=False) if corr is None else np.asarray(corr, dtype=float)
    O = np.atleast_2d(np.nan_to_num(O, nan=0.0))
    if O.shape != (k, k):
        O = np.eye(k)
    O = (1.0 - shrink) * O + shrink * np.eye(k)
    inv = np.linalg.pinv(O)
    w = inv @ ic
    s = np.abs(w).sum()
    w = w / s if s > 0 else w
    ic_comb = float(np.sqrt(max(0.0, ic @ inv @ ic)))
    return {"available": True, "weights": w, "ic_combined": round(ic_comb, 4),
            "ic_naive_sum": round(float(np.sqrt((ic ** 2).sum())), 4),
            "score": Z @ w, "shrink": shrink}
