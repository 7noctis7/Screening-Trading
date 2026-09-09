"""Les briques dont un signal est fait — fenêtres glissantes et coupe transversale.

POURQUOI CE FICHIER

La première grammaire du générateur produisait 75 candidats du type `identite(open, 0)`
ou `log(volume, 5)` : le prix brut, le volume brut. Aucun ne peut prédire quoi que ce
soit, parce qu'aucun ne dit rien de RELATIF — ni au passé de l'actif, ni aux autres
actifs. Explorer cet espace-là revenait à tirer 75 fois à pile ou face en croyant
chercher.

Les jeux de facteurs publiés (Alpha158 de Qlib, MIT) montrent où vivent les vrais
candidats : dans des expressions à DEUX ÉTAGES.
  · un étage TEMPOREL — l'actif comparé à son propre passé sur une fenêtre ;
  · un étage TRANSVERSAL — l'actif comparé aux autres, à la même date.
Un momentum brut n'est pas comparable entre une action calme et une crypto ; son RANG
dans la coupe du jour l'est. C'est cette composition qui fait le signal, pas l'un des
deux étages seul.

LA RÈGLE QUI NE SE NÉGOCIE PAS
Chaque opérateur temporel à l'instant `t` ne lit QUE les lignes `t-w+1 … t`. Jamais
`t+1`. Un décalage d'une seule ligne dans le mauvais sens fabrique un signal
spectaculaire et parfaitement faux — et rien dans les chiffres ne le signale, puisqu'ils
deviennent justement très beaux. Un test dédié le vérifie sur chaque opérateur, en
modifiant le futur et en exigeant que le passé ne bouge pas.

Les premières lignes valent `NaN` tant que la fenêtre n'est pas pleine. On ne complète
jamais : une valeur inventée sur les 20 premiers jours contamine toute l'étude.
"""

from __future__ import annotations

import numpy as np

__all__ = ["OPERATEURS_TEMPORELS", "OPERATEURS_TRANSVERSAUX", "FENETRES"]

FENETRES = (5, 21, 63, 126)


def _vide_comme(x: np.ndarray) -> np.ndarray:
    return np.full_like(np.asarray(x, float), np.nan)


def _fenetres_glissantes(x: np.ndarray, w: int) -> np.ndarray:
    """Vue (T-w+1, N, w) des fenêtres se terminant à chaque date.

    `sliding_window_view` ne copie rien et interdit structurellement de regarder
    au-delà de la date courante : la fenêtre qui finit en `t` s'arrête en `t`.
    """
    return np.lib.stride_tricks.sliding_window_view(x, w, axis=0)


# Nombre d'actifs traités d'un bloc. La vue glissante d'un panneau (T × N) sur une
# fenêtre w pèse (T−w+1) × N × w valeurs : sur 1499 dates, 774 actifs et 126 jours, cela
# fait 1,07 Go — et les réductions qui ignorent les NaN y ajoutent leur masque. Le
# processus a été TUÉ par le système au premier lancement réel (VPS, 08/09), après avoir
# passé les trois étapes précédentes. Découper borne le pic à ~100 Mo quel que soit le
# nombre d'actifs, pour un coût de calcul identique : c'est la même arithmétique, faite
# en plusieurs fois.
BLOC_ACTIFS = 64


def _applique(x: np.ndarray, w: int, fn) -> np.ndarray:
    """Applique `fn` sur chaque fenêtre pleine, NaN avant. Mémoire bornée."""
    x = np.asarray(x, float)
    if w < 2 or x.shape[0] < w:
        return _vide_comme(x)
    out = _vide_comme(x)
    for debut in range(0, x.shape[1], BLOC_ACTIFS):
        bloc = x[:, debut:debut + BLOC_ACTIFS]
        out[w - 1:, debut:debut + BLOC_ACTIFS] = fn(_fenetres_glissantes(bloc, w))
    return out


def momentum(panneau: dict, w: int) -> np.ndarray:
    """Rendement sur la fenêtre : où en est le cours par rapport à il y a `w` jours."""
    c = np.asarray(panneau["close"], float)
    out = _vide_comme(c)
    if c.shape[0] > w:
        avant = c[:-w]
        out[w:] = np.where(avant > 0, c[w:] / np.where(avant == 0, np.nan, avant) - 1.0,
                           np.nan)
    return out


