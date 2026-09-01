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


N_MELANGES = 20                  # tirages de référence pour le témoin sans dépendance


def _largeur_temoin(x, n_boot: int, seed: int, bloc: int) -> float:
    """Largeur d'IC ATTENDUE en l'absence de dépendance, sur cette série précise.

    UN SEUL mélange ne suffit pas, et c'est mesurable : un échantillon i.i.d. de 600
    points porte par hasard de l'autocorrélation locale, si bien qu'un unique tirage de
    référence donne un rapport de 1,15 là où la vérité est 1. On prend donc la MÉDIANE
    sur plusieurs mélanges — c'est la largeur attendue, débarrassée de la chance d'un
    ordre particulier.
    """
    arr = np.asarray([v for v in _seq(x) if _fini(v)], float)
    rng = np.random.default_rng(seed)
    largeurs = [_largeur_ic(rng.permutation(arr), max(n_boot // 5, 200), seed + k, bloc)
                for k in range(N_MELANGES)]
    return float(np.median(largeurs))


def _largeur_ic(x, n_boot: int, seed: int, bloc: int | None) -> float:
    """Largeur d'intervalle NON ARRONDIE.

    La version publiée arrondit à deux décimales. Sur des R d'amplitude 0,16 cela
    suffit à fabriquer un rapport de 1,19 là où il n'y a rigoureusement rien à mesurer —
    un « biais du bootstrap par blocs » entièrement imaginaire. Une comparaison de deux
    largeurs doit partir des valeurs brutes.
    """
    arr = np.asarray([v for v in _seq(x) if _fini(v)], float)
    moyennes = _bootstrap(arr, n_boot, seed, bloc).mean(axis=1)
    lo, hi = np.percentile(moyennes, [2.5, 97.5])
    return float(hi - lo)


def dependance(pnls, n_boot: int = N_BOOTSTRAP, seed: int = 7) -> dict:
    """Corrige le t de la DÉPENDANCE entre trades qui se chevauchent.

    Deux positions ouvertes en même temps encaissent le même choc de marché : elles ne
    valent pas deux observations. Le bootstrap par blocs conserve la dépendance locale
    et élargit l'intervalle en conséquence.

    LA RÉFÉRENCE N'EST PAS LE BOOTSTRAP I.I.D., mais la même série MÉLANGÉE plusieurs
    fois : même longueur, même distribution, même longueur de bloc, dépendance détruite.
    Comparer des blocs à des blocs annule tout biais propre à l'estimateur, et isole ce
    que l'ORDRE CHRONOLOGIQUE ajoute — lui seul :

        inflation = largeur(blocs, série) / largeur(blocs, série mélangée)
        t_effectif = t_naïf / inflation        n_effectif = n / inflation²

    PRÉCISION DE L'ESTIMATEUR, mesurée et non supposée. Sur 30 séries de 600 points sans
    aucune dépendance : médiane 1,004, moyenne 1,010 — il est bien centré sur 1. Mais
    son écart-type vaut 0,14, et l'étendue p5-p95 va de 0,79 à 1,23. À cette taille
    d'échantillon, `inflation` se lit donc comme un ORDRE DE GRANDEUR — « autour de 1,
    pas de dépendance notable » contre « autour de 3, forte dépendance » — jamais comme
    un diviseur précis. Le `t_effectif` en hérite : ±15 % environ.

    EXIGENCE. Les blocs n'ont de sens que sur une séquence CHRONOLOGIQUE. Sur une liste
    déjà mélangée, la dépendance a disparu et la correction ne mesure plus rien —
    l'appelant doit trier avant d'appeler.
    """
    x = [v for v in _seq(pnls) if _fini(v)]
    iid = significativite(x, n_boot=n_boot, seed=seed)
    if "t_esperance" not in iid:
        return {}
    b = bloc_conseille(len(x))
    lb = _largeur_ic(x, n_boot, seed, b)
    l0 = _largeur_temoin(x, n_boot, seed, b)
    if l0 <= 0:
        return {}
    infl = lb / l0
    return {"inflation_ecart_type": round(infl, 3),
            "t_effectif": round(iid["t_esperance"] / infl, 3),
            "n_effectif": int(len(x) / infl ** 2)}


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
    # le t en R subit la MÊME dépendance que le t en dollars : le publier en i.i.d.
    # seul reproduirait, sur la mesure censée corriger, l'optimisme qu'on dénonce.
    dep = dependance(rs)
    return {"couverture_R_pct": round(couverture * 100, 1),
            "t_esperance_en_R": en_r.get("t_esperance"),
            "t_effectif_en_R": dep.get("t_effectif"),
            "n_effectif_en_R": dep.get("n_effectif"),
            "n_trades_pour_conclure_en_R": en_r.get("n_trades_pour_conclure"),
            "gain_de_t_si_risque_egal_pct": gain,
            **{f"{k}_en_R": v for k, v in concentration(rs).items()}}
