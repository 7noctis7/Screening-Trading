"""Métriques de SURVIE : Ulcer, temps sous l'eau, linéarité de l'equity, ES modifié.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09), bloc 4. Complète `portfolio/metrics` (Sharpe,
Sortino, maxDD, Calmar) et `portfolio/risk_metrics` (VaR/CVaR historiques et
paramétriques) par les quatre mesures qui manquaient.

POURQUOI CES QUATRE-LÀ, ET PAS D'AUTRES RATIOS. Le maxDD est un MAXIMUM : il ne dit rien
de la durée. Deux courbes peuvent afficher -20 % l'une et l'autre, l'une s'en remettant
en trois semaines, l'autre restant sous l'eau trois ans. L'Ulcer et le temps sous l'eau
séparent ces deux cas ; le maxDD seul les confond.

LA VaR GAUSSIENNE MENT SUR LES QUEUES, ET ELLE MENT DANS LE MAUVAIS SENS. Les rendements
financiers sont asymétriques et leptokurtiques : à 99 %, la VaR normale SOUS-ESTIME la
perte, donc rassure exactement là où il faudrait alerter. L'expansion de Cornish-Fisher
corrige le quantile par le skew et le kurtosis observés. Elle reste une APPROXIMATION —
elle ne devient pas fiable pour un kurtosis extrême, et cesse même d'être monotone
au-delà d'un certain point ; on le vérifie plutôt que de le supposer.

CE QUE CES CHIFFRES NE FONT PAS. Aucun d'eux ne mesure un avantage. Une stratégie sans
espérance positive peut afficher un Ulcer excellent : il suffit qu'elle ne fasse rien.
Ils décrivent la FORME du risque, jamais l'existence du rendement.
"""

from __future__ import annotations

import math

_PPA = 252.0        # périodes par an (barres quotidiennes)


def _finis(serie) -> list[float]:
    """Points finis uniquement. Un NaN est un incident de données, pas une valeur."""
    out = []
    for v in (serie if serie is not None else []):
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out.append(x)
    return out


def serie_drawdown(equity) -> list[float]:
    """Drawdown en fraction à chaque point (0 au sommet, négatif en dessous)."""
    eq = _finis(equity)
    dd, sommet = [], None
    for v in eq:
        sommet = v if sommet is None or v > sommet else sommet
        dd.append((v / sommet - 1.0) if sommet and sommet > 0 else 0.0)
    return dd


def ulcer_index(equity) -> dict:
    """Ulcer Index : racine de la moyenne des drawdowns AU CARRÉ, en POINTS DE %.

    Le carré est ce qui fait tout : il pénalise une chute profonde bien plus qu'une
    longue érosion, et rend l'indice sensible à la DURÉE autant qu'à l'amplitude — un
    drawdown deux fois plus long compte deux fois, un drawdown deux fois plus profond
    compte quatre fois.

    L'unité est le POINT DE POURCENTAGE, pas la fraction : la cible « UI <= 4,5 » de la
    spec ne veut rien dire sans ça (4,5 % de drawdown quadratique moyen, pas 450 %).
    """
    dd = serie_drawdown(equity)
    if len(dd) < 30:
        return {"available": False, "motif": "moins de 30 points"}
    moyenne_carres = sum((d * 100.0) ** 2 for d in dd) / len(dd)
    return {"available": True, "ulcer": round(math.sqrt(moyenne_carres), 3),
            "n": len(dd)}


def temps_sous_l_eau(equity) -> dict:
    """Part du temps passée sous le précédent sommet, et plus longue série continue.

    On compte STRICTEMENT sous le sommet : un point exactement AU sommet n'est pas sous
    l'eau, et compter l'égalité gonflerait mécaniquement la mesure sur une courbe plate.
    """
    dd = serie_drawdown(equity)
    if len(dd) < 30:
        return {"available": False, "motif": "moins de 30 points"}
    sous = [d < 0 for d in dd]
    plus_longue, courante = 0, 0
    for x in sous:
        courante = courante + 1 if x else 0
        plus_longue = max(plus_longue, courante)
    return {"available": True, "part_sous_l_eau": round(sum(sous) / len(sous), 4),
            "plus_longue_serie": plus_longue,
            "plus_longue_annees": round(plus_longue / _PPA, 2), "n": len(dd)}


