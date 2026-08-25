"""Hypothèses d'alpha PRÉ-ENREGISTRÉES — paramètres figés a priori, jamais optimisés.

Le dépôt a déjà rejeté proprement une douzaine d'hypothèses directionnelles (DSR ≈ 0). Ce
module ne promet pas d'alpha : il fournit un banc d'essai HONNÊTE pour cinq hypothèses qui
ont un antécédent sérieux dans la littérature et qui n'ont pas encore été testées ici, avec
trois disciplines non négociables :

1. **Pré-enregistrement** : chaque hypothèse a UNE paramétrisation, écrite ici, choisie
   d'après la littérature et non d'après les données. Pas de grille, donc pas de sélection
   in-sample déguisée.
2. **Exécution décalée** : le score se calcule au close t, l'exécution est au close t+1
   (`exec_lag=1` par défaut — le défaut inverse du preset est un mini look-ahead, finding F4).
3. **Coûts sur |Δposition|**, par classe d'actifs, à chaque rebalancement.

Les cinq hypothèses :
  H1 momentum 12-1        (Jegadeesh-Titman) — CONTRÔLE : c'est le facteur de référence
  H2 momentum RÉSIDUEL    (Blitz-Huij-Martens) — momentum sur rendements résidualisés
  H3 basse vol idiosync.  (Ang et al.) — l'anomalie IVOL, distincte du low-vol total
  H4 reversal 5j GATÉ     (Lehmann/Lo-MacKinlay) — avec test d'admission alpha vs coût
  H5 proximité plus-haut  (George-Hwang) — distance au plus haut 52 semaines

H2 est celle qui vaut le détour : elle utilise l'orthogonalisation livrée en M1/M3, et sa
comparaison à H1 est un test propre — si le résidualisé ne bat pas le brut, c'est un négatif
publiable, pas un échec.

numpy pur. `A` = matrice n × L de prix (lignes = actifs, colonnes = dates), déjà alignée.
"""

from __future__ import annotations

import numpy as np

from packages.ranking.orthogonalize import robust_z

# --- PRÉ-ENREGISTREMENT : ces valeurs ne doivent JAMAIS être ajustées sur les résultats ---
PRE_REGISTERED: dict[str, dict] = {
    "H1_momentum_12_1": {"lookback": 252, "skip": 21},
    "H2_momentum_residuel": {"lookback": 252, "skip": 21, "n_factors": 3,
                             "window": 252},   # window = fenêtre d'ENTRAÎNEMENT antérieure
    "H3_low_ivol": {"window": 60, "n_factors": 3},
    "H4_reversal_5j": {"lookback": 5, "min_alpha_bps": 0.0},   # seuil réglé par le coût réel
    "H5_proximite_52w": {"window": 252},
}
STEP = 21               # rebalancement mensuel — horizon compatible avec des coûts retail
TOP_FRAC = 0.20         # quintiles : assez de noms pour diversifier, assez tranché pour scorer
MAX_WEIGHT = 0.10


def _returns(A: np.ndarray) -> np.ndarray:
    return A[:, 1:] / np.where(A[:, :-1] == 0, np.nan, A[:, :-1]) - 1.0


def _loadings(R_train: np.ndarray, n_factors: int) -> np.ndarray | None:
    """Loadings factoriels (n × k) estimés par ACP sur une fenêtre d'ENTRAÎNEMENT."""
    X = np.nan_to_num(R_train)
    X = X - X.mean(axis=1, keepdims=True)
    if X.shape[0] < 3 or X.shape[1] < 20 or n_factors <= 0:
        return None
    try:
        U, S, _ = np.linalg.svd(X, full_matrices=False)
    except np.linalg.LinAlgError:
        return None
    return U[:, :min(n_factors, S.size)]


def _residualize_oos(R_train: np.ndarray, R_score: np.ndarray,
                     n_factors: int) -> np.ndarray:
    """Résidus HORS ÉCHANTILLON : loadings appris sur `R_train`, appliqués à `R_score`.

    ⚠️ Résidualiser sur la fenêtre où l'on MESURE ensuite le momentum induit un retour à la
    moyenne MÉCANIQUE : retirer des composantes ajustées sur les mêmes points rend le résidu
    cumulé anti-persistant par construction, et le signal devient contrarian sans qu'aucune
    information de marché n'intervienne. Mesuré sur panel sans alpha : Sharpe brut −0,68
    avant correction, ≈ 0 après. C'est la même faute que résidualiser un alpha sur des
    facteurs estimés plein-échantillon, à une échelle plus discrète.
    """
    X = np.nan_to_num(R_score)
    X = X - X.mean(axis=1, keepdims=True)
    B = _loadings(R_train, n_factors)
    if B is None or X.shape[1] < 5:
        return X
    f = np.linalg.pinv(B) @ X                      # rendements factoriels implicites
    return X - B @ f


