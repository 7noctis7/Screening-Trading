"""IC du classement RÉELLEMENT TRADÉ, par horizon, contre une distribution nulle.

POURQUOI (audit de l'espérance, 06/10, rang 1). L'IC publié jusqu'ici (−0,068) est celui
du score de SCREENING, que la production n'utilise pas. La production choisit ses 12
lignes par `preset_config.momentum_rank` : le rendement sur 252 barres jusqu'au dernier
close (« 12-0 »). Rien n'établissait que CE classement prédit quoi que ce soit, à aucun
horizon. Tant qu'il n'est pas mesuré, chercher des features est chercher dans le noir.

MÉTHODE.
- Grille de dates commune (`preset_rejeu.calendrier`) : à la date d, la coupe
  transversale contient les titres cotés ce jour-là, avec au moins 253 barres connues.
- Score = c[d − saut] / c[d − 252] − 1, calculé sur les clôtures ≤ d seulement
  (saut = 0 : la production ; saut = 21 : le 12-1 classique, une AUTRE hypothèse).
- Cible = rendement du PRIX D'EXÉCUTION : close(d + 1) → close(d + 1 + h),
  h ∈ {1, 5, 10, 20, 60} séances. Le rejeu exécute au close de la séance suivant la
  décision ; le label part de ce prix, jamais du close qui a servi au signal (06/10).
- RankIC (Spearman) par date ; pas = horizon par défaut, donc des fenêtres DISJOINTES.
- Écart du top-12 : rendement moyen des 12 premiers moins la médiane de la coupe — la
  quantité que le portefeuille encaisse réellement, avant pondération et coûts.
- Distribution NULLE : inversion aléatoire du SIGNE des IC datés (test de
  randomisation de la moyenne, fenêtres disjointes) ; p bilatérale
  = (1 + #{|IC nul| ≥ |IC observé|}) / (1 + N). Elle porte la VRAIE variabilité d'une
  date à l'autre.
  CORRIGÉ LE 06/10 (premier passage réel) : la nulle permutait les scores AU SEIN de
  chaque date. Elle suppose les titres indépendants entre eux ; or un facteur commun
  (marché, secteur) fait varier l'IC d'une date à l'autre bien plus que 1/√N. Résultat
  mesuré : h = 20 j, t = +0,70 mais p_perm = 0,005 (le plancher à 200 tirages) — une
  nulle 4 fois trop étroite, qui déclarait significatif ce que le t ne voit pas.

CE QUE ÇA NE MESURE PAS. Les portes (régime, ampleur, DD-target), l'ERC et les coûts :
c'est l'IC du SIGNAL de sélection, pas la performance du portefeuille (cf. le rejeu).
Chaque horizon est un essai au registre ; les 5 horizons se lisent ENSEMBLE (aucun ne
se publie seul — data-snooping).
"""

from __future__ import annotations

import numpy as np

HORIZONS = (1, 5, 10, 20, 60)
FENETRE = 252                  # identique à `preset_config.momentum_rank`
TOP_K = 12                     # `top_k` de production
N_NULLES = 2000
N_DATES_MIN = 12
N_TITRES_MIN = 20              # sous 20 titres, un rang transversal ne veut rien dire


def _series(data: dict) -> dict:
    """{symbole: ({jour: index}, clôtures)} — clôtures > 0 et finies uniquement."""
    from packages.backtest.panel import _jour
    out = {}
    for s, barres in data.items():
        jours, closes = [], []
        for b in barres:
            c = getattr(b, "close", None)
            j = _jour(b)
            if j and c is not None and c == c and c > 0:
                jours.append(j)
                closes.append(float(c))
        if closes:
            out[s] = ({j: i for i, j in enumerate(jours)}, np.asarray(closes))
    return out


def score_momentum(closes: np.ndarray, i: int, saut: int = 0) -> float | None:
    """Momentum à l'index i (clôtures ≤ i) : c[i − saut] / c[i − FENETRE] − 1."""
    if i - FENETRE < 0 or saut < 0 or saut >= FENETRE:
        return None
    return float(closes[i - saut] / closes[i - FENETRE] - 1.0)


def coupe(series: dict, jour: str, entree: str, sortie: str, saut: int = 0):
    """(symboles, scores, rendements) : score connu au close de `jour`, rendement du
    close d'`entree` (exécution) au close de `sortie`. Coté aux trois dates."""
    syms, sc, fut = [], [], []
    for s, (idx, c) in series.items():
        i, e, k = idx.get(jour), idx.get(entree), idx.get(sortie)
        if i is None or e is None or k is None:
            continue
        v = score_momentum(c, i, saut)
        if v is not None and np.isfinite(v):
            syms.append(s)
            sc.append(v)
            fut.append(float(c[k] / c[e] - 1.0))
    return syms, np.asarray(sc), np.asarray(fut)


