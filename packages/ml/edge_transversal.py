"""Score ML d'edge en COUPE TRANSVERSALE : le titre face à ses pairs, à ~1 mois.

Sorti de `apps/api/snapshot.py` le 06/10 (l'entraînement d'un modèle n'a rien à faire
dans le module qui sert les pages). `snapshot._ml_section` et `make train` appellent
`section_ml` ; les diagnostics (calibration, conformal, méta-label, walk-forward,
dérive) vivent dans `edge_diagnostics`.

LE LABEL (changé deux fois le 06/10 : relatif net de frais, puis départ à
l'exécution — deux essais au registre). Avant : `c[t+H] > c[t]`, une direction
ABSOLUE, frais ignorés. Mélangé sur tout l'univers, ce label apprend surtout le bêta du
marché — dans un mois haussier presque tout monte — et ne dit rien du choix ENTRE les
titres, qui est le seul usage d'un score de sélection. Un +0,01 % y comptait comme un
gain alors que l'aller-retour coûte davantage. Désormais : le titre bat la MÉDIANE des
titres échantillonnés la même semaine calendaire, d'au moins le coût aller-retour
actions de `CostModel` — « meilleur que ses pairs, frais payés ». Le rendement court
du close de la séance SUIVANTE (prix d'exécution du rejeu) au close H séances plus
tard : jamais depuis le close qui a servi au signal.

Anti look-ahead : features point-in-time (clôtures ≤ t), labels purgés (CV purgée +
embargo, bornes en jours calendaires), modèle servi depuis un artefact daté.
"""

from __future__ import annotations

import numpy as np

H = 21                                  # horizon ~1 mois (profil moyen-long terme)
PAS = 5                                 # un échantillon tous les 5 jours par titre
MIN_ECHANTILLONS = 500
MAX_ECHANTILLONS = 60_000
# Toute modification des features OU du label change cette version : la clé de
# l'artefact en dépend ; un modèle de l'ancienne définition n'est plus servi.
VERSION_FEATURES = "2026-10-06/relatif-net-de-frais/depart-execution"
NOMS = ["momentum 1 mois", "momentum 3 mois", "tendance vs MM50", "RSI",
        "volatilité (ATR)", "momentum ajusté risque", "distance plus-haut 52 sem.",
        "reversal 5 j", "dérive post-choc (PEAD)", "régime de volatilité"]


def cout_aller_retour() -> float:
    """Coût aller-retour actions (fraction), barème unique de `CostModel`."""
    from packages.execution.costs import CostModel
    return CostModel.for_asset_class("equity").round_trip_bps / 1e4


def auc(scores, y) -> float | None:
    y = np.asarray(y, float)[np.argsort(scores)]
    n_pos, n = y.sum(), len(y)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = np.arange(1, n + 1)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def modele():
    """Gradient Boosting (sklearn) si disponible, sinon logit numpy."""
    try:
        from packages.ml.model import SklearnModel
        return SklearnModel(), "Gradient Boosting (sklearn)"
    except Exception:  # noqa: BLE001
        from packages.ml.model import LogitModel
        return LogitModel(epochs=400), "régression logistique (numpy)"


def importance(model, names, X, y):
    """Importance : native (arbres) sinon |poids| (logit) sinon uniforme."""
    pipe = getattr(model, "pipe", None)
    clf = getattr(pipe, "named_steps", {}).get("clf") if pipe is not None else None
    if clf is not None and hasattr(clf, "feature_importances_"):
        vals = [float(v) for v in clf.feature_importances_]
    elif getattr(model, "w", None) is not None:
        vals = [abs(float(v)) for v in model.w]
    else:
        vals = [1.0] * len(names)
    return sorted(zip(names, vals, strict=False), key=lambda kv: -kv[1])


def features_point(c, sma, rsi, atr, rets_c, t) -> list[float] | None:
    """Les 10 features à la date t, calculées sur des clôtures ≤ t uniquement."""
    if t < 60 or t >= len(c):
        return None
    if sma[t] != sma[t] or rsi[t] != rsi[t] or atr[t] != atr[t]:      # NaN
        return None
    vol = atr[t] / c[t] if c[t] else 0.0
    hi52 = c[max(0, t - 252):t + 1].max()
    # Proxy PEAD sans donnée payante : plus gros choc quotidien des 10 derniers jours.
    win = c[max(1, t - 10):t + 1]
    rr = win[1:] / win[:-1] - 1 if len(win) > 1 else None
    gap = float(rr[abs(rr).argmax()]) if rr is not None and len(rr) else 0.0
    # Régime de volatilité : part des |rendements| de l'année sous la vol 20 j courante.
    rv = rets_c[max(0, t - 20):t]
    cur_v = float(rv.std()) if rv.size > 3 else 0.0
    hist = rets_c[max(0, t - 252):t]
    reg = float((np.abs(hist) < cur_v).mean()) if hist.size > 20 else 0.5
    return [c[t] / c[t - 20] - 1, c[t] / c[t - 60] - 1,
            (c[t] - sma[t]) / sma[t], rsi[t] / 100.0, vol,
            (c[t] / c[t - 60] - 1) / (vol + 1e-6),
            c[t] / hi52 - 1 if hi52 else 0.0,
            -(c[t] / c[t - 5] - 1),
            gap, reg]