def h1_momentum(A: np.ndarray, t: int, lookback: int = 252, skip: int = 21) -> np.ndarray:
    """Momentum 12-1 : rendement de t−lookback à t−skip (le mois récent est EXCLU)."""
    i0, i1 = t - lookback, t - skip
    if i0 < 0 or i1 <= i0:
        return np.full(A.shape[0], np.nan)
    return A[:, i1] / np.where(A[:, i0] == 0, np.nan, A[:, i0]) - 1.0


def h2_momentum_residuel(A: np.ndarray, t: int, lookback: int = 252, skip: int = 21,
                         n_factors: int = 3, window: int = 252) -> np.ndarray:
    """Momentum sur rendements RÉSIDUELS : le momentum du titre, pas celui de son secteur.

    On résidualise les rendements sur les premières composantes principales de la fenêtre,
    puis on cumule le résidu sur la même période que H1. Standardisé par la volatilité
    résiduelle (Blitz-Huij-Martens) — ce qui compte est la régularité, pas l'amplitude.
    """
    i0, i1 = t - lookback, t - skip
    if i0 < 1 or i1 <= i0 or i0 - window < 1:
        return np.full(A.shape[0], np.nan)
    R_train = _returns(A[:, i0 - window:i0])            # fenêtre ANTÉRIEURE à la mesure
    R_score = _returns(A[:, i0:i1 + 1])
    if R_score.shape[1] < 20:
        return np.full(A.shape[0], np.nan)
    E = _residualize_oos(R_train, R_score, n_factors)
    sd = E.std(axis=1, ddof=1)
    return np.where(sd > 0, E.sum(axis=1) / np.where(sd > 0, sd, np.nan), np.nan)


def h3_low_ivol(A: np.ndarray, t: int, window: int = 60, n_factors: int = 3) -> np.ndarray:
    """Anomalie de volatilité IDIOSYNCRATIQUE : score = −écart-type du résidu (bas = bon)."""
    if t - 2 * window < 1:
        return np.full(A.shape[0], np.nan)
    R_train = _returns(A[:, t - 2 * window:t - window])   # loadings hors échantillon
    R_score = _returns(A[:, t - window:t])
    if R_score.shape[1] < 10:
        return np.full(A.shape[0], np.nan)
    return -_residualize_oos(R_train, R_score, n_factors).std(axis=1, ddof=1)


def h4_reversal(A: np.ndarray, t: int, lookback: int = 5, **_) -> np.ndarray:
    """Retour à la moyenne court terme : score = −rendement des `lookback` derniers jours."""
    if t - lookback < 0:
        return np.full(A.shape[0], np.nan)
    return -(A[:, t] / np.where(A[:, t - lookback] == 0, np.nan, A[:, t - lookback]) - 1.0)


def h5_proximite_52w(A: np.ndarray, t: int, window: int = 252) -> np.ndarray:
    """Proximité au plus haut 52 semaines : prix / plus-haut. Proche de 1 = fort."""
    i0 = max(0, t - window)
    hi = np.nanmax(A[:, i0:t + 1], axis=1)
    return np.where(hi > 0, A[:, t] / np.where(hi > 0, hi, np.nan), np.nan)


SIGNALS = {"H1_momentum_12_1": h1_momentum, "H2_momentum_residuel": h2_momentum_residuel,
           "H3_low_ivol": h3_low_ivol, "H4_reversal_5j": h4_reversal,
           "H5_proximite_52w": h5_proximite_52w}


def _weights(score: np.ndarray, long_only: bool, top_frac: float,
             max_weight: float) -> np.ndarray:
    """Quintiles extrêmes, pondérés par le z robuste, dollar-neutres (ou long-only)."""
    z = robust_z(np.where(np.isfinite(score), score, np.nan))
    valid = np.isfinite(score)
    if valid.sum() < 10:
        return np.zeros_like(z)
    k = max(1, int(round(valid.sum() * top_frac)))
    ordre = np.argsort(np.where(valid, z, -np.inf))
    longs, shorts = ordre[-k:], ordre[:k]
    w = np.zeros_like(z)
    w[longs] = np.abs(z[longs]) + 1e-9
    s = w[longs].sum()
    w[longs] = w[longs] / s * (1.0 if long_only else 0.5)
    if not long_only:
        w[shorts] = -(np.abs(z[shorts]) + 1e-9)
        w[shorts] = w[shorts] / abs(w[shorts].sum()) * 0.5
    return np.clip(w, -max_weight, max_weight)


