"""Boucle du backtest preset — panel, univers, garde-fous, pas de rebalancement.

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier). Comportement
repris à l'identique : mêmes seuils, même ordre d'application des garde-fous.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.panel import (
    aligner_par_date,
    dernier_connu,
    fenetre_commune,
)
from packages.backtest.preset_config import (
    momentum_rank,
)
from packages.backtest.preset_helpers import (
    adaptive_cap as _adaptive_cap_fn,
)
from packages.backtest.preset_helpers import (
    breadth as _breadth_fn,
)
from packages.backtest.preset_helpers import (
    cap_weights as _cap_weights_fn,
)
from packages.backtest.preset_helpers import (
    mom_tilt as _mom_tilt_fn,
)
from packages.backtest.preset_helpers import (
    regime_mult as _regime_mult_fn,
)
from packages.execution.costs import CostModel
from packages.portfolio.risk_advanced import ewma_vol
from packages.portfolio.risk_overlay import drawdown_taper


class Compteurs:
    """COMPTEURS DE DÉCLENCHEMENT — un garde-fou qui ne s'est jamais déclenché est soit inutile,
    soit cassé, et dans les deux cas il faut le savoir. Sans ces compteurs, « levier rejeté »
    et « levier jamais activé » produisent EXACTEMENT la même ligne de résultat (24/08).
    Seuls les garde-fous ACTIFS reçoivent un compteur : une clé absente = « désactivé »,
    une clé à 0 = « actif mais jamais déclenché ». Confondre les deux, c'est crier au loup.

    AMPLEUR, pas seulement fréquence. « 38 déclenchements » avec un ΔSharpe de +0,00 ne dit pas
    si le garde-fou a été neutralisé ou s'il n'a rien eu à corriger. On accumule donc l'effet
    multiplicatif appliqué (1,0 = sans effet) pour publier une moyenne à côté du compte.
    """

    def __init__(self, *, max_weight, regime_gate, breadth_gate, risk_overlay, band) -> None:
        self.decl = {"blackout": 0, "vol_target": 0}
        if max_weight:
            self.decl["plafond"] = 0
        if regime_gate:
            self.decl["regime"] = 0
        if breadth_gate:
            self.decl["ampleur"] = 0
        if risk_overlay:
            self.decl["taper_dd"] = self.decl["frein_vol"] = 0
        if band > 0:
            self.decl["bande"] = 0
        self.ampl: dict[str, list[float]] = {k: [] for k in self.decl}

    def note(self, cle: str, declenche: bool, ampleur: float) -> None:
        self.decl[cle] += int(declenche)
        self.ampl[cle].append(ampleur)

    def moyennes(self) -> dict:
        return {k: round(float(sum(v) / len(v)), 4) for k, v in self.ampl.items() if v}


def panel_backtest(data: dict, eligibles: list, aligner_dates: bool, couverture: float):
    """Panel du backtest. `min(len)` laissait la série la plus COURTE fixer la profondeur du panel
    entier (24/08 : 929 titres, 10 ans en base, 7 rebalancements). On garde la fenêtre la plus
    longue couverte par `couverture` des noms ; `couverture=1.0` restaure l'ancien comportement.

    ALIGNEMENT PAR DATE (cf. panel.aligner_par_date) : l'empilement positionnel suppose que
    toutes les séries se terminent le même jour — faux pour un délisté, dont la dernière barre
    est sa radiation. Sur un calendrier uniforme, les deux produisent la MÊME matrice.
    """
    if aligner_dates:
        syms, _dates, Ad, diag = aligner_par_date(data, eligibles, couverture=couverture)
        if len(syms) < 5:
            return None
        return syms, Ad.shape[1], {s: Ad[i] for i, s in enumerate(syms)}, diag
    syms, L, diag = fenetre_commune(data, eligibles, couverture=couverture)
    if len(syms) < 5:
        return None
    return syms, L, {s: np.asarray([b.close for b in data[s]][-L:], float) for s in syms}, diag


def univers_backtest(syms: list, M: dict, quality: dict, lookback: int, top_k: int,
                     legacy_quality_universe: bool) -> list:
    """#2 ANTI-FUITE : en backtest, le score `quality` est le score ACTUEL → l'appliquer à des
    dates passées = look-ahead + biais du survivant. On sélectionne donc l'univers par MOMENTUM
    prix-only mesuré au DÉBUT du backtest (aucune info future). `legacy_quality_universe=True`
    rétablit l'ancien comportement (fuite — pour comparaison uniquement). En PRODUCTION, le tilt
    qualité du jour reste légitime."""
    if legacy_quality_universe:
        q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
        return (sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
                if len(q) >= 5 else syms[:top_k])
    return momentum_rank(M, syms, max(lookback, 50), top_k)


def _poids_pas(A, t, w, dispo, cov, cpt: Compteurs, *, blackout_move, mom_tilt,
               max_weight, corr_tighten):
    """Poids du pas : ERC (déjà dans `w`) → blackout → tilt momentum → plafond."""
    # `last2` d'un titre non négociable vaut NaN : on le neutralise pour que la comparaison
    # du blackout ne devienne pas False par propagation (son poids est déjà nul).
    last2 = np.nan_to_num(A[:, t] / A[:, t - 2] - 1, nan=0.0)   # blackout : post-choc binaire
    bl = (np.abs(last2) > blackout_move) & (w > 0)
    cpt.note("blackout", bool(bl.any()), 1.0 - float(w[bl].sum()))  # poids retiré par le blackout
    w = np.where(np.abs(last2) > blackout_move, 0.0, w)
    ssum = w.sum()
    w = w / ssum if ssum > 0 else w
    if mom_tilt:                                # #4 incline vers les leaders (momentum)
        w = _mom_tilt_fn(A, t, w)
    if max_weight:                              # plafond (adaptatif si corr_tighten)
        cap = _adaptive_cap_fn(cov, max_weight, corr_tighten)   # cov = sous-ensemble négociable
        avant = w.copy()
        w = _cap_weights_fn(w, cap)             # a-t-il MORDU, ou juste tourné ?
        cpt.note("plafond", bool((avant > cap + 1e-12).any()),
                 1.0 - 0.5 * float(np.abs(w - avant).sum()))
    return w


def _gross_pas(A, mkt, t, w, dispo, cov, cpt: Compteurs, port: list, *, tgt_vol,
               regime_gate, breadth_gate, risk_overlay, ro_dd_soft, ro_dd_hard,
               ewma_lam, per_year, dd_now):
    """Exposition brute du pas : DD-target → régime → ampleur → overlay. Jamais > 1 (pas de levier)."""
    # `cov` porte le SOUS-ENSEMBLE négociable : la forme quadratique doit utiliser les mêmes
    # indices. Identique à `w @ cov @ w` quand tout est négociable (le cas d'un panel complet).
    wd = w[dispo]
    pv = float(np.sqrt(max(0.0, wd @ cov @ wd)))   # DD-target : exposition pilotée par la vol
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    cpt.note("vol_target", bool(pv > 0 and tgt_vol < pv), gross if pv > 0 else 1.0)
    if regime_gate:                     # #5 régime + #6 frein DD (≤ 1, jamais de levier)
        rm = _regime_mult_fn(mkt, t)
        cpt.note("regime", rm < 1.0 - 1e-12, rm)
        gross *= rm
    if breadth_gate:                    # #8 ampleur de marché (rallye étroit → ↓)
        am = float(np.clip(_breadth_fn(A, t) / 0.5, 0.0, 1.0))
        cpt.note("ampleur", am < 1.0 - 1e-12, am)
        gross *= am
    if risk_overlay:                    # overlay : taper DD + vol prévue
        tp = drawdown_taper(dd_now, ro_dd_soft, ro_dd_hard)
        cpt.note("taper_dd", tp < 1.0 - 1e-12, tp)
        gross *= tp
        if pv > 0 and len(port) >= 10:  # EWMA > réalisée → réduire
            fv = ewma_vol(port[-60:], lam=ewma_lam, annualize=int(round(per_year)))
            if fv > pv:
                cpt.note("frein_vol", True, pv / fv)
                gross *= pv / fv
    return gross


def _fwd(A, entry: int, nxt: int, aligner_dates: bool):
    """Rendement RÉALISÉ après exécution. Une ligne dont la cotation s'arrête entre l'entrée et
    la sortie est soldée au DERNIER cours connu — sinon son rendement serait NaN et contaminerait
    tout le pas. C'est une approximation optimiste pour une faillite (le dernier cours coté n'est
    pas zéro) : le biais du survivant ainsi mesuré est un MINORANT."""
    if not aligner_dates:
        return A[:, nxt] / A[:, entry] - 1
    px_e, px_n = dernier_connu(A, entry), dernier_connu(A, nxt)
    return np.nan_to_num(np.divide(px_n, px_e, out=np.full_like(px_n, np.nan),
                                   where=np.isfinite(px_e) & (px_e > 0)) - 1.0, nan=0.0)


def couts_univers(universe: list, asset_classes: dict) -> np.ndarray:
    """Barème aller-retour par classe d'actifs."""
    return np.asarray([CostModel.for_asset_class(asset_classes.get(s, "equity")).round_trip_bps
                       / 1e4 for s in universe])