def volatilite(panneau: dict, w: int) -> np.ndarray:
    """Agitation récente : écart-type des rendements quotidiens sur la fenêtre."""
    c = np.asarray(panneau["close"], float)
    r = np.full_like(c, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        r[1:] = np.diff(c, axis=0) / np.where(c[:-1] == 0, np.nan, c[:-1])
    return _applique(r, w, lambda f: np.nanstd(f, axis=-1))


def ecart_a_la_moyenne(panneau: dict, w: int) -> np.ndarray:
    """Retour à la moyenne : de combien le cours s'écarte de sa moyenne mobile."""
    c = np.asarray(panneau["close"], float)
    moy = _applique(c, w, lambda f: np.nanmean(f, axis=-1))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(moy > 0, c / np.where(moy == 0, np.nan, moy) - 1.0, np.nan)


def position_dans_la_bande(panneau: dict, w: int) -> np.ndarray:
    """Où se situe le cours entre son plus bas et son plus haut de la fenêtre.

    0 = au plancher, 1 = au sommet. Sans unité, donc comparable entre une action
    et une crypto — contrairement à un écart en euros ou en pourcents.
    """
    c = np.asarray(panneau["close"], float)
    bas = _applique(np.asarray(panneau["low"], float), w,
                    lambda f: np.nanmin(f, axis=-1))
    haut = _applique(np.asarray(panneau["high"], float), w,
                     lambda f: np.nanmax(f, axis=-1))
    etendue = haut - bas
    with np.errstate(divide="ignore", invalid="ignore"):
        sur = np.where(etendue == 0, np.nan, etendue)
        return np.where(etendue > 0, (c - bas) / sur, np.nan)


def pente(panneau: dict, w: int) -> np.ndarray:
    """Pente de la tendance sur la fenêtre, rapportée au niveau du cours.

    Rapportée au niveau, sinon un titre à 400 $ aurait mécaniquement une pente cent fois
    plus forte qu'un titre à 4 $ pour la même tendance en pourcentage.
    """
    c = np.asarray(panneau["close"], float)

    def _pente(f):
        t = np.arange(f.shape[-1], dtype=float)
        t = t - t.mean()
        num = np.nansum(f * t, axis=-1)
        return num / float(np.sum(t * t))

    brut = _applique(c, w, _pente)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(c > 0, brut / np.where(c == 0, np.nan, c), np.nan)


def ratio_de_volume(panneau: dict, w: int) -> np.ndarray:
    """Volume du jour rapporté à son habitude : l'attention se porte-t-elle ici ?"""
    v = np.asarray(panneau["volume"], float)
    moy = _applique(v, w, lambda f: np.nanmean(f, axis=-1))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(moy > 0, v / np.where(moy == 0, np.nan, moy), np.nan)


OPERATEURS_TEMPORELS = {
    "momentum": momentum,
    "volatilite": volatilite,
    "ecart_a_la_moyenne": ecart_a_la_moyenne,
    "position_dans_la_bande": position_dans_la_bande,
    "pente": pente,
    "ratio_de_volume": ratio_de_volume,
}


def _par_date(x: np.ndarray, fn) -> np.ndarray:
    """Applique `fn` à CHAQUE date séparément — jamais sur la colonne entière.

    Mélanger les dates ferait entrer le futur dans le calcul du présent : un z-score
    calculé sur toute l'histoire d'un actif utilise des moyennes qu'on ne connaîtra
    que plus tard.
    """
    x = np.asarray(x, float)
    out = np.full_like(x, np.nan)
    for t in range(x.shape[0]):
        ligne = x[t]
        valides = np.isfinite(ligne)
        if valides.sum() >= 3:
            out[t, valides] = fn(ligne[valides])
    return out


def _rang_normalise(v: np.ndarray) -> np.ndarray:
    ordre = np.argsort(np.argsort(v, kind="stable"), kind="stable").astype(float)
    return ordre / max(1.0, ordre.size - 1.0)


OPERATEURS_TRANSVERSAUX = {
    "brut": lambda x: np.asarray(x, float),
    "rang": lambda x: _par_date(x, _rang_normalise),
    "zscore": lambda x: _par_date(x, lambda v: (v - v.mean()) / (v.std() + 1e-12)),
    "inverse": lambda x: -np.asarray(x, float),
}
