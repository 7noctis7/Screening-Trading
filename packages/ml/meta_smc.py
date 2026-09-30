"""Méta-labellisation du signal SMCLXTP-A — le ML ne choisit pas le SENS, il FILTRE.

Chaîne de López de Prado (AFML ch. 3 et 7), chaque maillon réutilisant le dépôt :
  1. ÉVÉNEMENTS : barres où `long_signal` de SMCLXTP-A (causal) est vrai ;
  2. LABELS : triple barrière en multiples d'ATR — gain à k_tp·ATR, perte à k_sl·ATR,
     horizon H (`ml.labeling.triple_barrier`, vol = ATR/close). Méta-label = 1 si le long
     a rapporté plus qu'un aller-retour de frais. Un événement dont l'horizon dépasse les
     données est ÉCARTÉ : pas d'étiquette sur un avenir incomplet ;
  3. FEATURES à t, sans unité de prix : ratio de zone SMC, (close − SMA20)/ATR, z-score
     du RSI(14) sur 100 barres, ATR/close, rendement 5 barres / ATR, distances au dernier
     sommet et au dernier creux CONFIRMÉS, en ATR ;
  4. VALIDATION : `PurgedKFold` (embargo ≥ horizon, bornes en jours calendaires), AUC par
     pli, distribution NULLE par permutation des labels (`validation_edge.edge_detecte`) ;
  5. SEUIL : seulement si l'edge est établi. Ajusté sur la 1re moitié CHRONOLOGIQUE des
     probabilités hors échantillon, jugé sur la 2de. Jamais « 0,65 » posé par principe.

STATUT : SHADOW_UNCALIBRATED — aucun ordre n'en dépend ; `MetaFiltre.autorise` refuse
de répondre tant que le filtre n'est pas calibré.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from packages.indicators.registry import indicators
from packages.indicators.smc_lux_tp import calculer, dernier_connu

STATUT = "SHADOW_UNCALIBRATED"
FEATURES = ("smc_zone_ratio", "ecart_sma_atr", "rsi_z", "atr_rel", "rend5_atr",
            "dist_sommet_atr", "dist_creux_atr")
MIN_GARDES = 20


@dataclass(frozen=True)
class Reglages:
    """Conventions NON calibrées ; chaque variante mesurée est un essai au ledger."""

    swing_length: int = 50
    pivot_length: int = 50
    k_tp: float = 2.0
    k_sl: float = 1.0
    horizon: int = 20
    periode_atr: int = 14
    cout_ar: float = 0.001          # aller-retour : un gain plus petit n'est pas un gain
    n_plis: int = 5
    n_permutations: int = 50
    modele: str = "lightgbm"
    graine: int = 0
    min_evenements: int = 200


def auc(y, p) -> float:
    """AUC par les rangs (Mann-Whitney), égalités au rang moyen. NaN sans les 2 classes."""
    y, p = np.asarray(y, int), np.asarray(p, float)
    n1 = int(y.sum())
    n0 = y.size - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    _, inverse, effectifs = np.unique(p, return_inverse=True, return_counts=True)
    rangs = (np.cumsum(effectifs) - (effectifs - 1) / 2.0)[inverse]
    return float((rangs[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _serie(bars, nom: str, **kw) -> np.ndarray:
    return np.asarray(indicators.create(nom, **kw).compute(bars), float)


def _zscore_glissant(x: np.ndarray, n: int) -> np.ndarray:
    """(x_t − moyenne) / écart-type sur les n valeurs finissant en t (causal)."""
    from numpy.lib.stride_tricks import sliding_window_view as fenetres
    out = np.full(x.size, np.nan)
    if x.size < n:
        return out
    W = fenetres(x, n)
    m, sd = W.mean(axis=1), W.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[n - 1:] = np.where(sd > 0, (x[n - 1:] - m) / sd, np.nan)
    return out


def _calculs(bars, r: Reglages) -> tuple[dict, dict[str, np.ndarray]]:
    """(sorties SMCLXTP-A, features) — tout est lu sur les barres ≤ t."""
    c = np.array([b.close for b in bars], float)
    smc = calculer([b.high for b in bars], [b.low for b in bars], c,
                   swing_length=r.swing_length, pivot_length=r.pivot_length)
    atr = _serie(bars, "atr", period=r.periode_atr)
    sma, rsi = _serie(bars, "sma", period=20), _serie(bars, "rsi", period=14)
    rend5 = np.full(c.size, np.nan)
    rend5[5:] = c[5:] - c[:-5]
    with np.errstate(invalid="ignore", divide="ignore"):
        a = np.where(atr > 0, atr, np.nan)
        feats = {"smc_zone_ratio": smc["smc_zone_ratio"], "ecart_sma_atr": (c - sma) / a,
                 "rsi_z": _zscore_glissant(rsi, 100), "atr_rel": a / c,
                 "rend5_atr": rend5 / a,
                 "dist_sommet_atr": (dernier_connu(smc["swing_high"]) - c) / a,
                 "dist_creux_atr": (c - dernier_connu(smc["swing_low"])) / a}
    return smc, feats


def features(bars, r: Reglages | None = None) -> dict[str, np.ndarray]:
    return _calculs(bars, r or Reglages())[1]


def etiqueter(bars, idx, r: Reglages) -> tuple[np.ndarray, ...]:
    """(y, ret, t0, t1, garde), alignés sur `idx`. `garde` = étiquette observable."""
    from packages.ml.labeling import triple_barrier
    c = np.array([b.close for b in bars], float)
    atr = _serie(bars, "atr", period=r.periode_atr)
    idx = np.asarray(idx, int)
    garde = (idx + r.horizon <= c.size - 1) & np.isfinite(atr[idx]) & (atr[idx] > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        vol = np.where(np.isfinite(atr) & (atr > 0), atr / c, np.nan)
    labels = triple_barrier(c, idx[garde].tolist(), pt=r.k_tp, sl=r.k_sl, vol=vol,
                            horizon=r.horizon)
    y, ret = np.zeros(idx.size, int), np.full(idx.size, np.nan)
    t0, t1 = np.zeros(idx.size, int), np.zeros(idx.size, int)
    for k, lab in zip(np.flatnonzero(garde), labels, strict=True):
        ret[k], y[k] = lab.ret, int(lab.ret > r.cout_ar)
        t0[k], t1[k] = bars[lab.entry_idx].ts.toordinal(), bars[lab.exit_idx].ts.toordinal()
    return y, ret, t0, t1, garde


def evenements_etiquetes(bars, r: Reglages) -> dict[str, np.ndarray]:
    smc, feats = _calculs(bars, r)
    idx = np.flatnonzero(smc["long_signal"])
    X = np.column_stack([feats[k][idx] for k in FEATURES]) if idx.size else \
        np.empty((0, len(FEATURES)))
    fini = np.isfinite(X).all(axis=1)
    idx, X = idx[fini], X[fini]
    y, ret, t0, t1, garde = etiqueter(bars, idx, r)
    return {"X": X[garde], "y": y[garde], "ret": ret[garde], "t0": t0[garde],
            "t1": t1[garde]}


def echantillon(barres_par_symbole: dict, r: Reglages) -> dict[str, np.ndarray]:
    """Événements de tous les titres, TRIÉS dans le temps (la CV découpe par position)."""
    parts = [evenements_etiquetes(b, r) for b in barres_par_symbole.values() if b]
    parts = [p for p in parts if p["y"].size]
    if not parts:
        return {"X": np.empty((0, len(FEATURES))), "y": np.empty(0, int),
                "ret": np.empty(0), "t0": np.empty(0, int), "t1": np.empty(0, int)}
    e = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    ordre = np.argsort(e["t0"], kind="stable")
    return {k: v[ordre] for k, v in e.items()}


def _plis(X, y, splits, r: Reglages) -> tuple[list[float], np.ndarray]:
    from packages.ml.model import make_model
    p, aucs = np.full(y.size, np.nan), []
    for tr, te in splits:
        if np.unique(y[tr]).size < 2 or np.unique(y[te]).size < 2:
            continue
        p[te] = make_model(r.modele).fit(X[tr], y[tr]).predict_proba(X[te])
        aucs.append(auc(y[te], p[te]))
    return aucs, p


def valider(X, y, t0, t1, r: Reglages) -> dict:
    """AUC hors échantillon (CV purgée) contre la distribution NULLE des labels permutés."""
    from packages.ml.cv import PurgedKFold
    from packages.ml.validation_edge import edge_detecte
    cv = PurgedKFold(r.n_plis, 0.01, label_horizon=int(np.ceil(r.horizon * 1.5)))
    splits = [(tr, te) for tr, te in cv.split(t0, t1) if tr.size > 10]
    aucs, p_oof = _plis(X, y, splits, r)
    rng = np.random.default_rng(r.graine)
    nulles = []
    for _ in range(r.n_permutations):
        a = _plis(X, rng.permutation(y), splits, r)[0]
        nulles.append(float(np.mean(a)) if a else float("nan"))
    return {"edge": edge_detecte(aucs, nulles), "aucs": aucs, "proba_oof": p_oof,
            "n_plis": len(splits)}


def seuil_hors_echantillon(p, y, ret, grille=None, min_trades: int = MIN_GARDES) -> dict:
    """Seuil ajusté sur la 1re moitié chronologique, jugé sur la 2de — jamais sur la même."""
    p, y, ret = np.asarray(p, float), np.asarray(y, int), np.asarray(ret, float)
    ok = np.isfinite(p) & np.isfinite(ret)
    p, y, ret = p[ok], y[ok], ret[ok]
    mi = p.size // 2
    grille = np.round(np.arange(0.50, 0.81, 0.05), 2) if grille is None else grille
    cands = [(float(ret[:mi][p[:mi] > s].mean()), float(s)) for s in grille
             if (p[:mi] > s).sum() >= min_trades]
    if mi < 2 * min_trades or not cands:
        return {"disponible": False, "motif": f"moins de {min_trades} trades au-dessus "
                                              "de tout seuil sur la moitié d'ajustement"}
    seuil = max(cands)[1]
    g = p[mi:] > seuil
    ev = {"n_evalues": int(p.size - mi), "n_gardes": int(g.sum()),
          "rend_moyen_tous": float(ret[mi:].mean()), "taux_base": float(y[mi:].mean()),
          "rend_moyen_filtre": float(ret[mi:][g].mean()) if g.any() else float("nan"),
          "precision_filtre": float(y[mi:][g].mean()) if g.any() else float("nan")}
    return {"disponible": True, "seuil": seuil, "n_ajustement": mi, "evaluation": ev}


@dataclass(frozen=True)
class MetaFiltre:
    """Le filtre ne répond que s'il est CALIBRÉ : edge par permutation ET gain jugé hors
    de l'échantillon qui a fixé le seuil. Sinon il refuse, au lieu de laisser tout passer."""

    calibre: bool
    seuil: float | None
    motif: str

    @classmethod
    def depuis(cls, validation: dict, seuil: dict) -> MetaFiltre:
        if not validation["edge"].get("edge"):
            return cls(False, None, f"pas d'edge : {validation['edge'].get('motif')}")
        ev = seuil.get("evaluation") or {}
        gain = ev.get("rend_moyen_filtre", float("nan")) - ev.get("rend_moyen_tous", 0.0)
        if not seuil.get("disponible") or not gain > 0 or ev.get("n_gardes", 0) < MIN_GARDES:
            return cls(False, None, "le seuil n'améliore pas la moitié d'évaluation")
        return cls(True, float(seuil["seuil"]), "edge établi et gain hors échantillon")

    def autorise(self, proba: float) -> bool:
        if not self.calibre:
            raise RuntimeError(f"méta-filtre non calibré ({self.motif}) : aucune décision")
        return float(proba) > float(self.seuil)


def analyser(barres_par_symbole: dict, r: Reglages | None = None) -> dict:
    """Rapport complet : événements, edge, seuil, et si le filtre est utilisable."""
    r = r or Reglages()
    e = echantillon(barres_par_symbole, r)
    n = int(e["y"].size)
    base = {"statut_module": STATUT, "n_evenements": n,
            "taux_base": float(e["y"].mean()) if n else None,
            "rend_moyen": float(np.mean(e["ret"])) if n else None}
    if n < r.min_evenements:
        return {**base, "statut": "UNCALIBRATED", "filtre_utilisable": False,
                "motif": f"{n} événement(s) < {r.min_evenements}"}
    v = valider(e["X"], e["y"], e["t0"], e["t1"], r)
    s = seuil_hors_echantillon(v["proba_oof"], e["y"], e["ret"])
    f = MetaFiltre.depuis(v, s)
    return {**base, "statut": v["edge"]["statut"], "edge": v["edge"], "seuil": s,
            "filtre_utilisable": f.calibre, "motif": f.motif}
