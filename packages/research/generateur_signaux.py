"""Découverte de signaux — la moitié qui PROPOSE, tenue par celle qui REFUSE.

CE QUE FAIT LE BLUEPRINT NVIDIA, ET CE QUI Y MANQUE

`quantitative-signal-discovery-agent` boucle : un modèle de langage invente une formule
de signal, un second l'écrit en Python, un troisième la teste au Rank IC, et la retient
si |IC| ≥ 0,02 avec p ≤ 0,05. La boucle est excellente. Le critère d'acceptation, lui,
est celui d'un signal isolé — appliqué à une machine qui en produit des centaines.

Le chiffre le montre mieux qu'un argument. La sélection de CE projet a été mesurée à
IC = +0,0202, t = 0,76 : elle FRANCHIRAIT le seuil de 0,02 du blueprint, alors que notre
propre méthode la rejette parce que 0,76 n'est pas 2. Un générateur branché sur ce seuil
aurait donc « découvert » exactement le signal qu'on venait d'écarter.

CE QUE FAIT CE MODULE À LA PLACE

Il ne dessert pas la boucle, il la CONTRAINT :

1. **Aucun code n'est exécuté.** Le blueprint fait écrire du Python par un modèle puis
   l'exécute. Dans un dépôt qui peut passer des ordres réels, c'est une porte d'entrée
   pour du code arbitraire. Ici, un signal est une EXPRESSION dans une grammaire fermée,
   évaluée par notre propre interpréteur. Un modèle de langage pourra proposer des
   expressions ; il ne pourra jamais injecter de code.

2. **Chaque candidat est inscrit au registre AVANT d'être jugé.** `ledger.trial_count()`
   compte les essais, `deflation_params()` s'en sert pour déflater le Sharpe. Un
   générateur qui produit trois cents candidats fait donc monter N de trois cents, et
   resserre mécaniquement le seuil pour tout le monde. C'est exactement ce que le
   blueprint ne fait pas — et sans quoi générer beaucoup revient à trouver du bruit.

3. **L'évaluation réutilise `information_coefficient`**, sur des fenêtres DISJOINTES.
   Des fenêtres qui se chevauchent font exploser le t-stat sans ajouter d'information.

Aucun modèle de langage n'est requis : `enumerer()` produit des candidats de
façon déterministe. Le modèle, quand il viendra, remplacera cette énumération —
jamais le garde-fou.
"""

from __future__ import annotations

import numpy as np

from packages.research.information_coefficient import information_coefficient
from packages.research.ledger import append_record, trial_count

# Seuil de la boucle NVIDIA, gardé comme POINT DE COMPARAISON, jamais comme critère.
IC_SEUIL_BLUEPRINT = 0.02
# Notre exigence : un t-stat lisible sur fenêtres disjointes. 2 ≈ 5 % bilatéral.
T_MIN = 2.0
N_FENETRES_MIN = 12

# Grammaire fermée : uniquement ces opérateurs, uniquement sur ces champs.
CHAMPS = ("open", "high", "low", "close", "volume")


def _rang(x: np.ndarray) -> np.ndarray:
    ordre = np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)
    return ordre / max(1.0, ordre.size - 1.0)


OPERATEURS: dict[str, callable] = {
    "identite": lambda x: x,
    "negatif": lambda x: -x,
    "rang": _rang,
    "zscore": lambda x: (x - x.mean()) / (x.std() + 1e-12),
    "log": lambda x: np.log(np.clip(x, 1e-12, None)),
}


class ExpressionInvalide(ValueError):
    """Une expression hors grammaire. Levée AVANT toute évaluation."""


