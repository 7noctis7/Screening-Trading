"""Momentum RÉSIDUEL — le momentum d'un titre une fois le marché retiré (plugin facteur).

THÈSE (Blitz, Huij & Martens 2011 ; Gutierrez & Prinsky 2007). Le momentum de prix
mélange deux choses : ce que le titre a fait de SON PROPRE fait, et ce qu'il a encaissé
parce qu'il est exposé au marché. La seconde part n'est pas une information sur le titre :
après une hausse du marché, le haut du classement se remplit de titres à bêta élevé, et le
portefeuille devient un pari de marché déguisé — c'est ce qui casse le momentum aux
retournements. Le momentum résiduel classe sur la première part seulement.

POURQUOI CE CANDIDAT, ET PAS UN AUTRE (10/11). Le seul effet mesuré du dépôt est le
classement momentum 12-1 (RankIC à 1 séance +0,019, t = 4,09, VPS 07/10). Le modèle ML,
lui, ne prédit rien hors échantillon (IC +0,0007), et quatre représentations de label
ont été écartées (ADR-0219). On raffine donc le signal qui existe plutôt que d'en chercher
un autre : aucun paramètre n'est ajusté, tous viennent de la publication.

DÉFINITION. Sur les `estimation` dernières séances (≤ jour de décision) :
    r_titre = α + β · r_marché + ε          (moindres carrés, avec constante)
    score = Σ ε sur la fenêtre de formation  /  (σ_ε · √n)
où la formation est [t − formation, t − saut) : 12 mois en sautant le dernier, comme le
momentum classique. Le marché est la moyenne équipondérée des titres cotés ce jour-là.

PIÈGE VERROUILLÉ. Avec une constante, les résidus somment à ZÉRO sur la fenêtre
d'estimation. Si elle égale la fenêtre de formation, le score vaut exactement l'opposé
des `saut` derniers résidus : un retournement à un mois, vendu sous le nom de momentum.
`estimation` doit donc couvrir au moins deux fois `formation` (la publication : 36 mois
pour 12) ; sinon le calcul refuse.

STATUT : CANDIDATE_UNCALIBRATED. Enregistré dans le registre des facteurs, mais absent de
`config/factors.yaml` : aucun classement de production ne l'utilise. Mesure :
`make labo-momentum-residuel` (essai figé : `config/essais/2026-11-10_momentum_residuel.yaml`).
"""
from __future__ import annotations

import numpy as np

from packages.ranking.factors import FactorContext, factor_calcs

STATUT = "CANDIDATE_UNCALIBRATED"
ESTIMATION = 756            # 36 mois de séances
FORMATION = 252             # 12 mois
SAUT = 21                   # le dernier mois est exclu
N_MARCHE_MIN = 20           # sous 20 titres cotés, la moyenne n'est pas un « marché »
COUVERTURE = 0.80           # un jour compte s'il est coté par 80 % des titres (cf. panel)


def verifier_fenetres(estimation: int, formation: int, saut: int) -> None:
    """Refuse les fenêtres dégénérées (cf. PIÈGE VERROUILLÉ)."""
    if not 0 <= saut < formation:
        raise ValueError(f"saut {saut} hors de [0, formation {formation})")
    if estimation < 2 * formation:
        raise ValueError(
            f"estimation {estimation} < 2 × formation {formation} : avec une constante, "
            "le score dégénère en retournement court terme")


def rendements_marche(R: np.ndarray, n_min: int = N_MARCHE_MIN) -> np.ndarray:
    """Rendement équipondéré par séance ; NaN si moins de `n_min` titres cotés ce jour."""
    cotes = np.isfinite(R)
    n = cotes.sum(axis=1)
    somme = np.where(cotes, R, 0.0).sum(axis=1)
    return np.where(n >= n_min, somme / np.maximum(n, 1), np.nan)


