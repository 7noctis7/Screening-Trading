"""Ce qu'un contrôle ligne par ligne ne peut pas voir.

L'audit d'intégrité existant vérifie chaque série SÉPARÉMENT : prix positifs, cohérence
du plus haut et du plus bas, dates croissantes, trous de calendrier. Il attrape
l'impossible. Il ne peut pas attraper le POSSIBLE MAIS ABSURDE — une valeur qui respecte
toutes les règles prise isolément, et qui ne tient pas une seconde une fois replacée
parmi les autres.

Trois cas réels que seul le croisement révèle :
  · un split non ajusté : le cours est divisé par quatre du jour au lendemain. Rien
    d'illégal ligne à ligne — mais le marché entier n'a pas bougé ce jour-là.
  · un tick erroné : un prix aberrant, aussitôt corrigé. Il passe tous les contrôles de
    forme, et fabrique une volatilité et une queue de distribution qui n'existent pas.
  · un flux figé : la série ne bouge plus alors que tout le reste bouge. C'est le
    cas le plus dangereux du lot, parce qu'un cours immobile paraît SANS RISQUE à la
    variance comme au CVaR — il hériterait d'un poids qu'il ne mérite pas.

MÉTHODE. Deux mesures qui ne se recouvrent pas :

1. `ecart_a_la_coupe` — pour chaque date, à quelle distance le rendement d'un actif se
   situe de la médiane du marché ce jour-là, en unités d'écart robuste (MAD). La médiane
   et le MAD plutôt que la moyenne et l'écart-type : un jour de krach, une poignée
   de valeurs extrêmes déplacerait la moyenne au point de rendre le reste « normal ».

2. `series_figees` — combien de jours consécutifs un cours ne bouge pas, alors que le
   marché, lui, bouge. Un actif immobile un jour férié local n'est pas une anomalie ; un
   actif immobile quand tout le monde cote, si.

CE QUE ÇA NE FAIT PAS. Rien n'est corrigé automatiquement. Une correction silencieuse de
données de marché est pire que l'anomalie : elle efface la trace de ce qui n'allait pas.
On SIGNALE, l'humain tranche — même règle que le reste de la chaîne de qualité.
"""

from __future__ import annotations

import numpy as np

__all__ = ["auditer_panel", "echelle_par_actif", "ecart_a_la_coupe", "gravite_du_saut",
           "resumer_par_actif", "series_figees"]

# CALIBRÉ SUR LE PANNEAU RÉEL le 09/09 (1500 dates × 823 actifs, `make calibrer-seuil`).
# 8,0 avait été posé à vue et signalait 59 % de l'univers : un rapport que personne
# n'ouvre ne protège de rien. La mesure confronte le COÛT (part de l'univers signalée)
# au BÉNÉFICE (part des défauts injectés retrouvés — splits ×4 et ticks erronés placés
# dans le vrai panneau, sur des séances réellement cotées) :
#
#   seuil │  coût  │ splits │ ticks │ (mesuré sur)
#      8  │ 59,4 % │  98 %  │  98 % │  57 actifs
#     16  │ 15,6 % │  98 %  │  99 % │ 121 actifs
#     24  │  5,5 % │  93 %  │  99 % │ 138 actifs   ← retenu
#     32  │  3,0 % │  87 %  │  99 % │ 143 actifs
#     48  │  1,1 % │  67 %  │  97 % │ 147 actifs
#
# 24 maximise (sensibilité − coût) et l'optimum est INTÉRIEUR : la grille monte à 64 et
# le score y redescend, ce n'est donc pas un artefact de borne. Passer de 8 à 24 fait
# tomber la lecture de 489 actifs à 45, en perdant cinq points sur les splits.
# 24 et 32 sont à cinq millièmes l'un de l'autre — le choix entre eux ne pèse rien ; ce
# qui pesait, c'était 8.
SEUIL_ECART = 24.0       # écarts robustes : au-delà, on regarde
JOURS_FIGES_MIN = 5      # en dessous, un pont ou un jour férié suffit à l'expliquer
PLANCHER_ECHELLE = 1e-6  # une échelle nulle = série figée : traitée par `series_figees`


def _mad(x: np.ndarray) -> float:
    """Écart absolu médian, remis à l'échelle d'un écart-type gaussien."""
    fini = x[np.isfinite(x)]
    if fini.size < 3:
        return 0.0
    return float(1.4826 * np.median(np.abs(fini - np.median(fini))))