def valider(expression: dict) -> dict:
    """Vérifie qu'une expression appartient à la grammaire. Lève sinon.

    C'est la frontière de sécurité du module : rien n'est évalué avant d'être passé
    ici. Une expression venue d'un modèle de langage, d'un fichier ou du réseau suit le
    même chemin qu'une expression écrite à la main.
    """
    if not isinstance(expression, dict):
        raise ExpressionInvalide("une expression est un dictionnaire")
    champ = expression.get("champ")
    op = expression.get("operateur", "identite")
    retard = expression.get("retard", 0)
    if champ not in CHAMPS:
        raise ExpressionInvalide(f"champ inconnu : {champ!r} (attendus : {CHAMPS})")
    if op not in OPERATEURS:
        raise ExpressionInvalide(
            f"opérateur inconnu : {op!r}. La grammaire est FERMÉE — on n'exécute "
            "jamais de code fourni de l'extérieur, on refuse."
        )
    if not isinstance(retard, int) or not 0 <= retard <= 252:
        raise ExpressionInvalide(f"retard hors bornes : {retard!r}")
    return {"champ": champ, "operateur": op, "retard": retard}


def nom(expression: dict) -> str:
    """Nom stable et lisible, qui sert de clé au registre."""
    e = valider(expression)
    return f"{e['operateur']}({e['champ']}, retard={e['retard']})"


def evaluer(expression: dict, valeurs: dict[str, np.ndarray]) -> np.ndarray:
    """Applique l'expression à un panneau {champ: matrice (T × N)}.

    Rend une matrice de mêmes dimensions : une valeur de signal par actif et par date.
    Le retard décale dans le PASSÉ — jamais vers le futur, c'est la seule direction
    qui ne fabrique pas d'information.
    """
    e = valider(expression)
    brut = np.asarray(valeurs[e["champ"]], dtype=float)
    if brut.ndim != 2:
        raise ExpressionInvalide(
            "le panneau doit être une matrice (T dates × N actifs)")
    if e["retard"]:
        decale = np.full_like(brut, np.nan)
        decale[e["retard"]:] = brut[: -e["retard"]]
        brut = decale
    fn = OPERATEURS[e["operateur"]]
    sortie = np.full_like(brut, np.nan)
    for i in range(brut.shape[0]):
        ligne = brut[i]
        if np.isfinite(ligne).sum() >= 2:
            sortie[i] = fn(np.nan_to_num(ligne, nan=float(np.nanmean(ligne))))
    return sortie


def enumerer(champs=CHAMPS, operateurs=None, retards=(0, 5, 21)) -> list[dict]:
    """Tous les candidats de la grammaire — déterministe, sans modèle de langage.

    L'ordre est fixe : deux exécutions produisent la même liste, donc le même compte
    d'essais et la même déflation. Un générateur non déterministe rendrait le registre
    inexploitable.
    """
    ops = tuple(operateurs or OPERATEURS)
    return [{"champ": c, "operateur": o, "retard": r}
            for c in champs for o in ops for r in retards]


def mesurer_ic(signal: np.ndarray, rendements_futurs: np.ndarray,
               horizon: int) -> dict:
    """IC moyen et t-stat sur des fenêtres DISJOINTES (pas = horizon).

    Le pas égal à l'horizon est ce qui rend le t-stat lisible : deux fenêtres qui se
    recouvrent partagent des rendements, leurs IC deviennent autocorrélés et le t-stat
    grossit sans qu'aucune information n'ait été ajoutée. C'est la même règle que
    `screening_ic`, pour que les deux mesures restent comparables.
    """
    s = np.asarray(signal, float)
    r = np.asarray(rendements_futurs, float)
    if s.shape != r.shape or s.ndim != 2:
        raise ValueError("signal et rendements doivent être deux matrices (T × N)")
    ics = [ic for t in range(0, s.shape[0], max(1, horizon))
           if (ic := information_coefficient(s[t], r[t])) is not None]
    if len(ics) < 2:
        return {"ic_moyen": None, "t_stat": None, "n_fenetres": len(ics)}
    serie = np.asarray(ics, float)
    ecart = float(serie.std(ddof=1))
    moyenne = float(serie.mean())
    t_stat = float(moyenne / ecart * np.sqrt(serie.size)) if ecart > 0 else None
    return {"ic_moyen": moyenne, "t_stat": t_stat, "n_fenetres": int(serie.size)}


