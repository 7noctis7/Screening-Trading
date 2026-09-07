"""Ce que vaut la SÉLECTION du screening, mesuré — pas supposé.

La recommandation d'univers choisit ses actifs par le score composite du screening. Rien
n'établissait jusqu'ici que ce score prédise quoi que ce soit : la carte devait donc
s'annoncer « non validée hors échantillon ». Ce module remplace l'aveu par une mesure.

MÉTHODE. Pour une grille d'instants `t`, on demande au moteur son classement en ne lui
donnant QUE l'information disponible à `t` (`FactorContext` tronque à `bars[: t+1]`,
vérifié), puis on corrèle ce classement au rendement RÉALISÉ entre `t` et `t + horizon`.
La corrélation est de SPEARMAN (rangs) : un score composite z-scoré n'a pas d'unité, seul
son ordre a un sens, et les rangs résistent aux queues épaisses des rendements.

DEUX PIÈGES ÉVITÉS.
1. *Chevauchement.* Deux fenêtres qui se recouvrent partagent des rendements : les IC
   deviennent autocorrélés et le t-stat explose sans qu'aucune information n'ait été
   ajoutée. Le pas par défaut ÉGALE l'horizon — des fenêtres disjointes, donc un t-stat
   qu'on peut lire.
2. *Choix a posteriori de l'horizon.* Mesurer 1, 5, 21, 63 jours puis publier le meilleur
   serait du data-snooping. L'horizon est un paramètre explicite ; en tester plusieurs
   exige de corriger le seuil (Benjamini-Hochberg, déjà au backlog) et l'appelant en est
   averti par `horizons_testes`.
"""
from __future__ import annotations

import numpy as np

from packages.research.information_coefficient import information_coefficient

HORIZON_DEFAUT = 21          # ~1 mois de bourse
DEBUT_MIN = 260              # le facteur momentum exige 252 barres : avant, rien à noter
N_DATES_MIN = 12             # sous une douzaine de fenêtres disjointes, aucune inférence


def _rendement_futur(bars: list, t: int, horizon: int) -> float | None:
    """Rendement simple entre `t` et `t + horizon`, ou None si la fenêtre déborde."""
    if t + horizon >= len(bars):
        return None
    debut, fin = float(bars[t].close), float(bars[t + horizon].close)
    return (fin / debut - 1.0) if debut > 0 else None


def ic_a_la_date(panel: dict, moteur, t: int, horizon: int, fundamentals=None) -> float | None:
    """IC transversal à une date : score connu en `t` contre rendement `t → t+horizon`."""
    scores, futurs = [], []
    for resultat in moteur.screen(panel, t=t, fundamentals=fundamentals):
        if not resultat.passed:
            continue                      # un titre filtré n'est pas une prédiction
        futur = _rendement_futur(panel[resultat.symbol], t, horizon)
        if futur is None:
            continue
        scores.append(float(resultat.score))
        futurs.append(futur)
    return information_coefficient(scores, futurs)


def _grille(panel: dict, horizon: int, pas: int, debut: int) -> list[int]:
    longueur = max((len(bars) for bars in panel.values()), default=0)
    return list(range(debut, longueur - horizon, max(1, pas)))


def _stats(ics: list[float]) -> dict:
    """Moyenne, écart-type et t-stat sur des fenêtres DISJOINTES (pas = horizon)."""
    serie = np.asarray(ics, dtype=float)
    moyenne = float(serie.mean())
    ecart = float(serie.std(ddof=1)) if serie.size > 1 else 0.0
    t_stat = float(moyenne / ecart * np.sqrt(serie.size)) if ecart > 0 else None
    return {"ic_moyen": moyenne, "ic_ecart_type": ecart, "t_stat": t_stat,
            "part_positive": float((serie > 0).mean())}


def _hors_echantillon(dates: list[int], ics: list[float]) -> dict:
    """Coupe CHRONOLOGIQUE en deux : la seconde moitié n'a servi à aucun choix.

    Une coupe aléatoire mélangerait passé et futur et ne testerait rien. Le ratio
    OOS/IS < 0,5 est le signe usuel d'un signal qui ne survit pas à sa période d'origine.
    """
    milieu = len(ics) // 2
    if milieu < 3:
        return {"ic_premiere_moitie": None, "ic_seconde_moitie": None,
                "ratio_oos": None, "robuste": False}
    debut_serie, fin_serie = float(np.mean(ics[:milieu])), float(np.mean(ics[milieu:]))
    ratio = (fin_serie / debut_serie) if abs(debut_serie) > 1e-9 else None
    return {"ic_premiere_moitie": debut_serie, "ic_seconde_moitie": fin_serie,
            "coupure_index": dates[milieu], "ratio_oos": ratio,
            "robuste": bool(ratio is not None and ratio >= 0.5 and fin_serie > 0)}


def mesurer(panel: dict, moteur, horizon: int = HORIZON_DEFAUT, pas: int | None = None,
            debut: int = DEBUT_MIN, fundamentals=None) -> dict:
    """IC walk-forward du score de screening. `pas=None` → pas = horizon (sans chevauchement)."""
    pas = horizon if pas is None else pas
    grille = _grille(panel, horizon, pas, debut)
    mesures = [(t, ic_a_la_date(panel, moteur, t, horizon, fundamentals)) for t in grille]
    retenues = [(t, ic) for t, ic in mesures if ic is not None]
    if len(retenues) < N_DATES_MIN:
        return {"available": False, "status": "UNCALIBRATED",
                "reason": (f"{len(retenues)} fenêtre(s) mesurable(s), {N_DATES_MIN} minimum — "
                           "historique trop court pour conclure quoi que ce soit."),
                "horizon": horizon, "pas": pas, "n_dates": len(retenues)}
    dates = [t for t, _ in retenues]
    ics = [ic for _, ic in retenues]
    return {"available": True, "status": "MESURÉ", "horizon": horizon, "pas": pas,
            "chevauchement": pas < horizon, "n_dates": len(ics),
            "n_actifs_median": None, **_stats(ics), **_hors_echantillon(dates, ics),
            "horizons_testes": 1}
