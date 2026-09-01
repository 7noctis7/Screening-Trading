"""Fragilité d'un historique de trades : l'avantage est-il un avantage, ou une poignée
de coups de chance ?

POURQUOI CE MODULE EXISTE. Un profit factor de 1,19 se lit spontanément « léger
avantage ». Il peut aussi bien décrire un système dont la totalité du gain tient dans
cinq trades sur cinq cents. Les deux situations donnent le MÊME profit factor et
appellent des décisions opposées : la première se dimensionne, la seconde s'arrête.

Trois questions, trois mesures, et aucune ne se déduit des deux autres :

1. LA MARGE. Le payoff dépasse-t-il le seuil que le taux de réussite lui impose ?
   Un payoff seul ne dit rien : il ne se lit que contre (1 − p) / p.

2. LA CONCENTRATION. Combien de trades portent le résultat ? La mesure décisive est
   le profit factor RECALCULÉ SANS LES k MEILLEURS. Si retirer cinq trades sur cinq
   cents fait passer le système sous 1, l'espérance ne repose pas sur une régularité.

3. LA SIGNIFICATIVITÉ. L'espérance est-elle distinguable de zéro ? Sur quelques
   centaines de trades à profit factor proche de 1, la réponse est souvent non — et
   c'est une information, pas un détail de statisticien : elle dit que le chiffre
   affiché ne permet PAS de conclure, ni dans un sens ni dans l'autre.

CE QUE CE MODULE NE FAIT PAS. Il ne juge pas la stratégie. Il dit ce que l'échantillon
autorise à affirmer. Un système peut être bon et son historique trop court pour le
prouver ; les deux énoncés sont compatibles et il faut les tenir ensemble.
"""

from __future__ import annotations

import math

import numpy as np

K_CONCENTRATION = 5              # « top 5 » — ordre de grandeur, pas seuil calibré
N_BOOTSTRAP = 4000
T_CIBLE = 2.0                    # t visé pour « conclure » (~5 % bilatéral)


def marge_de_payoff(pnls) -> dict:
    """De combien le payoff dépasse le SEUIL DE RENTABILITÉ imposé par le taux de
    réussite, soit (1 − p) / p. À 31,7 % de réussite il faut 2,16 pour ne rien gagner.

    Le seuil est très sensible au taux de réussite — sa dérivée vaut −1/p², donc près
    de 30 % un point de réussite en plus abaisse le seuil d'environ 0,10. C'est le
    levier le plus puissant du tableau, et le moins intuitif.
    """
    g, p_ = _separe(pnls)
    if not g or not p_:
        return {}
    taux = len(g) / (len(g) + len(p_))
    seuil = (1.0 - taux) / taux
    paye = (sum(g) / len(g)) / (-sum(p_) / len(p_))
    marge = round((paye / seuil - 1.0) * 100.0, 1) if seuil else None
    return {"payoff": round(paye, 2), "payoff_seuil": round(seuil, 2),
            "marge_payoff_pct": marge}


def concentration(pnls, k: int = K_CONCENTRATION) -> dict:
    """Combien de trades portent le résultat, et que reste-t-il sans eux.

    `profit_factor_sans_top{k}` est la mesure DÉCISIVE, et elle est délibérément
    brutale : elle retire les k meilleurs trades et recalcule. Passer sous 1,00 signifie
    que l'espérance dépend de la reproduction de ces k trades — une hypothèse sur
    l'avenir, pas une propriété mesurée du passé.

    On préfère cette forme à une « part du gain NET » : avec un profit factor proche de
    1 le net tend vers zéro, et tout ratio qui le prend au dénominateur explose.
    """
    g, p_ = _separe(pnls)
    if not g or not p_:
        return {}
    perte = -sum(p_)
    tries = sorted(g, reverse=True)
    cumul, n_couvre = 0.0, 0
    while n_couvre < len(tries) and cumul < perte:
        cumul += tries[n_couvre]
        n_couvre += 1
    reste = sum(tries[k:])
    return {
        "n_gagnants_couvrant_les_pertes": n_couvre if cumul >= perte else None,
        f"part_top{k}_du_gain_brut_pct": round(sum(tries[:k]) / sum(g) * 100.0, 1),
        f"profit_factor_sans_top{k}": round(reste / perte, 3) if perte > 0 else None,
        f"net_sans_top{k}": round(reste - perte, 2),
    }


