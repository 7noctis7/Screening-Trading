"""Cœur MULTI-ACTIFS : on change la CORRÉLATION, pas la concentration.

D'OÙ VIENT CE MODULE. Le compte réel affiche N effectif = 1,5 (HHI 0,665, top-3 = 87 %)
: le portefeuille se comporte comme une position et demie. Concentrer davantage le cœur
(top-7 au lieu du top-10) n'y change rien — la mesure du 02/09 le dit déjà : preset 0,82
→ 50/50 QQQ 0,99 → QQQ pur 0,98 → momentum sectoriel 0,86, pendant que le maxDD passe de
-19,5 % à -73,6 %. La concentration achète du drawdown, pas du Sharpe.

Le seul levier resté ouvert est la corrélation. Le Sharpe d'une combinaison de N flux de
Sharpe s et de corrélation moyenne rho vaut s·sqrt(N/(1+(N-1)·rho)). À rho = 0,9 (des
actions entre elles), passer de 1 à 3 lignes ne rapporte presque rien ; à rho ≈ 0, la
même opération multiplie le Sharpe par sqrt(3). Les obligations longues et l'or ne sont
pas ici pour leur rendement propre — TLT et GLD ont un Sharpe médiocre sur onze ans —
mais parce qu'ils ne baissent pas en même temps que le Nasdaq.

CE QUI EST DÉCLARÉ D'AVANCE (avant toute mesure, comme pour le suiveur le 02/09) :
  · les paniers testés — trois pondérations fixes + une inverse-vol, soit QUATRE essais,
    comptés dans la déflation du DSR ;
  · la taille du cœur reste 50 %, identique à la production, pour que la SEULE chose qui
    change soit la COMPOSITION du cœur ;
  · les poids ne sont jamais ajustés après coup : « 50/30/20 » est une convention (un
    60/40
    incliné croissance, plus une poche or), pas un optimum.

CE QUE CE MODULE NE FAIT PAS. Il ne choisit rien. Il produit une courbe ; c'est
`scripts/coeur_multi_actifs_lab.py` qui la confronte à la production sur les MÊMES
dates, avec le test apparié de Jobson-Korkie/Memmel, et la règle d'acceptation écrite
avant le run.

DEUX PIÈGES, TOUS DEUX DÉJÀ PAYÉS DANS CE DÉPÔT :
  · ALIGNER PAR DATE, JAMAIS PAR POSITION. Empiler trois séries par index et supposer
    qu'elles partagent un calendrier est le bug qu'on a corrigé trois fois ici. Tout
    passe par `serie_sur_axe`, qui indexe sur un axe de dates fourni.
  · REPORT AVANT UNIQUEMENT. Un trou se comble avec la DERNIÈRE clôture connue, jamais
    avec la suivante : remplir en arrière, c'est lire le futur.
"""

from __future__ import annotations

import bisect

SYMBOLES: tuple[str, ...] = ("QQQ", "TLT", "GLD")

# Paniers DÉCLARÉS D'AVANCE. Le nombre d'entrées de ce dictionnaire EST le nombre
# d'essais de ce banc : l'ajouter après avoir vu les résultats fausserait la déflation
# du DSR.
PANIERS: dict[str, tuple[tuple[str, float], ...]] = {
    "60/25/15": (("QQQ", 0.60), ("TLT", 0.25), ("GLD", 0.15)),
    "50/30/20": (("QQQ", 0.50), ("TLT", 0.30), ("GLD", 0.20)),
    "40/35/25": (("QQQ", 0.40), ("TLT", 0.35), ("GLD", 0.25)),
}

REBAL = 21          # jours de bourse entre deux rééquilibrages (~1 mois)
COUT_BPS = 5.0      # coût aller simple, appliqué au NOTIONNEL échangé à chaque rééq.
FENETRE_VOL = 63    # fenêtre de l'inverse-vol (~1 trimestre), sur données PASSÉES


def serie_sur_axe(barres, axe: list[str]) -> list[float | None]:
    """Clôtures reportées sur l'AXE de dates fourni. `None` avant la 1re observation.

    Report AVANT seulement : à la date `d`, la valeur est la dernière clôture observée à
    une date <= `d`. Avant la première barre du titre, la valeur est `None` — et non le
    premier cours connu, qui ferait apparaître le titre AVANT son existence.
    """
    jours, closes = [], []
    for b in (barres or []):
        ts = getattr(b, "ts", None)
        c = getattr(b, "close", None)
        if ts is None or c is None:
            continue
        d = getattr(ts, "date", None)
        jours.append(d().isoformat() if callable(d) else str(ts)[:10])
        closes.append(float(c))
    if not jours:
        return [None] * len(axe)
    ordre = sorted(range(len(jours)), key=jours.__getitem__)
    jours = [jours[i] for i in ordre]
    closes = [closes[i] for i in ordre]
    out: list[float | None] = []
    for d in axe:
        k = bisect.bisect_right(jours, d) - 1
        out.append(closes[k] if k >= 0 else None)
    return out


def depart_commun(series: dict[str, list[float | None]]) -> int:
    """Premier index où TOUTES les séries existent. -1 si jamais.

    Le cœur ne commence pas avant que sa dernière composante existe : le démarrer plus
    tôt reviendrait à mesurer un panier différent de celui qu'on prétend mesurer.
    """
    if not series:
        return -1
    n = min(len(v) for v in series.values())
    for i in range(n):
        if all(v[i] is not None and v[i] > 0 for v in series.values()):
            return i
    return -1


