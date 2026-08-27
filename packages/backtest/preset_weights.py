"""Calcul des poids du preset — production (dernière barre) et pas de rebalancement.

Extrait de `preset_backtest.py` le 25/08 (règle < 400 lignes/fichier). Comportement
repris à l'identique.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.cov_risk import cov_annual as _cov_annual
from packages.backtest.cov_risk import cov_for_step
from packages.backtest.panel import aligner_sans_trous
from packages.backtest.preset_config import MIN_BARRES_REGIME, _price_universe
from packages.backtest.preset_diag import Diag
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
    regime_detail as _regime_detail_fn,
)
from packages.backtest.preset_helpers import (
    regime_mult as _regime_mult_fn,
)
from packages.portfolio.optimize import equal_risk_contribution


def _concentrate(w: np.ndarray, min_weight: float) -> np.ndarray:
    """Élimine les positions sous `min_weight` (fraction de l'investi) et redistribue leur poids
    aux survivants → portefeuille CONCENTRÉ sur les meilleures convictions, même gross investi.
    Anti-« poussière » : fini les dizaines de lignes à quelques dollars."""
    inv = float(w.sum())
    if inv <= 0 or min_weight <= 0:
        return w
    w = np.where(w / inv < min_weight, 0.0, w)
    keep = float(w.sum())
    return w * (inv / keep) if keep > 0 else w


def _erc_blackout(A, cov, t, blackout_move, min_names):
    """ERC + blackout appliqué SEULEMENT s'il laisse un portefeuille diversifié, puis renormalisé."""
    w = np.asarray(equal_risk_contribution(cov), float)
    last2 = A[:, t] / A[:, t - 2] - 1
    w_bl = np.where(np.abs(last2) > blackout_move, 0.0, w)
    if int((w_bl > 0).sum()) >= min_names:
        w = w_bl
    s1 = w.sum()
    return w / s1 if s1 > 0 else w


def _weights_at(A, rets, t, lookback, blackout_move, max_weight, min_names, tgt_vol):
    """Poids du preset au temps t (ERC + blackout diversifié + plafond + DD-target)."""
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return None
    cov = _cov_annual(win)
    w = _cap_weights_fn(_erc_blackout(A, cov, t, blackout_move, min_names), max_weight)
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    return w * gross


def _eligibles(data: dict, lookback: int) -> list:
    """Titres assez profonds pour la PRODUCTION : `regime_mult` lit une MM200 et le PIC
    historique, il lui faut au moins MIN_BARRES_REGIME barres. Le seuil était à `lookback`
    (120) : mesuré, une seule série de 125 barres, incapable d'entrer dans le top-K,
    déplaçait les poids de PRODUCTION de 2 points — la MM200 devenait une MM125."""
    return [s for s, b in data.items() if b and len(b) > max(lookback, MIN_BARRES_REGIME)]


def _selection(data: dict, quality: dict, lookback: int, top_k: int, d: Diag):
    """Univers de production.

    Le REPLI `syms[:top_k]` est un INCIDENT, pas un défaut normal : sans score
    qualité, la sélection devient l'ordre arbitraire du dictionnaire. Il était
    silencieux ; il est désormais tracé.
    """
    syms = _eligibles(data, lookback)
    _seuil = max(lookback, MIN_BARRES_REGIME)
    d.note("éligibles", f"{len(syms)} titres (> {_seuil} barres)")
    if len(syms) < 5:
        d.stop(f"{len(syms)} titres éligibles (< 5) — historique insuffisant")
        return None
    q = {s: quality.get(s) for s in syms if quality.get(s) is not None}
    if len(q) >= 5:
        d.note("score qualité", f"{len(q)} titres scorés → top-{top_k} par qualité")
        return sorted(q, key=lambda s: q[s], reverse=True)[:top_k]
    # REPLI PAR MOMENTUM, plus jamais par l'ordre du dictionnaire.
    #
    # Constaté en production le 26/08 : `make live` tourne en mode LÉGER, qui coupe
    # la section `fundamentals` — `quality` est donc TOUJOURS vide à l'exécution, et
    # le repli tirait les 12 premiers symboles de `data`. Conséquence en chaîne :
    # `mkt`, l'indice de marché des portes de régime et d'ampleur, était la moyenne
    # de ces 12 noms arbitraires. Les portes concluaient « marché en chute > 15 %,
    # aucun titre au-dessus de sa MM200 » et mettaient l'exposition brute à ZÉRO. Le
    # satellite actions était donc vide non par décision de risque, mais parce qu'on
    # mesurait le risque d'un panier tiré au hasard.
    #
    # `_price_universe` est le MÊME classement momentum que le backtest, aligné par
    # date et sans fondamentaux : il fonctionne quelle que soit la raison de
    # l'absence de scores (mode léger, réseau coupé, quota d'API).
    # `au_dernier_point=True` le mesure sur les 252 dernières barres et non au début
    # de la fenêtre : en production, « aujourd'hui » EST le dernier point connu, donc
    # aucune fuite — alors que garder le point de départ revenait à figer l'univers
    # sur le momentum de 2015.
    d.note("score qualité", f"⚠️  {len(q)} scoré(s) (< 5) → repli MOMENTUM "
                            f"(prix seuls, aligné par date)")
    return _price_universe(data, syms, lookback, top_k, au_dernier_point=True)


def _prod_panel(data: dict, universe: list, min_names: int):
    """Matrice de prix de PRODUCTION, alignée PAR DATE et sans NaN.

    MIGRATION DU 26/08. Cette fonction empilait les séries POSITIONNELLEMENT
    (`fenetre_commune`) alors que le backtest était passé à l'alignement par date en #341.
    Production et backtest ne mesuraient donc pas la même chose : sur un panier mêlant
    actions (5 séances/semaine) et crypto (7 j/7), les colonnes des deux familles portaient
    des dates différentes — jusqu'à trois ans d'écart sur onze ans. La covariance de l'ERC,
    l'indice de marché de la porte de régime et le tilt momentum étaient tous calculés sur
    ce mélange.

    `aligner_sans_trous` plutôt qu'`aligner_par_date` : la production dimensionne des ordres
    réels, un NaN y produirait un poids FAUX plutôt qu'une erreur visible. Même choix que
    pour le ledger et les courbes du dashboard (ADR-0037).
    """
    if len(universe) < 2:
        return None, None
    noms, _dates, A = aligner_sans_trous(data, list(universe), min_names)
    if len(noms) < 2 or A.shape[1] < MIN_BARRES_REGIME:
        return None, None
    return noms, A


def preset_latest_weights(data: dict, quality: dict | None = None,
                          asset_classes: dict | None = None,
                          dd_target: float = 0.35, band: float = 0.03, lookback: int = 120,
                          top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
                          max_weight: float = 0.10, min_names: int = 12,
                          regime_gate: bool = True, mom_tilt: bool = True,
                          breadth_gate: bool = True, min_weight: float = 0.025,
                          corr_tighten: bool = True, cov_denoise: bool = False) -> dict:
    """Poids cibles ACTUELS du preset (dernière barre) — pilote la PRODUCTION (make live).

    Même logique que le backtest (qualité top-K -> ERC -> DD-target -> blackout),
    mais calculée au dernier point. Renvoie {symbol: poids}, reste en cash.

    Pour savoir POURQUOI c'est vide : `preset_latest_weights_explique`.
    """
    poids, _ = preset_latest_weights_explique(
        data, quality, asset_classes, dd_target, band, lookback, top_k, k_dd,
        blackout_move, max_weight, min_names, regime_gate, mom_tilt, breadth_gate,
        min_weight, corr_tighten, cov_denoise)
    return poids


def preset_latest_weights_explique(
        data: dict, quality: dict | None = None, asset_classes: dict | None = None,
        dd_target: float = 0.35, band: float = 0.03, lookback: int = 120,
        top_k: int = 30, k_dd: float = 1.6, blackout_move: float = 0.12,
        max_weight: float = 0.10, min_names: int = 12, regime_gate: bool = True,
        mom_tilt: bool = True, breadth_gate: bool = True, min_weight: float = 0.025,
        corr_tighten: bool = True, cov_denoise: bool = False) -> tuple[dict, Diag]:
    """Identique, mais renvoie AUSSI le journal des étages. Aucun chiffre ne change."""
    d = Diag()
    universe = _selection(data, quality or {}, lookback, top_k, d)
    if universe is None:
        return {}, d
    universe, A = _prod_panel(data, universe, min_names)
    if A is None:
        d.stop("panel inexploitable : après intersection des dates, moins de 2 "
               f"noms ou moins de {MIN_BARRES_REGIME} dates communes")
        return {}, d
    d.note("panel aligné",
           f"{len(universe)} noms × {A.shape[1]} dates communes (sans NaN)")
    L, t = A.shape[1], A.shape[1] - 1
    rets = A[:, 1:] / A[:, :-1] - 1
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        d.stop(f"fenêtre de covariance de {win.shape[1]} barres (< 20)")
        return {}, d
    cov, _, _ = cov_for_step(win, denoise=cov_denoise)
    w = _erc_blackout(A, cov, t, blackout_move, min_names)
    if mom_tilt:
        w = _mom_tilt_fn(A, t, w)
    w = _cap_weights_fn(w, _adaptive_cap_fn(cov, max_weight, corr_tighten))
    gross = _exposition(A, cov, w, np.asarray(A.mean(axis=0)), t, d, k_dd=k_dd,
                        dd_target=dd_target, regime_gate=regime_gate,
                        breadth_gate=breadth_gate)
    w = _concentrate(w * gross, min_weight)
    poids = {universe[i]: round(float(w[i]), 4)
             for i in range(len(universe)) if w[i] > 1e-4}
    if not poids:
        d.stop("aucun poids au-dessus du seuil après exposition brute et concentration")
    else:
        d.note("poids retenus",
               f"{len(poids)} ligne(s), somme {sum(poids.values()):.1%}")
    return poids, d


def _exposition(A, cov, w, mkt, t, d: Diag, *, k_dd, dd_target, regime_gate,
                breadth_gate):
    """Exposition brute et effet de CHAQUE porte — ce qui manquait le plus."""
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    pv = float(np.sqrt(max(0.0, w @ cov @ w)))
    gross = 0.0 if pv <= 0 else min(1.0, tgt_vol / pv)
    d.porte("DD-target", gross)
    if regime_gate:
        rm = _regime_mult_fn(mkt, t)
        d.porte("régime", rm)
        d.note("régime (détail)", _regime_detail_fn(mkt, t))
        gross *= rm
    if breadth_gate:
        am = float(np.clip(_breadth_fn(A, t) / 0.5, 0.0, 1.0))
        d.porte("ampleur", am)
        gross *= am
    if gross <= 0:
        zero = [k for k, v in d.gross.items() if v <= 0]
        noms = ", ".join(zero) or "DD-target"
        d.stop(f"exposition brute NULLE — porte(s) à zéro : {noms}")
    return gross
