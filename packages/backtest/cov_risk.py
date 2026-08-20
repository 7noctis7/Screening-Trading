"""Covariance du preset : estimation, DIAGNOSTIC d'exploitabilité, variante débruitée (RMT).

Extrait de `preset_backtest.py` (qui dépassait le plafond de 400 lignes) et enrichi.

Trois fonctions, une seule porte d'entrée (`cov_for_step`) partagée par le rail backtest et
le rail production, pour qu'ils ne puissent pas diverger.

**Le diagnostic est TOUJOURS calculé, le débruitage jamais par défaut.** C'est délibéré :
on veut d'abord savoir si le preset optimise du signal ou du bruit, sans rien changer aux
chiffres publiés. Le diagnostic est purement observationnel ; seul `denoise=True` modifie
la covariance renvoyée.

Dégradation honnête : quand moins de 2 directions sont distinguables du bruit
(cf. `packages/portfolio/rmt_denoise.py`), une optimisation transversale n'a pas de sens —
on retombe sur une covariance DIAGONALE, ce qui transforme l'ERC en pondération
inverse-volatilité. C'est ce que la matrice permet réellement d'affirmer, ni plus ni moins.
"""

from __future__ import annotations

import numpy as np


def cov_annual(win: np.ndarray) -> np.ndarray:
    """Covariance annualisée, shrinkée Ledoit-Wolf si disponible (comportement historique)."""
    if win.shape[0] == 1:
        return np.array([[float(win.var()) * 252]])
    try:                                                        # #3 Ledoit-Wolf : covariance shrinkée
        from packages.data.engine import ledoit_wolf_shrinkage  # (n×T) → Σ stabilisée
        cov, _ = ledoit_wolf_shrinkage(win)
        return cov * 252
    except Exception:  # noqa: BLE001 — repli covariance empirique si indispo
        return np.cov(win) * 252


def cov_diag_annual(win: np.ndarray) -> np.ndarray:
    """Covariance DIAGONALE annualisée : volatilités seules, aucune corrélation estimée."""
    var = np.atleast_1d(np.asarray(win, dtype=float).var(axis=1)) * 252
    return np.diag(np.clip(var, 1e-12, None))


def cov_diagnostic(win: np.ndarray) -> dict:
    """Nombre de directions exploitables (RMT) + q = n/T. Ne lève jamais."""
    A = np.asarray(win, dtype=float)
    n, t = (A.shape if A.ndim == 2 else (1, A.size))
    out = {"n": int(n), "t": int(t), "q": round(n / t, 4) if t else None}
    if n < 2 or t < 3:
        return {**out, "k_signal": int(n), "available": False}
    try:
        from packages.portfolio.rmt_denoise import denoise_covariance
        d = denoise_covariance(A, shrink=False)
        if not d.get("available"):
            return {**out, "k_signal": int(n), "available": False}
        return {**out, "available": True, "k_signal": d["k_signal"], "k_mp": d["k_mp"],
                "effective_rank": d["effective_rank"], "cond_before": d["cond_before"],
                "cond_after": d["cond_after"], "cov": d["cov"]}
    except Exception:  # noqa: BLE001 — diagnostic optionnel, jamais bloquant
        return {**out, "k_signal": int(n), "available": False}


def cov_for_step(win: np.ndarray, denoise: bool = False,
                 min_k: int = 2) -> tuple[np.ndarray, dict, bool]:
    """Porte d'entrée unique. Renvoie (covariance, diagnostic, dégradée ?).

    `denoise=False` (défaut) : covariance historique, diagnostic observationnel seulement —
    les chiffres publiés sont inchangés au bit près.
    `denoise=True` : covariance débruitée par RMT, et repli DIAGONAL si moins de `min_k`
    directions sont distinguables du bruit.
    """
    try:                            # un diagnostic KO ne doit JAMAIS casser un backtest
        diag = cov_diagnostic(win)
    except Exception:  # noqa: BLE001
        diag = {"available": False}
    cov_rmt = diag.pop("cov", None)
    if not denoise:
        return cov_annual(win), diag, False
    if not diag.get("available") or cov_rmt is None:
        return cov_annual(win), diag, False
    if int(diag.get("k_signal", 0)) < min_k:
        return cov_diag_annual(win), diag, True
    return cov_rmt * 252, diag, False


def summarize(diags: list[dict], n_degraded: int, denoised: bool) -> dict:
    """Agrège les diagnostics d'un backtest — la réponse à « signal ou bruit ? »."""
    ks = [d["k_signal"] for d in diags if d.get("k_signal") is not None]
    qs = [d["q"] for d in diags if d.get("q") is not None]
    if not ks:
        return {"available": False}
    return {"available": True, "denoised": bool(denoised), "n_steps": len(ks),
            "k_signal_median": float(np.median(ks)),
            "k_signal_min": int(min(ks)), "k_signal_max": int(max(ks)),
            "q_median": round(float(np.median(qs)), 4) if qs else None,
            "n_degraded": int(n_degraded),
            "degraded_pct": round(100.0 * n_degraded / len(ks), 1),
            "verdict": ("covariance exploitable" if float(np.median(ks)) >= 2
                        else "UNE SEULE DIRECTION FIABLE — l'optimisation transversale "
                             "range du bruit ; préférer l'inverse-vol")}