def _serie(bars, h: int):
    """Échantillons (features, rendement à terme, bornes du label) d'UN titre."""
    from packages.indicators.momentum import RSI
    from packages.indicators.trend import SMA
    from packages.indicators.volatility import ATR
    from packages.ml.validation_edge import bornes_label
    c = np.array([b.close for b in bars], float)
    sma, rsi, atr = SMA(50).compute(bars), RSI(14).compute(bars), ATR(14).compute(bars)
    rets_c = np.concatenate([[0.0], np.diff(c) / c[:-1]])
    lignes = []
    # Le label part du PRIX D'EXÉCUTION (close de la séance suivante, comme le rejeu),
    # jamais du close qui a servi aux features. Purge : du signal à la sortie.
    for t in range(60, len(c) - h - 1, PAS):
        f = features_point(c, sma, rsi, atr, rets_c, t)
        if f is not None:
            lignes.append((f, c[t + 1 + h] / c[t + 1] - 1.0,
                           *bornes_label(bars, t, h + 1)))
    return lignes, features_point(c, sma, rsi, atr, rets_c, len(c) - 1)


def jeu_de_donnees(data: dict, h: int = H):
    """(X, R, T0, T1, last) triés par début de label. R = rendement à terme BRUT."""
    lignes, last = [], {}
    for s, bars in data.items():
        if len(bars) < 90 + h:
            continue
        rows, fl = _serie(bars, h)
        lignes.extend(rows)
        if fl is not None:
            last[s] = fl
    if not lignes:
        return None
    X = np.array([r[0] for r in lignes], float)
    R, T0, T1 = (np.array([r[i] for r in lignes]) for i in (1, 2, 3))
    if len(X) > MAX_ECHANTILLONS:               # borne le coût (tirage reproductible)
        idx = np.random.default_rng(0).choice(len(X), MAX_ECHANTILLONS, replace=False)
        X, R, T0, T1 = X[idx], R[idx], T0[idx], T1[idx]
    order = np.argsort(T0, kind="stable")       # tri temporel requis par la CV purgée
    return X[order], R[order], T0[order], T1[order], last


def labels_relatifs(R, T0, cout: float) -> np.ndarray:
    """1 si le titre bat la médiane de la MÊME semaine calendaire de plus que `cout`.

    `T0` est en ordinaux de jour : `T0 // 7` regroupe des semaines lundi → dimanche.
    Un titre seul dans sa semaine est à 0 de la médiane, donc jamais compté gagnant."""
    import pandas as pd
    R = np.asarray(R, float)
    med = pd.Series(R).groupby(np.asarray(T0) // 7).transform("median").to_numpy()
    return ((R - med) > cout).astype(float)


def cv_purgee(X, y, T0, T1, n_splits: int = 5) -> list[float]:
    """AUC hors échantillon par pli (CV purgée + embargo, López de Prado)."""
    from packages.ml.cv import PurgedKFold
    aucs: list[float] = []
    try:
        for tr, te in PurgedKFold(n_splits=n_splits, embargo_pct=0.01).split(T0, T1):
            if len(tr) < 100 or len(te) < 30 or len(set(y[te])) < 2:
                continue
            m, _ = modele()
            m.fit(X[tr], y[tr])
            a = auc(m.predict_proba(X[te]), y[te])
            if a is not None:
                aucs.append(a)
    except Exception:  # noqa: BLE001 — CV indisponible → on continue sans
        pass
    return aucs


def signature(X, T1, last) -> tuple:
    """Clé de l'artefact : le jeu vu ET la définition des features/du label."""
    return (len(X), X.shape[1], len(last), int(T1.max()) if len(T1) else 0,
            VERSION_FEATURES, tuple(NOMS))


def section_ml(data: dict, sector_of: dict, names: dict) -> dict:
    """Entraîne (ou recharge) le modèle d'edge et publie la section ML du snapshot."""
    jeu = jeu_de_donnees(data)
    if jeu is None or len(jeu[0]) < MIN_ECHANTILLONS:
        return {"available": False}
    X, R, T0, T1, last = jeu
    y = labels_relatifs(R, T0, cout_aller_retour())
    if len(set(y)) < 2:
        return {"available": False}
    from packages.ml.edge_publication import publier
    return publier(X, y, T0, T1, last, sector_of, names)