def benchmark_equipondere(A: np.ndarray, step: int = STEP, cost_rt_bps: float = 10.0,
                          exec_lag: int = 1) -> dict:
    """Détention équipondérée de l'UNIVERS, sur la même grille et avec les mêmes coûts.

    C'est le point de comparaison qui manquait aux hypothèses long-only : sans lui, un Sharpe de
    1,70 sur une période haussière se lit comme de l'alpha alors qu'il peut n'être que du bêta.
    Même `start`, même `step`, même `exec_lag` que `cross_sectional_backtest` — sinon les deux
    séries ne sont pas comparables et l'écart mesuré serait un artefact de calendrier."""
    n, L = A.shape
    start = 520
    if L < start + 3 * step:
        return {"available": False, "status": "UNCALIBRATED", "L": int(L)}
    w = np.full(n, 1.0 / n)
    prev = np.zeros(n)
    rets, turn = [], 0.0
    for t in range(start, L - 1 - exec_lag, step):
        entry = min(t + exec_lag, L - 1)
        nxt = min(entry + step, L - 1)
        fwd = A[:, nxt] / np.where(A[:, entry] == 0, np.nan, A[:, entry]) - 1.0
        fwd = np.nan_to_num(fwd)
        cout = float(np.abs(w - prev).sum()) * cost_rt_bps / 1e4
        rets.append(float((w * fwd).sum()) - cout)
        turn += float(np.abs(w - prev).sum())
        prev = w
    if len(rets) < 8:
        return {"available": False, "status": "UNCALIBRATED", "n_steps": len(rets)}
    r = np.asarray(rets)
    per_year = 252.0 / step
    sd = float(r.std(ddof=1))
    eq = np.cumprod(1 + r)
    return {"available": True, "returns": r, "n_steps": int(r.size),
            "sharpe": round(float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0, 3),
            "annualized": round(float(eq[-1] ** (per_year / r.size) - 1), 4),
            "max_drawdown": round(float((eq / np.maximum.accumulate(eq) - 1).min()), 4),
            "turnover_annual": round(turn / r.size * per_year, 2), "step": step}


def cross_sectional_backtest(A: np.ndarray, name: str, long_only: bool = False,
                             step: int = STEP, cost_rt_bps: float = 10.0,
                             exec_lag: int = 1, top_frac: float = TOP_FRAC,
                             max_weight: float = MAX_WEIGHT,
                             shuffle_seed: int | None = None) -> dict:
    """Backtest transversal d'une hypothèse pré-enregistrée. Renvoie la série de rendements.

    `shuffle_seed` : permute le score EN COUPE à chaque date → **placebo**. La structure
    temporelle et les coûts sont conservés, seule l'information de classement est détruite.
    C'est le seul placebo qui teste vraiment le signal et non l'univers.
    """
    if name not in SIGNALS:
        raise KeyError(f"hypothèse inconnue : {name}")
    fn, params = SIGNALS[name], PRE_REGISTERED[name]
    n, L = A.shape
    start = 520          # H2/H3 exigent une fenêtre d'entraînement ANTÉRIEURE
    if L < start + 3 * step:
        return {"available": False, "status": "UNCALIBRATED", "L": int(L)}
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    prev = np.zeros(n)
    rets, turn = [], 0.0
    for t in range(start, L - 1 - exec_lag, step):
        score = fn(A, t, **params)
        if rng is not None:
            fini = np.isfinite(score)
            vals = score[fini].copy()
            rng.shuffle(vals)
            score = score.copy()
            score[fini] = vals
        w = _weights(score, long_only, top_frac, max_weight)
        entry = min(t + exec_lag, L - 1)
        nxt = min(entry + step, L - 1)
        fwd = A[:, nxt] / np.where(A[:, entry] == 0, np.nan, A[:, entry]) - 1.0
        fwd = np.nan_to_num(fwd)
        cout = float(np.abs(w - prev).sum()) * cost_rt_bps / 1e4
        rets.append(float((w * fwd).sum()) - cout)
        turn += float(np.abs(w - prev).sum())
        prev = w
    if len(rets) < 8:
        return {"available": False, "status": "UNCALIBRATED", "n_steps": len(rets)}
    r = np.asarray(rets)
    per_year = 252.0 / step
    sd = float(r.std(ddof=1))
    eq = np.cumprod(1 + r)
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    return {"available": True, "returns": r, "n_steps": int(r.size),
            "sharpe": round(float(r.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0, 3),
            "annualized": round(float(eq[-1] ** (per_year / r.size) - 1), 4),
            "max_drawdown": round(dd, 4),
            "turnover_annual": round(turn / r.size * per_year, 2),
            "long_only": long_only, "step": step, "exec_lag": exec_lag}
