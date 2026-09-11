"""Le régime « haute volatilité » de la spec, MESURÉ avant d'être câblé.

LA RÈGLE À L'ÉTUDE. « ATR > 200 % de sa moyenne 30 périodes ⇒ régime haute volatilité,
on bascule sur un modèle dédié. » Trois choses s'y cachent, et aucune n'est acquise :

1. **Le seuil.** 200 % est un nombre rond, pas une mesure. Sur ces données il peut ne
   jamais mordre (règle inerte, pire qu'absente : elle se lit comme « géré ») ou mordre
   sans arrêt. On compte donc les barres de chaque côté avant toute chose.
2. **La séparation.** Deux régimes ne justifient deux modèles que si la distribution des
   rendements FUTURS y diffère. Sinon on a coupé l'échantillon en deux pour rien.
3. **Le budget d'échantillon.** `_ml_section` refuse d'entraîner sous 500 lignes. Couper
   par régime divise l'échantillon ; si un côté passe sous le plancher, le modèle dédié
   n'est pas entraînable et la question est close — sans écrire une ligne de bascule.

AUCUN REGARD EN AVANT. Le classement d'une barre n'utilise que l'ATR et sa moyenne
arrêtés à cette barre ; le rendement mesuré est POSTÉRIEUR. La fenêtre de moyenne
consomme donc les 30 + 14 premières barres, et l'horizon en ampute autant à la fin.

Ce module ne fait aucune E/S : il reçoit des barres, il rend des comptes. Le banc
`scripts/regime_atr_lab.py` l'alimente avec la base RÉELLE.
"""

from __future__ import annotations

import math

FENETRE_ATR = 14
FENETRE_MOYENNE = 30
SEUIL_SPEC = 2.0          # « 200 % de la moyenne » — le nombre de la spec, à éprouver
HORIZON = 5               # jours ouvrés
PLANCHER_ENTRAINEMENT = 500   # `snapshot.py` : `if len(X) < 500: return indisponible`
MIN_OBS_VERDICT = 30      # sous ce seuil, une moyenne de rendements ne dit rien


def true_range(hauts, bas, clotures) -> list[float | None]:
    """TR de Wilder. La première barre n'en a pas : pas de clôture précédente."""
    tr: list[float | None] = [None]
    for i in range(1, len(clotures)):
        pc = clotures[i - 1]
        tr.append(max(hauts[i] - bas[i], abs(hauts[i] - pc), abs(bas[i] - pc)))
    return tr


def _moyenne_mobile(valeurs, n: int) -> list[float | None]:
    """Moyenne arrêtée à chaque barre. `None` tant que la fenêtre n'est pas pleine."""
    out: list[float | None] = []
    fenetre: list[float] = []
    for v in valeurs:
        if v is None:
            fenetre.clear()      # un trou casse la fenêtre, on ne moyenne pas à travers
            out.append(None)
            continue
        fenetre.append(float(v))
        if len(fenetre) > n:
            fenetre.pop(0)
        out.append(sum(fenetre) / n if len(fenetre) == n else None)
    return out


def ratios(hauts, bas, clotures, *, fenetre_atr: int = FENETRE_ATR,
           fenetre_moyenne: int = FENETRE_MOYENNE) -> list[float | None]:
    """ATR / moyenne(ATR) barre par barre — la quantité que la spec compare à 2,0."""
    atr = _moyenne_mobile(true_range(hauts, bas, clotures), fenetre_atr)
    moy = _moyenne_mobile(atr, fenetre_moyenne)
    return [None if (a is None or m is None or m <= 0) else a / m
            for a, m in zip(atr, moy, strict=True)]