def significativite(pnls, n_boot: int = N_BOOTSTRAP, seed: int = 7,
                    bloc: int | None = None) -> dict:
    """L'espérance par trade est-elle distinguable de zéro ?

    `t_esperance` est le t de Student de la moyenne des P&L. `p_esperance_negative` est
    la part des rééchantillonnages dont la moyenne est ≤ 0 — la probabilité, sous le
    seul échantillon observé, de ne pas avoir d'avantage du tout.

    HYPOTHÈSE, ET ELLE EST OPTIMISTE. Le tirage i.i.d. suppose les trades indépendants.
    Des positions qui se chevauchent dans le temps partagent le même choc de marché :
    l'échantillon effectif est alors plus petit que `n`, et le t réel plus bas. D'où
    `bloc` : un bootstrap par blocs mobiles sur la séquence CHRONOLOGIQUE, qui conserve
    la dépendance locale. La longueur usuelle est de l'ordre de √n.
    """
    x = np.asarray([v for v in _seq(pnls) if _fini(v)], float)
    n = x.size
    if n < 30:
        return {"significativite": "UNCALIBRATED",
                "motif": f"{n} trades clôturés — trop peu pour conclure"}
    sd = float(x.std(ddof=1))
    moy = float(x.mean())
    t = moy / sd * math.sqrt(n) if sd > 0 else 0.0
    tirages = _bootstrap(x, n_boot, seed, bloc)
    moyennes = tirages.mean(axis=1)
    return {
        "t_esperance": round(t, 3),
        "p_esperance_negative": round(float((moyennes <= 0).mean()), 4),
        "esperance_ic95": [round(float(v), 2)
                           for v in np.percentile(moyennes, [2.5, 97.5])],
        "n_trades_pour_conclure": (int(math.ceil((T_CIBLE * sd / moy) ** 2))
                                   if moy > 0 else None),
        "bootstrap_bloc": bloc,
    }


def _bootstrap(x: np.ndarray, n_boot: int, seed: int, bloc: int | None) -> np.ndarray:
    """Rééchantillonnage — i.i.d. si `bloc` est None, par blocs mobiles sinon."""
    rng = np.random.default_rng(seed)
    n = x.size
    if not bloc or bloc < 2 or bloc >= n:
        return rng.choice(x, size=(n_boot, n), replace=True)
    n_blocs = int(math.ceil(n / bloc))
    debuts = rng.integers(0, n - bloc + 1, size=(n_boot, n_blocs))
    idx = (debuts[:, :, None] + np.arange(bloc)[None, None, :]).reshape(n_boot, -1)
    return x[idx[:, :n]]


def bloc_conseille(n: int) -> int:
    """√n — le choix usuel quand la structure de dépendance n'est pas connue."""
    return max(2, int(round(math.sqrt(max(n, 1)))))


def _seq(serie) -> list:
    """Le seul test permis sur une séquence est `is None` : sur un ndarray, toute autre
    forme de vérité (`x or []`) lève « truth value ambiguous ». Leçon du 01/09."""
    return [] if serie is None else list(serie)


def _separe(pnls) -> tuple[list[float], list[float]]:
    vals = [float(v) for v in _seq(pnls) if _fini(v)]
    return [v for v in vals if v > 0], [v for v in vals if v <= 0]


def _fini(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def comparer_dimensionnement(pnls, r_multiples) -> dict:
    """Queue épaisse RÉELLE, ou simple loterie de dimensionnement ?

    La distinction est décisive et elle est mesurable. Le R d'un trade vaut
    (sortie − entrée) / (entrée − stop) : c'est son résultat exprimé en unités de
    RISQUE ENGAGÉ, donc débarrassé de la taille de la position. Or dimensionner à risque
    égal signifie choisir la quantité telle que qty × (entrée − stop) soit constante —
    auquel cas le P&L de chaque trade devient exactement proportionnel à son R.

    Le t calculé sur les R n'est donc pas une analogie : c'est le t QU'ON AURAIT OBTENU,
    à signaux identiques, si chaque trade avait risqué le même montant. L'écart entre
    les deux t se lit directement :

      · t(R) nettement supérieur à t($) → la dispersion vient de la TAILLE des
        positions, pas du signal. Le risque égal relève alors le t sans exiger le
        moindre alpha nouveau ;
      · t(R) comparable → la queue est structurelle, elle appartient à la stratégie, et
        aucun dimensionnement ne la fera disparaître.

    LIMITE À GARDER EN TÊTE. La contrefactuelle suppose les mêmes entrées et sorties. En
    pratique, redimensionner change le capital disponible, donc les trades qu'on peut
    prendre. L'écart mesuré est une INDICATION FORTE, pas une promesse de résultat.
    """
    # `zip(..., strict=True)` DÉLIBÉRÉMENT : les deux séries sont indexées par trade.
    # Une longueur qui diverge est un défaut d'appelant, et apparier un P&L au R d'un
    # AUTRE trade produirait un chiffre faux tout en restant parfaitement lisible.
    p_, r_ = _seq(pnls), _seq(r_multiples)
    couples = [(float(a), float(b)) for a, b in zip(p_, r_, strict=True)
               if _fini(a) and _fini(b)]
    n_pnl = len([v for v in p_ if _fini(v)])
    if not n_pnl:
        return {}
    couverture = len(couples) / n_pnl
    if couverture < 0.90:
        return {"dimensionnement": "UNCALIBRATED",
                "motif": f"R connu sur {couverture:.0%} des trades — insuffisant",
                "couverture_R_pct": round(couverture * 100, 1)}
    rs = [r for _, r in couples]
    t_dollars = significativite([p for p, _ in couples]).get("t_esperance")
    en_r = significativite(rs)
    gain = (round((en_r["t_esperance"] / t_dollars - 1.0) * 100.0, 1)
            if t_dollars and t_dollars > 0 and en_r.get("t_esperance") else None)
    return {"couverture_R_pct": round(couverture * 100, 1),
            "t_esperance_en_R": en_r.get("t_esperance"),
            "n_trades_pour_conclure_en_R": en_r.get("n_trades_pour_conclure"),
            "gain_de_t_si_risque_egal_pct": gain,
            **{f"{k}_en_R": v for k, v in concentration(rs).items()}}