def _poids_inverse_vol(rends: dict[str, list[float]], t: int,
                       fenetre: int = FENETRE_VOL) -> dict[str, float] | None:
    """Poids ∝ 1/σ sur les `fenetre` derniers rendements CONNUS À t (indices < t).

    Ce n'est pas un réglage : aucune valeur n'est choisie en regardant le résultat.
    C'est une règle mécanique, la seule des quatre variantes qui ne fixe pas ses poids à
    la main.
    """
    debut = t - fenetre
    if debut < 0:
        return None
    inv: dict[str, float] = {}
    for s, r in rends.items():
        fen = r[debut:t]
        if len(fen) < fenetre // 2:
            return None
        m = sum(fen) / len(fen)
        var = sum((x - m) ** 2 for x in fen) / (len(fen) - 1)
        sd = var ** 0.5
        if sd <= 0:
            return None
        inv[s] = 1.0 / sd
    total = sum(inv.values())
    return {s: v / total for s, v in inv.items()} if total > 0 else None


def _derive(poids: dict[str, float], rend: dict[str, float]) -> dict[str, float]:
    """Poids après une séance : ils DÉRIVENT avec les rendements, ils ne restent
    pas fixes."""
    val = {s: w * (1.0 + rend.get(s, 0.0)) for s, w in poids.items()}
    total = sum(val.values())
    return {s: v / total for s, v in val.items()} if total > 0 else poids


def coeur_equity(series: dict[str, list[float | None]], poids: dict[str, float] | None,
                 rebal: int = REBAL, cout_bps: float = COUT_BPS,
                 base: float = 100.0, inverse_vol: bool = False,
                 fenetre_vol: int = FENETRE_VOL) -> dict:
    """Courbe du cœur multi-actifs sur l'axe des séries fournies (toutes déjà alignées).

    Renvoie {available, equity, depart, motif}. `equity` a la longueur de l'axe : la
    partie antérieure au démarrage commun vaut `None`, pour que l'appelant sache où le
    cœur commence RÉELLEMENT au lieu de le deviner.

    LE COÛT EST CHARGÉ, et il ne l'est nulle part ailleurs dans ce dépôt : le cœur QQQ
    est un buy-and-hold qui ne paie aucun rééquilibrage. La comparaison est donc
    DÉFAVORABLE au nouveau venu — c'est le sens d'erreur qu'on accepte.
    """
    if not series:
        return {"available": False, "motif": "aucune série"}
    i0 = depart_commun(series)
    n = min(len(v) for v in series.values())
    if i0 < 0 or n - i0 < 60:
        return {"available": False, "motif": "historique commun trop court"}
    syms = sorted(series)
    rends = {s: [0.0] * n for s in syms}
    for s in syms:
        v = series[s]
        for i in range(i0 + 1, n):
            prev, cur = v[i - 1], v[i]
            rends[s][i] = (cur / prev - 1.0) if (prev and cur and prev > 0) else 0.0
    if inverse_vol:
        cible = None
    else:
        total = sum((poids or {}).values())
        if not poids or total <= 0:
            return {"available": False, "motif": "poids vides"}
        cible = {s: poids.get(s, 0.0) / total for s in syms}
    # L'inverse-vol a besoin de sa fenêtre AVANT de pouvoir pondérer. On décale donc son
    # départ plutôt que de la laisser en cash : une courbe plate au début se lirait
    # comme une performance (nulle) alors qu'il n'y a rien à mesurer.
    i1 = i0 + (fenetre_vol if inverse_vol else 0)
    if n - i1 < 60:
        return {"available": False, "motif": "historique commun trop court"}
    eq: list[float | None] = [None] * i1 + [base]
    w: dict[str, float] = {}
    frais = cout_bps / 1e4
    for t in range(i1 + 1, n):
        cout = 0.0
        if ((t - 1 - i1) % rebal == 0) or not w:
            nouveau = (_poids_inverse_vol(rends, t, fenetre_vol) if inverse_vol
                       else cible)
            if not nouveau:
                return {"available": False, "motif": "pondération indisponible"}
            cout = frais * sum(abs(nouveau.get(s, 0.0) - w.get(s, 0.0)) for s in syms)
            w = dict(nouveau)
        r = sum(w[s] * rends[s][t] for s in syms) - cout
        eq.append(eq[-1] * (1.0 + r))
        w = _derive(w, {s: rends[s][t] for s in syms})
    return {"available": True, "equity": eq, "depart": i1, "motif": ""}


def correlations(series: dict[str, list[float | None]],
                 depart: int) -> dict[str, float]:
    """Corrélations DEUX À DEUX des rendements quotidiens, à partir du départ commun.

    C'est la justification de la construction, et elle se lit AVANT le Sharpe : si TLT
    et GLD sont corrélés à 0,8 au QQQ, le panier n'est qu'un QQQ plus cher.
    """
    syms = sorted(series)
    r: dict[str, list[float]] = {}
    n = min(len(v) for v in series.values()) if series else 0
    for s in syms:
        v = series[s]
        r[s] = [(v[i] / v[i - 1] - 1.0) if (v[i - 1] and v[i] and v[i - 1] > 0) else 0.0
                for i in range(max(depart + 1, 1), n)]
    out: dict[str, float] = {}
    for i, a in enumerate(syms):
        for b in syms[i + 1:]:
            out[f"{a}/{b}"] = _rho(r[a], r[b])
    return out


def _rho(a: list[float], b: list[float]) -> float:
    """Corrélation de deux séries DÉJÀ appariées. Des longueurs différentes signalent un
    défaut d'alignement en amont : on refuse plutôt que de recadrer sur `[-m:]` — ce
    recadrage silencieux est exactement ce qui a produit trois bugs d'empilement ici."""
    m = len(a)
    if m < 30 or len(b) != m:
        return 0.0
    ma, mb = sum(a) / m, sum(b) / m
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(m))
    return cov / (va ** 0.5 * vb ** 0.5)
