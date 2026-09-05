"""Information Coefficient — la pièce manquante de `breadth.py`.

`breadth.py` implémente toute la mécanique de la Loi Fondamentale de la Gestion
Active (Grinold & Kahn) — souffle effectif, TC, IR attendu — mais prend l'IC en
ENTRÉE, déjà mesuré. Rien dans le dépôt ne le mesure : ce module comble ce trou,
et rien de plus. Il ne touche à aucune exécution, aucun ordre, aucun risque — pure
statistique de diagnostic, sur des prédictions et des rendements déjà connus.

CE QUE C'EST : la corrélation de RANG (Spearman) entre le score qu'un signal donne
à un actif à la date t et le rendement RÉEL qu'il fait sur l'horizon suivant. Un IC
robuste dans la littérature se situe entre 0,02 et 0,06 — un chiffre plus haut sur
un facteur simple est un signal d'alarme de surapprentissage, pas une bonne nouvelle
(cf. `breadth.ic_required`, déjà dans le dépôt, qui sert justement ce test de
réalité).

MANDAT DONNÉES RÉELLES. Moins de 20 paires point-in-time valides → `None`
(UNCALIBRATED), jamais un chiffre calculé sur un échantillon qui ne veut rien dire.
Le seuil n'est pas arbitraire : sous ~20 observations, l'écart-type d'un coefficient
de Spearman est trop large pour distinguer un IC de 0,04 du bruit.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

SEUIL_N_MIN = 20


def information_coefficient(predictions, rendements_futurs) -> float | None:
    """IC = corrélation de Spearman(prédictions, rendements RÉELS futurs).

    `None` si les paires valides sont trop peu nombreuses ou dégénérées (variance
    nulle d'un des deux vecteurs) — jamais un chiffre qui prétend mesurer quelque
    chose qu'il n'a pas vu. C'est le même principe que `breadth.autocorr` (0,0 pour
    une entrée dégénérée), mais ici `None` plutôt que 0,0 : un IC de 0,0 mesuré est
    une information (« ce signal ne prédit rien ») ; `None` dit qu'on n'a pas pu
    mesurer du tout — les deux ne doivent jamais se confondre.
    """
    p = np.asarray(predictions, dtype=float)
    r = np.asarray(rendements_futurs, dtype=float)
    if p.shape != r.shape:
        raise ValueError(f"prédictions et rendements de tailles différentes : "
                         f"{p.shape} vs {r.shape}")
    valides = np.isfinite(p) & np.isfinite(r)
    p, r = p[valides], r[valides]
    if p.size < SEUIL_N_MIN or p.std() <= 0 or r.std() <= 0:
        return None
    ic = stats.spearmanr(p, r).statistic
    return float(ic) if np.isfinite(ic) else None


@dataclass(frozen=True)
class ICInEchantillon:
    """IC mesuré séparément sur deux fenêtres — jamais sur la fenêtre qui a servi
    à calibrer le signal. `ratio` = OOS/IS ; sous 0,5, la marge n'est pas au
    surapprentissage près (seuil déjà en usage dans ce dépôt, cf. ADR-0066)."""
    ic_in_sample: float | None
    ic_hors_echantillon: float | None

    @property
    def ratio(self) -> float | None:
        if self.ic_in_sample is None or self.ic_hors_echantillon is None:
            return None
        if self.ic_in_sample == 0:
            return None
        return self.ic_hors_echantillon / self.ic_in_sample

    @property
    def robuste(self) -> bool:
        """False tant que le ratio n'existe pas — jamais 'robuste par défaut'."""
        r = self.ratio
        return r is not None and r >= 0.5


def ic_in_sample_hors_echantillon(predictions_is, rendements_is,
                                  predictions_oos, rendements_oos) -> ICInEchantillon:
    """Mesure l'IC sur les DEUX fenêtres séparément. Ne calibre rien : les deux
    jeux de prédictions doivent déjà exister, produits par le même signal figé."""
    return ICInEchantillon(
        ic_in_sample=information_coefficient(predictions_is, rendements_is),
        ic_hors_echantillon=information_coefficient(predictions_oos, rendements_oos))