def verdict(mesure: dict) -> tuple[str, str]:
    """(statut, motif) — notre critère, PAS celui du blueprint.

    Trois issues, jamais deux : « rejete » n'est pas la même chose que « indistinct ».
    Un signal qu'on n'a pas pu mesurer assez longtemps n'est pas un mauvais signal,
    c'est un signal non mesuré ; les confondre alimente le registre en faux négatifs.
    """
    n, t = mesure.get("n_fenetres") or 0, mesure.get("t_stat")
    if n < N_FENETRES_MIN or t is None:
        return "en_test", (f"{n} fenêtres disjointes seulement (minimum "
                           f"{N_FENETRES_MIN}) : rien de mesurable, pas un rejet")
    if abs(t) < T_MIN:
        return "rejete", (f"t = {t:.2f}, il en faudrait {T_MIN:.0f} — indiscernable "
                          "du hasard sur cet échantillon")
    return "promu", f"t = {t:.2f} sur {n} fenêtres disjointes"


def accepte_par_le_blueprint(mesure: dict) -> bool:
    """Ce que la boucle NVIDIA retiendrait, aux valeurs par défaut (|IC| ≥ 0,02).

    Gardé comme POINT DE COMPARAISON, jamais comme critère de promotion. Sert à montrer
    l'écart sur des chiffres réels — c'est plus convaincant qu'un argument.
    """
    ic = mesure.get("ic_moyen")
    return ic is not None and abs(ic) >= IC_SEUIL_BLUEPRINT


def soumettre(expression: dict, signal: np.ndarray, rendements_futurs: np.ndarray,
              horizon: int, classe: list[str] | None = None,
              chemin_ledger=None) -> dict:
    """Mesure UN candidat, l'inscrit au registre, rend son verdict.

    L'ordre compte et n'est pas négociable : on écrit AVANT de juger. Un candidat
    rejeté qui ne serait pas inscrit ferait mentir le compte d'essais, donc la
    déflation du Sharpe de tous les autres. « Essayer beaucoup » ne doit jamais être
    gratuit — c'est précisément ce qui manque à une boucle qui génère sans compter.
    """
    e = valider(expression)
    mesure = mesurer_ic(signal, rendements_futurs, horizon)
    statut, motif = verdict(mesure)
    enregistrement = {
        "facteur": nom(e), "statut": statut, "motif": motif,
        "horizon": f"{horizon}j", "classe": classe or ["equity"],
        "ic_moyen": mesure["ic_moyen"], "t_stat": mesure["t_stat"],
        "n_fenetres": mesure["n_fenetres"],
        "source": "generateur_signaux",
        "accepte_par_le_blueprint": accepte_par_le_blueprint(mesure),
    }
    kw = {"path": chemin_ledger} if chemin_ledger else {}
    append_record(enregistrement, **kw)
    return enregistrement


def campagne(candidats: list[dict], panneau: dict[str, np.ndarray],
             rendements_futurs: np.ndarray, horizon: int,
             chemin_ledger=None) -> dict:
    """Évalue une liste de candidats et rend le bilan de la campagne.

    Publie le nombre d'essais AVANT et APRÈS : c'est la quantité qui déflate le Sharpe
    de tout le programme, et la seule façon de voir qu'une campagne de trois cents
    candidats a resserré le seuil pour tous les travaux à venir.
    """
    kw = {"path": chemin_ledger} if chemin_ledger else {}
    avant = trial_count(**kw)
    resultats = [soumettre(c, evaluer(c, panneau), rendements_futurs, horizon,
                           chemin_ledger=chemin_ledger) for c in candidats]
    apres = trial_count(**kw)
    promus = [r for r in resultats if r["statut"] == "promu"]
    faux_positifs = [r for r in resultats
                     if r["accepte_par_le_blueprint"] and r["statut"] != "promu"]
    return {
        "n_candidats": len(resultats), "promus": promus,
        "essais_avant": avant, "essais_apres": apres,
        "retenus_par_le_blueprint_mais_pas_par_nous": faux_positifs,
        "resultats": resultats,
    }