def classer(hauts, bas, clotures, *, dates=None, seuil: float = SEUIL_SPEC,
            horizon: int = HORIZON, chevauchement: bool = False, **kw) -> dict:
    """Range les rendements FUTURS de chaque barre dans son régime.

    Une barre n'est classée que si son ratio est connu ET que l'horizon tient encore
    dans la série — sinon on inventerait un rendement qu'on n'a pas observé.

    PAS DE CHEVAUCHEMENT PAR DÉFAUT, et c'est la décision qui compte ici. À horizon 5,
    prendre chaque barre donne cinq fois plus d'observations — mais deux barres voisines
    partagent quatre de leurs cinq jours. Ces observations ne sont pas indépendantes ;
    les compter comme telles gonfle n, rétrécit l'erreur-type et fabrique un t de Welch
    qui « prouve » une séparation entre régimes qu'on n'a pas mesurée. On avance donc
    d'`horizon` en `horizon`. `chevauchement=True` reste disponible pour comparer les
    deux lectures — l'écart entre elles mesure exactement l'illusion évitée.
    """
    r = ratios(hauts, bas, clotures, **kw)
    haute: list[float] = []
    basse: list[float] = []
    haute_d: list[tuple[str, float]] = []
    basse_d: list[tuple[str, float]] = []
    pas = 1 if chevauchement else max(1, horizon)
    for i in range(0, len(r), pas):
        ratio = r[i]
        j = i + horizon
        if ratio is None or j >= len(clotures) or clotures[i] <= 0:
            continue
        rendement = clotures[j] / clotures[i] - 1.0
        (haute if ratio > seuil else basse).append(rendement)
        if dates is not None and i < len(dates) and dates[i] is not None:
            (haute_d if ratio > seuil else basse_d).append((jour(dates[i]), rendement))
    connus = [x for x in r if x is not None]
    return {"haute": haute, "basse": basse, "ratios": connus,
            "haute_datees": haute_d, "basse_datees": basse_d,
            "ratio_median": _mediane(connus), "ratio_max": max(connus, default=None)}


def jour(ts) -> str:
    """Un horodatage, quelle que soit sa forme, réduit à sa journée.

    Les barres arrivent tantôt en `datetime`, tantôt en chaîne ISO selon la source.
    Le regroupement par date ne tolère pas deux conventions : deux écritures du même
    jour formeraient deux grappes, et le nombre de grappes est précisément ce qui
    décide de la force du résultat.
    """
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d")
    return str(ts)[:10]


def moyennes_par_date(observations: list[tuple[str, float]]) -> list[float]:
    """Une observation par JOUR de marché, et non par couple (symbole, jour).

    LA CORRECTION QUI DÉCIDE DE TOUT ICI. Un pic d'ATR n'est pas un accident propre à
    un titre : c'est un événement de marché que 800 symboles traversent le même jour.
    Les compter comme 800 tirages indépendants divise l'erreur-type par ~28 et fabrique
    un t qui n'a rien mesuré. On moyenne donc à l'intérieur de chaque journée, puis on
    compare des journées — n devient le nombre d'épisodes réellement observés, ce qui
    est le nombre de fois où le marché a répondu à la question.

    Cela ne corrige PAS tout : deux journées consécutives d'une même crise restent
    corrélées. C'est une borne haute plus serrée, pas une preuve.
    """
    par_jour: dict[str, list[float]] = {}
    for d, x in observations:
        par_jour.setdefault(d, []).append(x)
    return [sum(v) / len(v) for _, v in sorted(par_jour.items())]