def echelle_par_actif(rendements: np.ndarray) -> np.ndarray:
    """Échelle robuste PROPRE à chaque actif (MAD temporel de ses rendements).

    Renvoie un vecteur (N,). Une échelle nulle — série parfaitement immobile — est
    renvoyée telle quelle : `ecart_a_la_coupe` neutralise alors la colonne plutôt que
    de diviser par zéro, et c'est `series_figees` qui la signale, avec le bon motif.
    """
    r = np.asarray(rendements, float)
    if r.ndim != 2:
        raise ValueError("rendements doit être une matrice (T dates × N actifs)")
    return np.array([_mad(r[:, j]) for j in range(r.shape[1])], dtype=float)


def ecart_a_la_coupe(rendements: np.ndarray, seuil: float = SEUIL_ECART,
                     normaliser: bool = True) -> list[dict]:
    """Les points où un actif s'écarte du marché au-delà du raisonnable.

    `rendements` : matrice (T dates × N actifs). On compare CHAQUE date à elle-même :
    un jour de krach déplace toute la coupe, et ce qui compte est de s'en écarter, pas
    d'être négatif.

    NORMALISATION PAR ACTIF (`normaliser`, vrai par défaut). Sans elle, la coupe mélange
    des échelles qui n'ont rien à voir : le forex bouge de 0,5 % par jour, une action de
    1,5 %, une crypto de 5 %. La médiane et le MAD du jour sont alors dictés par la
    classe la plus nombreuse, et une crypto qui vit sa journée ordinaire se retrouve à
    seize écarts robustes de cette coupe-là — signalée pour avoir été elle-même. Mesuré
    sur un panneau SAIN de 774 séries sans la moindre anomalie injectée : **100 % des
    cryptos flaguées, 0 % du forex**, 12 974 événements pour zéro défaut réel. Diviser
    d'abord chaque série par sa propre échelle rend la coupe homogène ; ce qui reste
    signalé est un mouvement anormal POUR CET ACTIF, ce qu'on cherchait depuis le début.

    L'échelle est estimée sur tout l'historique fourni. C'est un audit de qualité de
    données, exécuté sur un panneau complet et clos : aucune de ses sorties n'alimente
    un modèle ni une décision, donc ce regard global n'est pas un biais de survol.
    """
    brut = np.asarray(rendements, float)
    if brut.ndim != 2:
        raise ValueError("rendements doit être une matrice (T dates × N actifs)")
    r = _normalises(brut) if normaliser else brut
    trouvailles = []
    for t in range(r.shape[0]):
        ligne, ligne_brute = r[t], brut[t]
        centre = float(np.nanmedian(ligne)) if np.isfinite(ligne).any() else 0.0
        dispersion = _mad(ligne)
        if dispersion <= 0:
            continue          # journée sans dispersion : rien à comparer
        ecarts = np.abs(ligne - centre) / dispersion
        # La gravité et le motif se lisent sur le rendement RÉEL : « split non ajusté »
        # se décide à −30 % de cours, pas à trente unités d'écart normalisé.
        centre_brut = (float(np.nanmedian(ligne_brute))
                       if np.isfinite(ligne_brute).any() else 0.0)
        for j in np.where(np.isfinite(ecarts) & (ecarts > seuil))[0]:
            rendement = float(ligne_brute[j])
            trouvailles.append({
                "date_index": int(t), "actif_index": int(j),
                "rendement": rendement, "mediane_du_jour": centre_brut,
                "ecarts_robustes": float(ecarts[j]),
                "gravite": gravite_du_saut(rendement),
                "motif": (f"bouge de {rendement:+.1%} quand le marché fait "
                          f"{centre_brut:+.1%} — {ecarts[j]:.0f} écarts robustes"),
            })
    return trouvailles


def _normalises(r: np.ndarray) -> np.ndarray:
    """Rendements divisés par l'échelle propre de chaque actif. Colonne d'échelle
    nulle → NaN : elle sort de la comparaison au lieu de faire diverger la division."""
    ech = echelle_par_actif(r)
    utilisable = ech > PLANCHER_ECHELLE
    return np.where(utilisable, r / np.where(utilisable, ech, 1.0), np.nan)