def _rangs(x: np.ndarray) -> np.ndarray:
    import pandas as pd
    return pd.Series(x).rank(method="average").to_numpy()


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    a, b = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / den) if den > 0 else None


def _ecart_top(sc: np.ndarray, fut: np.ndarray, k: int) -> float:
    top = np.argsort(-sc, kind="stable")[:k]
    return float(fut[top].mean() - np.median(fut))


def mesures_horizon(series: dict, cal: list[str], h: int, pas: int, saut: int,
                    debut: int = FENETRE) -> list[dict]:
    """Une ligne par date mesurable : RankIC, écart du top-12, rangs pour la nulle."""
    lignes = []
    for t in range(debut, len(cal) - h - 1, max(1, pas)):
        _, sc, fut = coupe(series, cal[t], cal[t + 1], cal[t + 1 + h], saut)
        if sc.size < N_TITRES_MIN:
            continue
        ic = _corr(_rangs(sc), _rangs(fut))
        if ic is not None:
            lignes.append({"jour": cal[t], "ic": ic,
                           "top": _ecart_top(sc, fut, TOP_K)})
    return lignes


def nulle(ics: np.ndarray, n: int = N_NULLES, graine: int = 0) -> np.ndarray:
    """IC moyens sous H0 (IC daté symétrique autour de 0) : signes tirés au hasard."""
    rng = np.random.default_rng(graine)
    signes = rng.choice((-1.0, 1.0), size=(n, ics.size))
    return (signes * ics).mean(axis=1)


def _stats(ics: np.ndarray) -> dict:
    from packages.research.screening_ic import p_valeur
    moy = float(ics.mean())
    sd = float(ics.std(ddof=1)) if ics.size > 1 else 0.0
    t = float(moy / sd * np.sqrt(ics.size)) if sd > 0 else None
    return {"ic_moyen": moy, "ic_ecart_type": sd, "t_stat": t,
            "p_student": p_valeur(t, ics.size),
            "part_positive": float((ics > 0).mean())}


def _ic95(x: np.ndarray) -> list[float] | None:
    """IC à 95 % de la moyenne (fenêtres disjointes, approximation normale)."""
    if x.size < 3:
        return None
    se = float(x.std(ddof=1) / np.sqrt(x.size))
    return [float(x.mean() - 1.96 * se), float(x.mean() + 1.96 * se)]


def resume_horizon(lignes: list[dict], h: int, pas: int, n_nulles: int) -> dict:
    """Statistiques d'un horizon ; UNCALIBRATED sous `N_DATES_MIN` dates."""
    if len(lignes) < N_DATES_MIN:
        return {"horizon": h, "available": False, "status": "UNCALIBRATED",
                "n_dates": len(lignes)}
    ics = np.asarray([li["ic"] for li in lignes])
    tops = np.asarray([li["top"] for li in lignes])
    nul = nulle(ics, n_nulles)
    obs = float(ics.mean())
    p_signes = float((1 + (np.abs(nul) >= abs(obs) - 1e-12).sum()) / (1 + nul.size))
    m = len(ics) // 2
    return {"horizon": h, "available": True, "status": "MESURÉ", "pas": pas,
            "chevauchement": pas < h, "n_dates": int(ics.size), **_stats(ics),
            "p_signes": p_signes, "nulle_p95": float(np.quantile(np.abs(nul), 0.95)),
            "ecart_top12_moyen": float(tops.mean()),
            "ic_premiere_moitie": float(ics[:m].mean()),
            "ic_seconde_moitie": float(ics[m:].mean()),
            "ic_seconde_moitie_ic95": _ic95(ics[m:]),
            "premier_jour": lignes[0]["jour"], "dernier_jour": lignes[-1]["jour"]}


def mesurer(data: dict, horizons=HORIZONS, saut: int = 0, pas: int | None = None,
            n_nulles: int = N_NULLES) -> dict:
    """IC du classement momentum de production pour chaque horizon. `pas=None` → h."""
    from packages.backtest.preset_rejeu import calendrier
    series = _series(data)
    cal = calendrier(data)
    res = []
    for h in horizons:
        p = h if pas is None else pas
        lignes = mesures_horizon(series, cal, h, p, saut)
        res.append(resume_horizon(lignes, h, p, n_nulles))
    return {"signal": f"momentum {FENETRE} barres, saut {saut}",
            "production": saut == 0, "n_series": len(series), "n_jours": len(cal),
            "horizons_testes": len(horizons), "resultats": res}