def scores_residuels(R: np.ndarray, m: np.ndarray, *, formation: int = FORMATION,
                     saut: int = SAUT, standardise: bool = True) -> np.ndarray:
    """Score par titre. `R` : (estimation × N) rendements dont la DERNIÈRE ligne est le
    jour de décision ; `m` : rendement du marché sur les mêmes séances.

    NaN pour un titre dont la fenêtre a un trou : on ne comble pas, on ne classe pas."""
    estimation, n = R.shape
    verifier_fenetres(estimation, formation, saut)
    out = np.full(n, np.nan)
    if m.shape[0] != estimation or not np.isfinite(m).all():
        return out
    ok = np.isfinite(R).all(axis=0)
    if not ok.any():
        return out
    y = R[:, ok]
    mc = m - m.mean()
    var = float(mc @ mc)
    if var <= 0.0:
        return out
    beta = (mc @ (y - y.mean(axis=0))) / var
    residus = y - y.mean(axis=0) - np.outer(mc, beta)
    f = residus[estimation - formation: estimation - saut]
    somme = f.sum(axis=0)
    if standardise:
        sd = f.std(axis=0, ddof=1)
        somme = np.where(sd > 0, somme / (np.where(sd > 0, sd, 1.0) * np.sqrt(f.shape[0])),
                         np.nan)
    out[ok] = somme
    return out


def matrice_cloture(par_titre: dict[str, dict[str, float]],
                    jours: list[str]) -> tuple[np.ndarray, list[str]]:
    """(jours × titres) des clôtures, NaN là où le titre n'a pas coté. Alignée PAR DATE."""
    syms = sorted(par_titre)
    C = np.full((len(jours), len(syms)), np.nan)
    rang = {j: i for i, j in enumerate(jours)}
    for k, s in enumerate(syms):
        for j, c in par_titre[s].items():
            i = rang.get(j)
            if i is not None and c is not None and c > 0:
                C[i, k] = c
    return C, syms


def calendrier_commun(par_titre: dict[str, dict[str, float]],
                      couverture: float = COUVERTURE) -> list[str]:
    """Jours cotés par au moins `couverture` des titres, triés."""
    compte: dict[str, int] = {}
    for cours in par_titre.values():
        for j in cours:
            compte[j] = compte.get(j, 0) + 1
    seuil = max(1, int(round(couverture * len(par_titre))))
    return sorted(j for j, n in compte.items() if n >= seuil)


def _jour(barre: object) -> str:
    ts = getattr(barre, "ts", None)
    d = getattr(ts, "date", None)
    return d().isoformat() if callable(d) else str(ts)[:10]


@factor_calcs.register("residual_momentum")
class MomentumResiduel:
    """Facteur du registre : `values(ctx)` → {symbole: score}, information ≤ `ctx.t`."""

    name = "residual_momentum"
    sector_neutral = False

    def __init__(self, estimation: int = ESTIMATION, formation: int = FORMATION,
                 saut: int = SAUT, standardise: bool = True) -> None:
        verifier_fenetres(estimation, formation, saut)
        self.estimation, self.formation = estimation, formation
        self.saut, self.standardise = saut, standardise

    def values(self, ctx: FactorContext) -> dict[str, float]:
        par_titre = {
            s: {_jour(b): float(b.close) for b in barres[: min(ctx.t, len(barres) - 1) + 1]
                if b.close is not None and b.close > 0}
            for s, barres in ctx.panel.items()}
        out = {s: float("nan") for s in ctx.panel}
        jours = calendrier_commun(par_titre)[-(self.estimation + 1):]
        if len(jours) < self.estimation + 1:
            return out
        C, syms = matrice_cloture(par_titre, jours)
        R = C[1:] / C[:-1] - 1.0
        scores = scores_residuels(R, rendements_marche(R), formation=self.formation,
                                  saut=self.saut, standardise=self.standardise)
        out.update({s: float(v) for s, v in zip(syms, scores, strict=True)})
        return out
