"""À quel moment de la journée le rendement se fait-il vraiment ? — le mesurer.

LA QUESTION (10/09) : « quel créneau pour trader, là où historiquement ça performe
le mieux ? » Il existe une réponse de manuel — éviter les trente premières minutes,
exécuter près de la clôture — mais elle porte sur le COÛT d'exécution, pas sur le
rendement. Or les deux ne se répondent pas : payer moins cher n'a d'intérêt que si
l'on est du bon côté de la journée.

LA DÉCOMPOSITION. Une séance se coupe en deux morceaux qui n'ont rien à voir :

  · NUIT      — clôture de la veille → ouverture du jour. On la capture en détenant à
                la clôture. Aucune décision n'y est possible : le marché est fermé.
  · JOURNÉE   — ouverture → clôture. On la capture en détenant pendant la séance.

LE PIÈGE, ET LE FAUX GARDE-FOU. Si la clôture est corrigée des splits et dividendes et
que l'ouverture ne l'est pas, chaque ajustement se loge ENTIÈREMENT dans le rendement de
nuit. On lit alors « la nuit fait tout le rendement » — exactement la conclusion
attendue, et complètement fausse.

J'avais d'abord voulu contrôler cela par l'identité `(1+nuit)(1+journée) = 1+total`.
Elle ne contrôle RIEN : l'ouverture se simplifie algébriquement, l'égalité tient pour
n'importe quels nombres, y compris incohérents. Un test l'a démasquée. Le contrôle qui
mord regarde ailleurs : **l'ouverture et la clôture doivent tomber dans la fourchette
[bas, haut] de la séance**. Si les colonnes ne partagent pas la même base d'ajustement,
l'ouverture en sort — et cela, aucune algèbre ne peut le masquer.

CE QUE CE MODULE NE DIT PAS. Il ne propose aucune stratégie. Capturer la seule nuit
imposerait deux allers-retours par jour, dont le coût dépasserait presque sûrement le
gain — et ce coût n'est pas mesuré ici. Il répond à une question plus modeste et plus
utile : « à quelle heure faut-il être en position pour que le rendement historique de
MON univers me soit acquis ? »
"""

from __future__ import annotations

import numpy as np

__all__ = ["coherence", "decomposer"]

TOLERANCE_COHERENCE = 1e-6     # l'identité est exacte : au-delà, les bases diffèrent


def _rendements(ouverture: np.ndarray, cloture: np.ndarray) -> tuple[np.ndarray, ...]:
    """(nuit, journée, clôture-à-clôture), alignés sur les jours 1..T-1."""
    o, c = np.asarray(ouverture, float), np.asarray(cloture, float)
    if o.shape != c.shape or o.ndim != 2 or o.shape[0] < 2:
        raise ValueError("ouverture et clôture doivent être deux matrices (T ≥ 2) × N")
    with np.errstate(divide="ignore", invalid="ignore"):
        veille = np.where(c[:-1] > 0, c[:-1], np.nan)
        nuit = o[1:] / veille - 1.0
        journee = c[1:] / np.where(o[1:] > 0, o[1:], np.nan) - 1.0
        total = c[1:] / veille - 1.0
    return nuit, journee, total


def coherence(ouverture: np.ndarray, haut: np.ndarray, bas: np.ndarray,
              cloture: np.ndarray) -> float:
    """Part des observations où l'ouverture ou la clôture SORT de [bas, haut].

    Proche de zéro : les quatre colonnes partagent la même base d'ajustement, et la
    décomposition nuit/journée veut dire quelque chose. Nettement au-dessus : elles ne
    la partagent pas, et tout ce qu'on lirait ensuite serait un artefact de splits et de
    dividendes logé dans le rendement de nuit.

    C'est le contrôle qui remplace l'identité multiplicative — laquelle, l'ouverture s'y
    simplifiant, tenait pour n'importe quels nombres.
    """
    o, h, b, c = (np.asarray(x, float) for x in (ouverture, haut, bas, cloture))
    if not (o.shape == h.shape == b.shape == c.shape) or o.ndim != 2:
        raise ValueError("les quatre colonnes doivent avoir la même forme (T × N)")
    valide = np.isfinite(o) & np.isfinite(h) & np.isfinite(b) & np.isfinite(c)
    if not valide.any():
        return float("nan")
    marge = 1e-9 * np.maximum(1.0, np.abs(h))
    dehors = ((o < b - marge) | (o > h + marge)
              | (c < b - marge) | (c > h + marge)) & valide
    return float(dehors.sum() / valide.sum())


def decomposer(ouverture: np.ndarray, cloture: np.ndarray,
               masque: np.ndarray | None = None) -> dict:  # noqa: D417
    """Rendement cumulé d'un panier équipondéré, séparé nuit / journée.

    `masque` : vecteur booléen (N,) pour restreindre à une classe d'actifs. Chaque jour
    est la moyenne transversale des actifs qui cotent CE jour-là — un actif absent ne
    tire pas la moyenne vers zéro, il n'y participe pas.
    """
    nuit, journee, total = _rendements(ouverture, cloture)
    if masque is not None:
        m = np.asarray(masque, bool)
        nuit, journee, total = nuit[:, m], journee[:, m], total[:, m]
    if nuit.size == 0:
        return {"available": False, "motif": "aucun actif dans ce périmètre"}

    def _cumul(r: np.ndarray) -> tuple[float, int]:
        quotidien = np.nanmean(r, axis=1)
        utiles = quotidien[np.isfinite(quotidien)]
        return (float(np.prod(1.0 + utiles) - 1.0), int(utiles.size))

    cum_nuit, n_jours = _cumul(nuit)
    cum_jour, _ = _cumul(journee)
    cum_total, _ = _cumul(total)
    part = (cum_nuit / cum_total) if cum_total != 0.0 else float("nan")
    return {
        "available": True,
        "n_actifs": int(nuit.shape[1]), "n_jours": n_jours,
        "nuit": cum_nuit, "journee": cum_jour, "total": cum_total,
        # Part de la nuit dans le total. Au-delà de 100 %, la séance a DÉTRUIT du
        # rendement que la nuit avait produit — ce n'est pas une aberration, c'est
        # le cas le plus souvent rapporté sur les actions américaines.
        "part_nuit": part,
    }