def _mediane(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def _moyenne_ecart(xs: list[float]) -> tuple[float | None, float | None]:
    n = len(xs)
    if n < 2:
        return (xs[0] if n else None), None
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    return mu, math.sqrt(var)


def welch(a: list[float], b: list[float]) -> dict:
    """Écart de moyenne entre deux échantillons de tailles et de variances inégales.

    Welch, pas Student : les deux régimes n'ont aucune raison de partager la variance —
    c'est même précisément ce qui les distingue. On rend le t et les degrés de liberté,
    pas une p-valeur : le lecteur doit voir sur quoi le chiffre repose.
    """
    ma, sa = _moyenne_ecart(a)
    mb, sb = _moyenne_ecart(b)
    if sa is None or sb is None or len(a) < 2 or len(b) < 2:
        return {"disponible": False, "motif": "moins de deux observations d'un côté"}
    va, vb = sa ** 2 / len(a), sb ** 2 / len(b)
    if va + vb <= 0:
        return {"disponible": False, "motif": "variance nulle des deux côtés"}
    t = (ma - mb) / math.sqrt(va + vb)
    ddl = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return {"disponible": True, "t": round(t, 3), "ddl": round(ddl, 1),
            "ecart_moyen": round(ma - mb, 6)}


def verdict(haute: list[float], basse: list[float], *,
            seuil: float = SEUIL_SPEC, haute_datees=None, basse_datees=None) -> dict:
    """Ce que la mesure autorise à conclure — y compris « rien ».

    Deux garde-fous bloquent AVANT le test statistique : un régime sous
    `MIN_OBS_VERDICT` ne porte aucune moyenne lisible, et un régime sous
    `PLANCHER_ENTRAINEMENT` ne peut pas porter de modèle dédié, quel que soit le t.

    QUAND LES DATES SONT FOURNIES, C'EST LE t GROUPÉ QUI DÉCIDE. Le t brut compte
    chaque couple (symbole, jour) comme un tirage ; or un pic d'ATR est un événement
    de marché que tout l'univers traverse ensemble. Le t groupé compare des JOURNÉES,
    donc des épisodes. Les deux sont rendus — l'écart entre eux est la mesure de ce
    qu'on aurait cru à tort — mais le statut suit le groupé, jamais le brut.
    """
    n_h, n_b = len(haute), len(basse)
    mh, _ = _moyenne_ecart(haute)
    mb, _ = _moyenne_ecart(basse)
    base = {"seuil": seuil, "n_haute": n_h, "n_basse": n_b,
            "part_haute": round(n_h / (n_h + n_b), 4) if (n_h + n_b) else None,
            "rendement_moyen_haute": round(mh, 6) if mh is not None else None,
            "rendement_moyen_basse": round(mb, 6) if mb is not None else None,
            "entrainable_haute": n_h >= PLANCHER_ENTRAINEMENT,
            "entrainable_basse": n_b >= PLANCHER_ENTRAINEMENT}
    if n_h == 0:
        return {**base, "statut": "REGLE_INERTE",
                "message": f"aucune barre au-dessus de {seuil:.2f} — la règle ne "
                           "mordrait jamais sur ces données"}
    if n_h < MIN_OBS_VERDICT or n_b < MIN_OBS_VERDICT:
        return {**base, "statut": "UNCALIBRATED",
                "message": f"{min(n_h, n_b)} observations du côté le plus mince "
                           f"(< {MIN_OBS_VERDICT}) — l'écart n'est pas lisible"}
    w = welch(haute, basse)
    base["welch"] = w
    if not base["entrainable_haute"]:
        return {**base, "statut": "NON_ENTRAINABLE",
                "message": f"{n_h} lignes en haute volatilité < plancher "
                           f"{PLANCHER_ENTRAINEMENT} de `_ml_section` — un modèle "
                           "dédié à ce régime ne peut pas être entraîné"}
    if haute_datees is None or basse_datees is None:
        return {**base, "statut": "MESURE_NON_GROUPEE",
                "message": f"t de Welch {w.get('t')} sur {w.get('ddl')} ddl, SANS "
                           "regroupement par date — borne haute, pas une mesure"}

    jh, jb = moyennes_par_date(haute_datees), moyennes_par_date(basse_datees)
    wg = welch(jh, jb)
    base.update({"n_jours_haute": len(jh), "n_jours_basse": len(jb),
                 "welch_groupe": wg})
    if len(jh) < MIN_OBS_VERDICT:
        return {**base, "statut": "UNCALIBRATED",
                "message": f"{len(jh)} JOURNÉES de haute volatilité seulement "
                           f"(< {MIN_OBS_VERDICT}) — les {n_h} observations brutes "
                           "sont ces mêmes journées vues par des centaines de "
                           "symboles, pas autant d'épisodes distincts"}
    if not wg.get("disponible"):
        return {**base, "statut": "UNCALIBRATED",
                "message": f"t groupé indisponible : {wg.get('motif')}"}
    return {**base, "statut": "MESURE",
            "message": f"t groupé {wg['t']} sur {wg['ddl']} ddl "
                       f"({len(jh)} journées contre {len(jb)}) — le t brut "
                       f"{w.get('t')} comptait {n_h} lignes comme indépendantes. "
                       "À confronter au gate de certification avant toute bascule"}
