"""Caractéristiques du filtre ML swing : distance aux EMA, RSI multi-périodes,
moments glissants, compression de volatilité.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09), bloc 2. Le PIPELINE existe déjà et n'est pas
redupliqué : validation croisée purgée `ml/cpcv` (plus stricte qu'un TimeSeriesSplit,
qui laisse fuiter par les labels chevauchants), `ml/labeling`, `ml/promotion`,
`ml/governance`, IC de Spearman dans `backtest/ml_walkforward`. Ce module n'ajoute que
les quatre familles de features qui manquaient, et rien d'autre.

TOUT EST CAUSAL, PAR CONSTRUCTION ET PAR TEST. Chaque valeur à l'indice `i` n'utilise
que `barres[:i+1]`. C'est la propriété qui décide de tout le reste : une feature qui
regarde une barre en avant produit un modèle brillant en backtest et sans valeur en
production, et l'écart ne se voit qu'après avoir engagé du capital.

LE Z-SCORE EST GLISSANT, PAS PLEIN ÉCHANTILLON. Normaliser par les moments de TOUTE la
série est la fuite la plus fréquente des pipelines de features : la valeur de 2015 s'y
trouve normalisée par des statistiques de 2026. On normalise donc sur une fenêtre
passée, et le prix de ce choix est assumé — les premières barres n'ont aucune feature,
plutôt qu'une feature fausse.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

import math

STATUT = "SHADOW_UNCALIBRATED"

PERIODES_RSI = (7, 14, 21)
FENETRE_MOMENTS = 30
FENETRE_ZSCORE = 250

# Plancher RELATIF de dispersion. Sous ce seuil, l'écart-type observé n'est plus de
# l'information : c'est du bruit d'arrondi flottant, et le standardiser l'amplifie
# jusqu'à produire un skew de 0,02 sur une série STRICTEMENT géométrique — une valeur
# qui a l'air d'un signal. Comparer à zéro ne suffit pas ; il faut une tolérance
# relative (même leçon que sur les canaux de régression, cf. CLAUDE.md).
PLANCHER_DISPERSION = 1e-12


def _closes(barres) -> list[float]:
    return [float(b.close) for b in barres]


def ema(valeurs: list[float], periode: int) -> list[float | None]:
    """EMA causale : `None` tant que la période n'est pas remplie.

    Amorcée sur la moyenne simple des `periode` premières valeurs — l'amorcer sur la
    première valeur seule laisse une empreinte du point de départ pendant des dizaines
    de barres, ce qui rend la feature dépendante de la date de début de la série.
    """
    if periode <= 0 or len(valeurs) < periode:
        return [None] * len(valeurs)
    out: list[float | None] = [None] * (periode - 1)
    prec = sum(valeurs[:periode]) / periode
    out.append(prec)
    k = 2.0 / (periode + 1)
    for v in valeurs[periode:]:
        prec = v * k + prec * (1 - k)
        out.append(prec)
    return out


def _zscore_glissant(serie: list[float | None], fenetre: int) -> list[float | None]:
    """Z-score sur les `fenetre` valeurs PRÉCÉDENTES, barre courante incluse."""
    out: list[float | None] = []
    fen: list[float] = []
    for v in serie:
        if v is None:
            out.append(None)
            continue
        fen.append(float(v))
        if len(fen) > fenetre:
            fen.pop(0)
        if len(fen) < max(20, fenetre // 5):
            out.append(None)
            continue
        m = sum(fen) / len(fen)
        var = sum((x - m) ** 2 for x in fen) / (len(fen) - 1)
        sd = math.sqrt(var)
        assez = sd > PLANCHER_DISPERSION * max(1.0, abs(m))
        out.append(((float(v) - m) / sd) if assez else None)
    return out


def distance_aux_ema(barres, periodes=(50, 200),
                     fenetre: int = FENETRE_ZSCORE) -> dict[str, list[float | None]]:
    """Écart relatif prix/EMA, normalisé en z-score glissant.

    L'écart BRUT n'est pas comparable d'un titre à l'autre : 3 % au-dessus de l'EMA50
    est extrême sur une obligation et banal sur une biotech. Le z-score rend la feature
    comparable en coupe transversale, ce qui est la condition pour qu'un modèle unique
    serve tout l'univers.
    """
    c = _closes(barres)
    sortie: dict[str, list[float | None]] = {}
    for p in periodes:
        e = ema(c, p)
        brut: list[float | None] = [
            (c[i] / e[i] - 1.0) if (e[i] and e[i] > 0) else None for i in range(len(c))]
        sortie[f"dist_ema{p}_z"] = _zscore_glissant(brut, fenetre)
    return sortie


def rsi_multi(barres, periodes=PERIODES_RSI) -> dict[str, list[float | None]]:
    """RSI sur plusieurs périodes — même dynamique lue à plusieurs échelles.

    Ces trois séries sont FORTEMENT corrélées entre elles ; c'est attendu et ce n'est
    pas un défaut, mais un modèle linéaire y sera instable. Les arbres n'en souffrent
    pas — d'où le choix d'un XGBoost/forêt plutôt que d'une régression.
    """
    from packages.indicators.momentum import RSI
    return {f"rsi{p}": [None if (v != v) else float(v)      # NaN -> None, explicitement
                        for v in RSI(period=p).compute(barres)]
            for p in periodes}


def moments_glissants(barres, fenetre: int = FENETRE_MOMENTS) -> dict[str, list]:
    """Asymétrie et aplatissement des rendements LOG sur `fenetre` barres passées.

    Rendements log et non arithmétiques : le skew d'une série arithmétique est
    mécaniquement positif (une perte est bornée à -100 %, un gain ne l'est pas), ce qui
    ferait lire de l'asymétrie là où il n'y a qu'un changement d'unité.
    """
    c = _closes(barres)
    lr = [math.log(c[i] / c[i - 1]) if (c[i] > 0 and c[i - 1] > 0) else 0.0
          for i in range(1, len(c))]
    skew: list[float | None] = [None]
    kurt: list[float | None] = [None]
    for i in range(len(lr)):
        fen = lr[max(0, i - fenetre + 1):i + 1]
        if len(fen) < fenetre:
            skew.append(None)
            kurt.append(None)
            continue
        m = sum(fen) / len(fen)
        var = sum((x - m) ** 2 for x in fen) / len(fen)
        sd = math.sqrt(var)
        if sd <= PLANCHER_DISPERSION * max(1.0, abs(m)):
            skew.append(None)          # dispersion nulle : pas d'asymétrie MESURABLE,
            kurt.append(None)          # surtout pas une asymétrie de zéro
            continue
        skew.append(sum(((x - m) / sd) ** 3 for x in fen) / len(fen))
        kurt.append(sum(((x - m) / sd) ** 4 for x in fen) / len(fen) - 3.0)
    return {"skew_log30": skew, "kurtosis_log30": kurt}


def compression_volatilite(barres, periode_bb: int = 20,
                           periode_atr: int = 14) -> dict[str, list[float | None]]:
    """Largeur de Bollinger rapportée à l'ATR — la « squeeze » qui précède l'expansion.

    LES DEUX TERMES SONT RAMENÉS À LA MÊME UNITÉ avant d'être divisés. `BollingerWidth`
    rend déjà une largeur RELATIVE (fraction du prix) ; l'ATR est en unités de prix. Les
    diviser tels quels donnerait un ratio dépendant du niveau du titre — comparable pour
    aucun couple d'actifs. On divise donc par l'ATR RELATIF (ATR/clôture).
    """
    from packages.indicators.volatility import ATR, BollingerWidth
    bb = BollingerWidth(period=periode_bb).compute(barres)
    at = ATR(period=periode_atr).compute(barres)
    c = _closes(barres)
    out: list[float | None] = []
    for i in range(len(c)):
        b, a = bb[i], at[i]
        if b != b or a != a or not c[i] or a <= 0:   # NaN ou prix nul
            out.append(None)
            continue
        atr_rel = a / c[i]
        out.append((b / atr_rel) if atr_rel > 0 else None)
    return {"squeeze_bb_atr": out}


def construire(barres, fenetre_zscore: int = FENETRE_ZSCORE) -> dict[str, list]:
    """Toutes les features en un appel, alignées sur `barres` (même longueur).

    Même longueur que l'entrée, `None` là où la feature n'existe pas encore : c'est ce
    qui permet à l'appelant de joindre par INDICE sans se demander de combien chaque
    série a été décalée. Les décalages implicites sont la façon la plus discrète
    d'introduire un look-ahead dans un jeu de features.
    """
    f: dict[str, list] = {}
    f.update(distance_aux_ema(barres, fenetre=fenetre_zscore))
    f.update(rsi_multi(barres))
    f.update(moments_glissants(barres))
    f.update(compression_volatilite(barres))
    n = len(barres)
    assert all(len(v) == n for v in f.values()), "features désalignées avec les barres"
    return {"statut": STATUT, **f}