def series_figees(prix: np.ndarray, jours_min: int = JOURS_FIGES_MIN) -> list[dict]:
    """Les actifs dont le cours ne bouge plus alors que le marché bouge.

    Le cas le plus dangereux : un cours immobile n'a ni dispersion ni queue, donc il
    paraît sans risque à TOUS les optimiseurs — variance comme CVaR — et hériterait
    d'un poids qu'il ne mérite pas. Aucun contrôle de forme ne peut le voir.
    """
    p = np.asarray(prix, float)
    if p.ndim != 2 or p.shape[0] < 2:
        raise ValueError("prix doit être une matrice (T ≥ 2) × N")
    immobile = np.abs(np.diff(p, axis=0)) < 1e-12
    # Le marché bouge-t-il ce jour-là ? Sinon (jour férié global), on ne reproche rien.
    marche_bouge = (~immobile).sum(axis=1) > 0.5 * p.shape[1]
    out = []
    for j in range(p.shape[1]):
        serie = immobile[:, j] & marche_bouge
        # On repère les ÉPISODES complets, pas leur début. La première version
        # publiait l'entrée au moment où le compteur atteignait le seuil, donc
        # `jours` valait toujours exactement le seuil : une série figée deux cents
        # séances s'annonçait « 5 séances ». Vu sur données réelles le 08/09 — le
        # chiffre était faux dans le sens qui minimise le problème, le pire des deux.
        debut = None
        for t in range(len(serie) + 1):
            fige = bool(serie[t]) if t < len(serie) else False
            if fige and debut is None:
                debut = t
            elif not fige and debut is not None:
                duree = t - debut
                if duree >= jours_min:
                    out.append({"actif_index": int(j), "depuis_index": int(debut),
                                "jusqu_index": int(t - 1), "jours": int(duree),
                                "motif": (f"cours identique sur {duree} séances "
                                          f"(indices {debut} à {t - 1}) alors que le "
                                          "marché cote — flux probablement arrêté")})
                debut = None
    return out


# Au-delà de ce rendement quotidien, ce n'est plus un mouvement de marché : c'est une
# donnée cassée. Aucun actif ne fait +1 000 % en une séance ; quand on le lit, c'est que
# le prix de la veille était faux (souvent proche de zéro), pas que le cours a bondi.
SEUIL_CORRUPTION = 10.0        # +1000 %
SEUIL_SPLIT = 0.30             # au-delà : possible division/regroupement non ajusté


def gravite_du_saut(rendement: float) -> str:
    """Nomme ce qu'on regarde. « Split non ajusté » et « prix cassé » appellent des
    gestes opposés : l'un se corrige par un facteur d'ajustement, l'autre exige de
    retirer la série jusqu'à ce que la source soit réparée."""
    a = abs(float(rendement))
    if a >= SEUIL_CORRUPTION:
        return "donnée cassée"
    if a >= SEUIL_SPLIT:
        return "split non ajusté ?"
    return "valeur extrême"


def resumer_par_actif(rapport: dict, symboles: list[str]) -> list[dict]:
    """Agrège les anomalies PAR ACTIF, du plus atteint au moins atteint.

    Cinq mille événements bruts sont illisibles et donc inutiles : personne ne les
    parcourt, et un rapport qu'on ne lit pas ne protège de rien. Ce qui se décide, ce
    n'est pas « ce point du 12 mars », c'est « cette série est-elle exploitable ».
    """
    par: dict[int, dict] = {}
    for s in rapport.get("sauts_isoles", []):
        d = par.setdefault(s["actif_index"], {"sauts": 0, "pire": 0.0, "figees": 0,
                                              "jours_figes": 0, "gravite": "—"})
        d["sauts"] += 1
        if abs(s["rendement"]) > abs(d["pire"]):
            d["pire"] = s["rendement"]
            d["gravite"] = gravite_du_saut(s["rendement"])
    for f in rapport.get("series_figees", []):
        d = par.setdefault(f["actif_index"], {"sauts": 0, "pire": 0.0, "figees": 0,
                                              "jours_figes": 0, "gravite": "—"})
        d["figees"] += 1
        d["jours_figes"] += f["jours"]
    lignes = [{"symbole": symboles[i] if i < len(symboles) else str(i), **v}
              for i, v in par.items()]
    lignes.sort(key=lambda d: (-abs(d["pire"]), -d["jours_figes"]))
    return lignes


def auditer_panel(prix: np.ndarray, seuil: float = SEUIL_ECART,
                  jours_min: int = JOURS_FIGES_MIN) -> dict:
    """Audit croisé complet d'un panneau de prix (T dates × N actifs).

    Rend un verdict lisible ET les anomalies détaillées. `ok` reste vrai tant qu'aucune
    anomalie n'est trouvée : c'est un rapport, jamais un blocage — corriger des données
    de marché sans qu'un humain l'ait décidé effacerait la trace du problème.
    """
    p = np.asarray(prix, float)
    if p.ndim != 2 or p.shape[0] < 3:
        raise ValueError("prix doit être une matrice (T ≥ 3) × N")
    with np.errstate(divide="ignore", invalid="ignore"):
        rendements = np.diff(p, axis=0) / np.where(p[:-1] == 0, np.nan, p[:-1])
    sauts = ecart_a_la_coupe(rendements, seuil)
    figees = series_figees(p, jours_min)
    return {
        "ok": not sauts and not figees,
        "n_dates": int(p.shape[0]), "n_actifs": int(p.shape[1]),
        "sauts_isoles": sauts, "series_figees": figees,
        "resume": (f"{len(sauts)} mouvement(s) incohérent(s) avec le marché du jour, "
                   f"{len(figees)} série(s) probablement figée(s)"),
    }