def r2_linearite(equity) -> dict:
    """R² d'une régression linéaire sur la courbe d'equity — sa « régularité ».

    ATTENTION À CE QUE CE CHIFFRE MESURE VRAIMENT, ET LA SPEC S'Y TROMPE. Sur une equity
    en croissance composée, la courbe est EXPONENTIELLE : une régression linéaire y
    obtient un R² médiocre alors même que la stratégie est parfaitement régulière. On
    régresse donc le LOG de l'equity, où une croissance à taux constant est une droite
    exacte. Régresser le niveau reviendrait à sanctionner la capitalisation.

    ET CE QU'IL NE MESURE PAS : un R² élevé ne prouve aucun avantage — un placement
    monétaire affiche 0,999. Il ne dit que ceci : la performance ne tient pas à quelques
    barres. Utilisé seul comme critère, il sélectionne les stratégies les plus plates.
    """
    eq = [v for v in _finis(equity) if v > 0]
    n = len(eq)
    if n < 30:
        return {"available": False, "motif": "moins de 30 points"}
    y = [math.log(v) for v in eq]
    mx = (n - 1) / 2.0
    my = sum(y) / n
    sxx = sum((i - mx) ** 2 for i in range(n))
    sxy = sum((i - mx) * (y[i] - my) for i in range(n))
    syy = sum((v - my) ** 2 for v in y)
    if sxx <= 0 or syy <= 0:
        return {"available": False, "motif": "courbe constante — R² indéfini"}
    r2 = (sxy * sxy) / (sxx * syy)
    return {"available": True, "r2": round(r2, 4), "pente_log_par_barre": sxy / sxx,
            "n": n, "echelle": "log"}


def _moments(r: list[float]) -> tuple[float, float, float, float]:
    """(moyenne, écart-type, skew, kurtosis EXCÉDENTAIRE)."""
    n = len(r)
    m = sum(r) / n
    var = sum((x - m) ** 2 for x in r) / n
    sd = math.sqrt(var)
    if sd <= 0:
        return m, 0.0, 0.0, 0.0
    s = sum(((x - m) / sd) ** 3 for x in r) / n
    k = sum(((x - m) / sd) ** 4 for x in r) / n - 3.0
    return m, sd, s, k


