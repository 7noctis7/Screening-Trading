"""Constantes et sélection d'univers du preset — socle partagé.

Extrait de `preset_backtest.py` (793 lignes) le 25/08 pour respecter la règle
d'architecture < 400 lignes/fichier. Aucun changement de comportement : les valeurs
et la logique sont reprises à l'identique.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.panel import (
    COUVERTURE_DEFAUT,
    aligner_par_date,
    fenetre_commune,
)

# ALIGNEMENT PAR DATE ACTIVÉ — mesuré puis gaté le 25/08 au soir, jamais activé en silence.
#
# `make diag-alignement` sur les données réelles (929 instruments) a décomposé le gain :
#     effet ALIGNEMENT, à univers comparable : ΔSharpe +0,59 (0,92 → 1,51)
#                                              maxDD  −19,4 % → −8,7 %
#     effet UNIVERS (le reste)               : ΔSharpe −0,17
# L'essentiel vient donc de la CORRECTION, pas d'un tirage d'univers plus chanceux — l'effet
# univers jouait même contre.
#
# LE MÉCANISME, vérifié par l'arithmétique. L'empilement positionnel prend les L dernières
# barres de chaque série et les superpose. Avec L = 2761 : une action (5 séances/semaine)
# remonte à 2015, une crypto (7 j/7) remonte à 2018. Les deux occupaient la MÊME colonne,
# décalées de TROIS ANS. Conséquence visible dans le diagnostic : le momentum crypto, mesuré
# sur une fenêtre 2018-2026, écrasait celui des actions, et le top-30 comptait douze paires
# crypto sélectionnées par pur artefact de calendrier.
#
# `aligner_dates=False` reproduit l'ancien comportement, pour comparaison uniquement.
ALIGNEMENT_PAR_DEFAUT = True

# EXÉCUTION DÉCALÉE D'UNE BARRE — activée le 25/08 au soir.
#
# `exec_lag = 0` remplissait au close de la barre de SIGNAL : un cours qui n'était pas
# exécutable au moment de la décision. Le dépôt le documentait lui-même comme un « mini
# look-ahead » et attendait de le chiffrer avant de le retirer.
#
# Chiffré sur données réelles, une fois l'alignement par date en place :
#     base (fill au signal)     Sharpe 1,34 · Sortino 2,95 · maxDD −11,0 % · turn. 1,48×
#     fill t+1 (réaliste)       Sharpe 1,35 · Sortino 3,06 · maxDD  −8,5 % · turn. 1,48×
#
# Meilleur sur TOUTES les colonnes. Le gate du labo l'avait pourtant rejeté, parce qu'il exige
# +0,05 de Sharpe : il demande « ce levier apporte-t-il de la valeur ? ». Ce n'est pas la bonne
# question ici. `exec_lag=0` n'est pas un levier, c'est un biais connu — et on ne garde pas un
# biais au motif que le retirer ne rapporte pas assez. Surtout quand le retirer ne coûte rien.
#
# `exec_lag=0` reste disponible pour reproduire l'ancien comportement.
EXEC_LAG_PAR_DEFAUT = 1

# `regime_mult` calcule une MM200 (`hist[-200:]`) et un pic historique. En dessous de ce
# nombre de barres, les deux sont silencieusement faux : la « MM200 » devient une moyenne plus
# courte, et le pic ignore tout ce qui précède la fenêtre.
MIN_BARRES_REGIME = 200


def momentum_rank(M: dict, syms: list, s0: int, top_k: int) -> list:
    """Classement momentum au point `s0`, borne basse ramenée à 0 (cf. `_price_universe`).

    Un titre non coté à l'une des deux bornes n'a pas de momentum mesurable : l'exclure est
    la seule réponse honnête (neutre si la matrice est complète).
    """
    b0 = max(0, s0 - 252 - 1)
    sel = {s: float(M[s][s0 - 1] / M[s][b0] - 1)
           for s in syms
           if len(M[s]) > s0 and np.isfinite(M[s][s0 - 1])
           and np.isfinite(M[s][b0]) and M[s][b0] > 0}
    return (sorted(sel, key=lambda s: sel[s], reverse=True)[:top_k]
            if len(sel) >= 5 else list(syms)[:top_k])


def _price_universe(data: dict, syms: list, lookback: int, top_k: int,
                    couverture: float = COUVERTURE_DEFAUT) -> list:
    """#2 ANTI-FUITE (partagé) : univers = top-K par MOMENTUM prix-only mesuré au DÉBUT de la
    fenêtre commune (aucune info future ; on n'applique JAMAIS le score qualité du JOUR à des dates
    passées). Miroir exact de `preset_backtest(legacy_quality_universe=False)`, réutilisé par les
    fonctions dashboard/ledger (sinon elles ré-introduisent le look-ahead + le biais du survivant).

    La fenêtre est celle du panel (cf. `packages/backtest/panel`) et non `min(len)` : sinon une
    seule introduction récente ramenait la fenêtre à ~13 mois et l'univers de TOUTES les fonctions
    dashboard/ledger était sélectionné sur ce moignon.

    NB sur l'horizon : `_s0 - 252 - 1` est presque toujours négatif, donc l'indice est ramené à 0
    et le classement porte sur l'historique DISPONIBLE avant le premier pas (~`lookback` barres),
    pas sur 12 mois. Ce n'est pas un bug : 252 barres antérieures à `start` n'existent pas sans
    décaler le premier rebalancement — les prendre serait une fuite."""
    if len(syms) < 5:
        return syms[:top_k]
    if ALIGNEMENT_PAR_DEFAUT:
        # Le classement de momentum comparait des fenêtres de calendriers DIFFÉRENTS : trois ans
        # d'écart entre une crypto et une action au même index, ce qui plaçait douze paires
        # crypto dans le top-30 par artefact. La sélection doit porter sur des dates communes.
        syms, _dates, A, _diag = aligner_par_date(data, list(syms), couverture=couverture)
        if len(syms) < 5:
            return list(syms)[:top_k]
        M = {s: A[i] for i, s in enumerate(syms)}
    else:
        syms, L, _ = fenetre_commune(data, list(syms), couverture=couverture)
        if len(syms) < 5:
            return list(syms)[:top_k]
        M = {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}
    return momentum_rank(M, syms, max(lookback, 50), top_k)
