"""Variantes PRÉ-ENREGISTRÉES du modèle d'edge : mêmes lignes, autres représentations.

Écrit le 07/10, AVANT toute mesure sur données réelles. L'AUC hors échantillon du
modèle de production vaut 0,519 (VPS, 06/10). Quatre variantes, et seulement quatre,
sont comparées sur les MÊMES lignes (titre, date) et les MÊMES plis :

  V0  actuel        features brutes · label « bat la médiane de la semaine, frais
                    payés »
  V1  rangs         features en RANG dans la coupe de la semaine · même label
                    (le label est relatif : des features absolues obligent le modèle à
                    réapprendre la normalisation transversale, et elles dérivent quand
                    la volatilité de marché change)
  V2  sectoriel     features en rang · label « bat la médiane de son SECTEUR la même
                    semaine, frais payés » (retire du label le pari sectoriel)
  V3  triple barr.  features en rang · label triple barrière (López de Prado) :
                    barrières à ±σ_GK·√H (Garman-Klass), horizon H ; gagnant =
                    barrière haute touchée d'abord, ou rendement final > coût

Le JUGE commun est l'IC de rang entre le score et le rendement RELATIF à terme
(rendement − médiane de la semaine) : l'AUC n'est pas comparable d'un label à l'autre.
"""

from __future__ import annotations

import numpy as np

VARIANTES = ("V0_actuel", "V1_rangs", "V2_sectoriel", "V3_triple_barriere")
K_BARRIERE = 1.0                 # barrières à ±K·σ_GK·√H — fixé avant mesure
MIN_GROUPE_SECTEUR = 5           # sous 5 titres, médiane de la semaine entière


def _lignes_titre(sym: str, bars: list, h: int, cout: float) -> list:
    from packages.indicators.momentum import RSI
    from packages.indicators.trend import SMA
    from packages.indicators.volatility import ATR
    from packages.ml.edge_transversal import PAS, features_point
    from packages.ml.labeling import volatilite_garman_klass
    from packages.ml.validation_edge import bornes_label
    c = np.array([b.close for b in bars], float)
    gk = volatilite_garman_klass([b.open for b in bars], [b.high for b in bars],
                                 [b.low for b in bars], c)
    sma, rsi, atr = SMA(50).compute(bars), RSI(14).compute(bars), ATR(14).compute(bars)
    rets_c = np.concatenate([[0.0], np.diff(c) / c[:-1]])
    out = []
    for t in range(60, len(c) - h - 1, PAS):
        f = features_point(c, sma, rsi, atr, rets_c, t)
        if f is not None:
            out.append((f, c[t + 1 + h] / c[t + 1] - 1.0, *bornes_label(bars, t, h + 1),
                        label_triple_barriere(c, t + 1, h, gk[t], cout), sym))
    return out


def label_triple_barriere(c: np.ndarray, i: int, h: int, sigma: float,
                          cout: float) -> float:
    """1 si la barrière haute (+K·σ·√h) est touchée avant la basse ; à l'échéance,
    1 si le rendement dépasse le coût aller-retour. Entrée au close d'exécution `i`."""
    from packages.ml.labeling import triple_barrier
    largeur = K_BARRIERE * float(sigma) * np.sqrt(h) if sigma == sigma else 0.0
    if largeur <= 0:
        return float(c[min(i + h, len(c) - 1)] / c[i] - 1.0 > cout)
    (lab,) = triple_barrier(c, [i], pt=1.0, sl=1.0, vol=np.full(len(c), largeur),
                            horizon=h)
    if lab.touched == "time":
        return float(lab.ret > cout)
    return float(lab.label == 1)


def construire(data: dict, sector_of: dict, h: int | None = None) -> dict | None:
    """Jeu commun aux quatre variantes, trié par début de label (CV purgée)."""
    from packages.ml.edge_transversal import MAX_ECHANTILLONS, H, cout_aller_retour
    h = H if h is None else h
    cout = cout_aller_retour()
    lignes = []
    for s, bars in data.items():
        if len(bars) >= 90 + h:
            lignes.extend(_lignes_titre(s, bars, h, cout))
    if not lignes:
        return None
    idx = np.arange(len(lignes))
    if len(idx) > MAX_ECHANTILLONS:              # même tirage que la production
        idx = np.random.default_rng(0).choice(len(idx), MAX_ECHANTILLONS, replace=False)
    sel = [lignes[i] for i in idx]
    jeu = {"X": np.array([r[0] for r in sel], float),
           "R": np.array([r[1] for r in sel], float),
           "T0": np.array([r[2] for r in sel]), "T1": np.array([r[3] for r in sel]),
           "TB": np.array([r[4] for r in sel], float),
           "sym": np.array([r[5] for r in sel], dtype=object)}
    jeu["secteur"] = np.array([sector_of.get(s, "?") for s in jeu["sym"]], dtype=object)
    ordre = np.argsort(jeu["T0"], kind="stable")
    return {k: v[ordre] for k, v in jeu.items()} | {"h": h, "cout": cout}


def semaine(T0) -> np.ndarray:
    return np.asarray(T0) // 7


def rangs_transversaux(X: np.ndarray, T0) -> np.ndarray:
    """Chaque feature remplacée par son rang centile dans la coupe de SA semaine."""
    import pandas as pd
    df = pd.DataFrame(X)
    return df.groupby(semaine(T0)).rank(pct=True).to_numpy()


def rendement_relatif(R, T0) -> np.ndarray:
    """Rendement − médiane de la semaine : ce que le classement encaisse vraiment."""
    import pandas as pd
    s = pd.Series(np.asarray(R, float))
    return (s - s.groupby(semaine(T0)).transform("median")).to_numpy()


def label_sectoriel(R, T0, secteur, cout: float) -> np.ndarray:
    import pandas as pd
    s = pd.Series(np.asarray(R, float))
    cle = pd.Series([f"{w}|{x}" for w, x in zip(semaine(T0), secteur, strict=True)])
    med_sect = s.groupby(cle).transform("median")
    n_sect = s.groupby(cle).transform("size")
    med_sem = s.groupby(semaine(T0)).transform("median")
    med = med_sect.where(n_sect >= MIN_GROUPE_SECTEUR, med_sem)
    return ((s - med) > cout).astype(float).to_numpy()


def variante(nom: str, jeu: dict) -> tuple[np.ndarray, np.ndarray]:
    """(X, y) de la variante `nom` sur le jeu commun."""
    from packages.ml.edge_transversal import labels_relatifs
    X, R, T0, cout = jeu["X"], jeu["R"], jeu["T0"], jeu["cout"]
    if nom == "V0_actuel":
        return X, labels_relatifs(R, T0, cout)
    Xr = rangs_transversaux(X, T0)
    if nom == "V1_rangs":
        return Xr, labels_relatifs(R, T0, cout)
    if nom == "V2_sectoriel":
        return Xr, label_sectoriel(R, T0, jeu["secteur"], cout)
    if nom == "V3_triple_barriere":
        return Xr, jeu["TB"]
    raise ValueError(nom)
