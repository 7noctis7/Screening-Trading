"""Deux Sharpe qui diffèrent de 0,07 sont-ils DIFFÉRENTS ? — Jobson-Korkie/Memmel.

Le gate du labo compare des estimations PONCTUELLES à un seuil fixe (+0,05). Sur
126 pas, cela revient à lire une différence sans savoir si elle est distinguable
de zéro. Constat du 25/08 : neuf leviers « rejetés » avec des ΔSharpe de −0,01 à
−0,12, présentés comme neuf verdicts distincts alors qu'ils sont peut-être tous
le même — « on ne voit pas de différence ».

Ce module ne tranche pas à la place du gate : il dit ce que la donnée PERMET de
dire.

POURQUOI PAS UNE SIMPLE ERREUR-TYPE. Les deux variantes tournent sur les MÊMES
dates, avec des positions largement communes : leurs rendements sont fortement
corrélés (ρ souvent > 0,95). Traiter les échantillons comme indépendants
surestimerait massivement l'incertitude et rendrait tout indiscernable.
Jobson-Korkie (1981), avec la correction de Memmel (2003), donne la variance
asymptotique de la DIFFÉRENCE en tenant compte de ρ :

    Var(S1 − S2) ≈ (1/N) · [ 2(1−ρ) + ½(S1² + S2² − 2ρ² S1 S2) ]

où S1, S2 sont les Sharpe PAR PÉRIODE (non annualisés) et N le nombre de pas.

Calibration vérifiée par Monte-Carlo dans les tests : ~5 % de rejets sous H0, à
ρ = 0,99 / 0,95 / 0,00. Un test non calibré serait pire qu'aucun test — il
donnerait une autorité chiffrée à une décision arbitraire.

Limites : asymptotique (mal calibré sous ~30 points), suppose des rendements
i.i.d. (l'autocorrélation gonfle le Sharpe et resserre à tort l'intervalle), et
ne corrige PAS la multiplicité des essais — c'est le rôle du DSR et du ledger.
"""

from __future__ import annotations

import math

Z_95 = 1.959963984540054      # quantile normal bilatéral à 5 %

# TOLÉRANCE RELATIVE, jamais `sd > 0`. L'écart-type d'une série constante ne vaut
# pas zéro en flottant mais ~1e-18 : `mu / sd` renvoyait alors 5e15 au lieu de 0
# (attrapé par les tests). Même piège que celui consigné pour `polyfit` dans
# CLAUDE.md — comparer à un seuil ABSOLU quand la dispersion est ~0 donne un
# résultat aberrant, pas une erreur visible.
_EPS_REL = 1e-12


def _moments(r: list[float]) -> tuple[float, float]:
    """Moyenne et écart-type d'échantillon (ddof=1)."""
    n = len(r)
    mu = sum(r) / n
    var = sum((x - mu) ** 2 for x in r) / (n - 1)
    return mu, math.sqrt(var)


def sharpe_periodique(r: list[float]) -> float:
    """Sharpe PAR PÉRIODE (non annualisé), sans taux sans risque."""
    if len(r) < 2:
        return 0.0
    mu, sd = _moments(r)
    return mu / sd if sd > _EPS_REL * max(1.0, abs(mu)) else 0.0


def _correlation(a: list[float], b: list[float]) -> float:
    mu_a, sd_a = _moments(a)
    mu_b, sd_b = _moments(b)
    if (sd_a <= _EPS_REL * max(1.0, abs(mu_a))
            or sd_b <= _EPS_REL * max(1.0, abs(mu_b))):
        return 0.0
    n = len(a)
    cov = sum((x - mu_a) * (y - mu_b)
              for x, y in zip(a, b, strict=True)) / (n - 1)
    return max(-1.0, min(1.0, cov / (sd_a * sd_b)))


def _phi(z: float) -> float:
    """Répartition normale standard (via erf, stdlib)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def comparer(base: list[float], variante: list[float],
             periodes_par_an: float = 12.0, min_points: int = 30) -> dict:
    """Compare deux séries de rendements APPARIÉES (mêmes dates, même longueur).

    Renvoie le ΔSharpe annualisé, son erreur-type, z, p, et un verdict à trois
    états : `meilleur` / `pire` / `indiscernable`. `indiscernable` n'est PAS
    « équivalent » : c'est « cet échantillon ne permet pas de trancher ».
    """
    n = min(len(base), len(variante))
    if n < min_points:
        return {"disponible": False, "n": n,
                "raison": f"{n} points < {min_points} — asymptotique non calibrée"}
    a, b = list(base[:n]), list(variante[:n])
    s_a, s_b = sharpe_periodique(a), sharpe_periodique(b)
    rho = _correlation(a, b)
    ech = math.sqrt(periodes_par_an)   # per-période -> annualisé (échelle commune)
    var = (2.0 * (1.0 - rho)
           + 0.5 * (s_a**2 + s_b**2 - 2.0 * rho**2 * s_a * s_b)) / n
    delta = s_b - s_a
    # VARIANCE DÉGÉNÉRÉE = les deux séries sont la MÊME (ρ = 1, Sharpe égaux) : la
    # variance de leur différence est nulle parce que la différence l'est. Ce
    # n'est pas un échec du test, c'est sa réponse — un levier qui ne change
    # aucun pas est indiscernable de la base. Le cas se produit vraiment : c'est
    # le « ⚪ INERTE » du labo, un garde-fou qui ne se déclenche jamais.
    if var <= _EPS_REL * max(1.0, s_a**2 + s_b**2):
        return {"disponible": True, "n": n, "degenere": True,
                "sharpe_base": round(s_a * ech, 4),
                "sharpe_variante": round(s_b * ech, 4),
                "delta": round(delta * ech, 4), "se": 0.0, "ic95": (0.0, 0.0),
                "correlation": round(rho, 4), "z": 0.0, "p": 1.0,
                "verdict": "indiscernable"}
    se = math.sqrt(var)
    z = delta / se
    p = 2.0 * (1.0 - _phi(abs(z)))
    verdict = ("indiscernable" if abs(z) < Z_95
               else ("meilleur" if z > 0 else "pire"))
    return {"disponible": True, "n": n, "degenere": False,
            "sharpe_base": round(s_a * ech, 4),
            "sharpe_variante": round(s_b * ech, 4),
            "delta": round(delta * ech, 4), "se": round(se * ech, 4),
            "ic95": (round((delta - Z_95 * se) * ech, 4),
                     round((delta + Z_95 * se) * ech, 4)),
            "correlation": round(rho, 4), "z": round(z, 3), "p": round(p, 4),
            "verdict": verdict}


def seuil_detectable(n: int, sharpe: float = 1.0, rho: float = 0.95,
                     periodes_par_an: float = 12.0) -> float:
    """Plus petit ΔSharpe annualisé détectable à 5 % — « ce labo voit-il +0,05 ? ».

    À lire AVANT de lancer : si le seuil détectable dépasse l'effet espéré,
    l'expérience ne peut pas conclure, et la lancer quand même produit du bruit
    qu'on lira comme un résultat.
    """
    var = (2.0 * (1.0 - rho)
           + 0.5 * (2 * sharpe**2 - 2.0 * rho**2 * sharpe**2)) / n
    return round(Z_95 * math.sqrt(var) * math.sqrt(periodes_par_an), 4)