def _z_normal(p: float) -> float:
    """Quantile de la loi normale (Acklam), suffisant à 1e-9 sur ]0,1[."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _z_cornish_fisher(z: float, s: float, k: float) -> float:
    """Quantile normal corrigé par le skew `s` et le kurtosis excédentaire `k`."""
    return (z
            + (z * z - 1) * s / 6.0
            + (z ** 3 - 3 * z) * k / 24.0
            - (2 * z ** 3 - 5 * z) * s * s / 36.0)


def _derivee_cornish_fisher(z: float, s: float, k: float) -> float:
    """Pente de l'expansion en `z`. Négative = la transformation n'est plus un quantile.

    C'est LE test de domaine, et il n'est pas décoratif : au-delà d'un certain couple
    (skew, kurtosis) le polynôme de Cornish-Fisher cesse d'être croissant, donc cesse
    d'être une fonction quantile. Les formules continuent pourtant de rendre un nombre —
    d'où des ES aberrants publiés en toute confiance dans beaucoup d'outils.
    """
    return (1.0
            + z * s / 3.0
            + (3 * z * z - 3) * k / 24.0
            - (6 * z * z - 5) * s * s / 36.0)


def _es_modifie(m: float, sd: float, zcf: float, s: float, k: float, p: float) -> float:
    """ES modifié de Boudt, Peterson & Croux (2008), formule complète.

    Le crochet corrige la moyenne de queue gaussienne par les mêmes moments que le
    quantile. L'omettre — n'évaluer que la densité normale AU quantile corrigé — donne
    une queue systématiquement trop légère : la correction de la VaR est alors annulée
    par un ES qui, lui, n'a pas été corrigé. C'est l'erreur que ce module a commise
    avant que le test `test_cornish_fisher_aggrave_la_queue` ne la fasse tomber.
    """
    z2, z3, z4, z6 = zcf ** 2, zcf ** 3, zcf ** 4, zcf ** 6
    crochet = (1.0
               + z3 * s / 6.0
               + (z6 - 9 * z4 + 9 * z2 + 3) * s * s / 72.0
               + (z4 - 2 * z2 - 1) * k / 24.0)
    dens = math.exp(-0.5 * zcf * zcf) / math.sqrt(2 * math.pi)
    return m - sd * dens * crochet / p


def var_es_cornish_fisher(rendements, alpha: float = 0.99) -> dict:
    """VaR et Expected Shortfall MODIFIÉS à `alpha`, corrigés du skew et du kurtosis.

    LE DOMAINE DE VALIDITÉ EST VÉRIFIÉ, PAS SUPPOSÉ, et trois conditions sont exigées :
      · l'expansion doit être CROISSANTE au point d'évaluation (sinon ce n'est plus un
        quantile) ;
      · la correction doit AGGRAVER la queue gauche, jamais l'alléger — une mesure de
        queue qui rassure est le mode de panne qu'on veut exclure ;
      · l'ES ne peut pas être plus sévère que la pire observation de l'échantillon : un
        ES à -60 % sur mille points dont le pire vaut -9 % signale une expansion partie
        en vrille, pas un risque découvert.
    Si l'une échoue, on renvoie `valide: False` et la version HISTORIQUE, en le disant.

    Ce garde-fou n'est pas théorique : sur une distribution très asymétrique et très
    leptokurtique (skew -4, kurtosis +15), l'expansion sort du domaine et produit un ES
    six fois pire que la pire perte jamais observée.
    """
    r = _finis(rendements)
    if len(r) < 100:
        return {"available": False, "motif": "moins de 100 rendements"}
    m, sd, s, k = _moments(r)
    if sd <= 0:
        return {"available": False, "motif": "écart-type nul"}
    p = 1.0 - alpha
    z = _z_normal(p)
    zcf = _z_cornish_fisher(z, s, k)
    var_cf = m + sd * zcf
    es_cf = _es_modifie(m, sd, zcf, s, k, p)
    dens_g = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    var_g, es_g = m + sd * z, m - sd * dens_g / p
    ordonnes = sorted(r)
    coupe = max(1, int(p * len(ordonnes)))
    es_hist, var_hist = sum(ordonnes[:coupe]) / coupe, float(ordonnes[coupe - 1])
    croissante = _derivee_cornish_fisher(z, s, k) > 0
    aggrave = zcf <= z + 1e-12
    plausible = es_cf >= min(r)
    valide = croissante and aggrave and plausible
    controles = (("expansion non croissante — hors domaine", croissante),
                 ("correction qui allège la queue", aggrave),
                 ("ES sous la pire observation — divergence", plausible))
    motifs = [] if valide else [txt for txt, ok in controles if not ok]
    return {"available": True, "alpha": alpha, "valide": bool(valide),
            "var_modifiee": round(var_cf if valide else var_hist, 6),
            "es_modifie": round(es_cf if valide else es_hist, 6),
            "var_gaussienne": round(var_g, 6), "es_gaussien": round(es_g, 6),
            "es_historique": round(es_hist, 6), "var_historique": round(var_hist, 6),
            "skew": round(s, 4), "kurtosis_excedentaire": round(k, 4), "n": len(r),
            "motif": "" if valide else " ; ".join(motifs) + " — repli historique"}


def profil_de_survie(equity, rendements=None, alpha: float = 0.99) -> dict:
    """Les quatre mesures en un appel, sur la MÊME courbe — pour les lire ensemble.

    Séparées, chacune se laisse optimiser seule ; ensemble, elles se contredisent, et
    c'est le but : on ne peut pas améliorer l'Ulcer sans toucher au temps sous l'eau.
    """
    eq = _finis(equity)
    if rendements is None:
        rendements = [eq[i] / eq[i - 1] - 1.0
                      for i in range(1, len(eq)) if eq[i - 1] > 0]
    return {"ulcer": ulcer_index(eq), "sous_l_eau": temps_sous_l_eau(eq),
            "linearite": r2_linearite(eq),
            "queue": var_es_cornish_fisher(rendements, alpha)}
