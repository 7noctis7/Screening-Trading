"""Backtest du PRESET stratégique « best practice » (point-in-time, anti-fuite).

Combine, à chaque rebalancement :
  1. **Tilt qualité** : univers = top-K par score fondamental (statique → neutre vis-à-vis des prix,
     pas de fuite ; c'est un *sleeve* facteur qualité).
  2. **Risk-parity (ERC)** : chaque actif contribue également au risque (covariance trailing).
  3. **DD-target exposure** : exposition brute dimensionnée pour viser un drawdown cible
     (vol-cible ≈ DD/1.6 — anti cash-drag), plafonnée à 100 % (**jamais de levier**) → le reste en cash.
     Tilt momentum (#4) + porte de régime/frein DD (#5/#6) appliqués au gross/poids.
  4. **Earnings blackout (proxy)** : on évite d'entrer juste après un choc binaire (|move 2 j| élevé).
  5. **No-trade band** : on ne bouge un poids que s'il dérive de plus de `band` (turnover ↓).
  6. **Coûts par classe d'actifs** déduits du turnover (réalisme).

Compare le preset à l'équipondéré (bench) et, si fourni, à la courbe du swing. numpy pur, testable.

DÉCOUPAGE (25/08) — ce fichier faisait 793 lignes avec cinq fonctions au-dessus de 50, contre une
règle d'architecture à 400/50. Il est désormais la FAÇADE : l'API publique est inchangée (mêmes
noms importables ici), les implémentations vivent dans `preset_config`, `preset_core`,
`preset_weights`, `preset_curves`, `preset_livre` et `preset_compta`.
"""

from __future__ import annotations

import numpy as np

from packages.backtest.conviction_backtest import _stats
from packages.backtest.cov_risk import cov_for_step, summarize
from packages.backtest.panel import COUVERTURE_DEFAUT
from packages.backtest.preset_compta import preset_ledger
from packages.backtest.preset_config import (
    ALIGNEMENT_PAR_DEFAUT,
    EXEC_LAG_PAR_DEFAUT,
    MIN_BARRES_REGIME,
    _price_universe,
)
from packages.backtest.preset_core import (
    Compteurs,
    _fwd,
    _gross_pas,
    _poids_pas,
    couts_univers,
    panel_backtest,
    univers_backtest,
)
from packages.backtest.preset_curves import preset_equity_daily, preset_trade_log
from packages.backtest.preset_weights import (
    _concentrate,
    _weights_at,
    preset_latest_weights,
)
from packages.portfolio.optimize import equal_risk_contribution

__all__ = [
    "ALIGNEMENT_PAR_DEFAUT", "EXEC_LAG_PAR_DEFAUT", "MIN_BARRES_REGIME",
    "_concentrate", "_price_universe", "_weights_at",
    "preset_backtest", "preset_equity_daily", "preset_latest_weights",
    "preset_ledger", "preset_trade_log",
]


def _cov_pas(A, rets, t, n, lookback, cov_denoise):
    """Covariance et ERC du pas, ou None si la fenêtre est inexploitable.

    NÉGOCIABILITÉ À CE PAS : un titre pas encore introduit, ou déjà radié, n'a pas de fenêtre
    de covariance exploitable. On le met à poids nul plutôt que de propager des NaN dans l'ERC.
    Sur une matrice complète, `dispo` est tout à True → aucun changement.
    """
    win = rets[:, max(0, t - lookback):t]
    if win.shape[1] < 20:
        return None
    dispo = np.isfinite(win).all(axis=1) & np.isfinite(A[:, t]) & np.isfinite(A[:, t - 2])
    if dispo.sum() < 2:
        return None
    cov, cd, deg = cov_for_step(win[dispo], denoise=cov_denoise)
    w = np.zeros(n)
    w[dispo] = np.asarray(equal_risk_contribution(cov), float)   # risk-parity
    return dispo, cov, cd, deg, w


def _boucle(A, mkt, rets, universe, rt, cpt: Compteurs, *, L, start, step, lookback,
            cov_denoise, blackout_move, mom_tilt, max_weight, corr_tighten, tgt_vol,
            regime_gate, breadth_gate, risk_overlay, ro_dd_soft, ro_dd_hard, ewma_lam,
            per_year, exec_lag, band, aligner_dates) -> dict:
    """Déroule les pas de rebalancement et renvoie séries + diagnostics de covariance."""
    prev_w = np.zeros(len(universe))
    port: list[float] = []
    gross_hist: list[float] = []
    cov_diags: list[dict] = []               # M1 : exploitabilité de la covariance
    n_degraded, turn = 0, 0.0
    eq_strat, peak_strat = 1.0, 1.0          # equity stratégie (overlay risque)
    for t in range(start, L - 1, step):
        pas = _cov_pas(A, rets, t, len(universe), lookback, cov_denoise)
        if pas is None:
            continue
        dispo, cov, cd, deg, w = pas
        cov_diags.append(cd)
        n_degraded += int(deg)
        w = _poids_pas(A, t, w, dispo, cov, cpt, blackout_move=blackout_move,
                       mom_tilt=mom_tilt, max_weight=max_weight, corr_tighten=corr_tighten)
        dd_now = eq_strat / peak_strat - 1.0 if peak_strat > 0 else 0.0
        w = w * _gross_pas(A, mkt, t, w, dispo, cov, cpt, port, tgt_vol=tgt_vol,
                           regime_gate=regime_gate, breadth_gate=breadth_gate,
                           risk_overlay=risk_overlay, ro_dd_soft=ro_dd_soft,
                           ro_dd_hard=ro_dd_hard, ewma_lam=ewma_lam,
                           per_year=per_year, dd_now=dd_now)
        if band > 0 and prev_w.sum() > 0:                       # bande de non-trading
            # « au moins un nom bloqué » est vrai à presque chaque pas et n'apprend rien : on
            # mesure la PART des noms que la bande ramène à leur poids précédent.
            dans = np.abs(w - prev_w) < band
            cpt.note("bande", bool(dans.any()), 1.0 - float(dans.mean()))
            w = np.where(dans, prev_w, w)
        entry = min(t + exec_lag, L - 1)                        # M-1 : exécution à t+exec_lag
        fwd = _fwd(A, entry, min(entry + step, L - 1), aligner_dates)
        ret_step = float((w * fwd).sum()) - float((np.abs(w - prev_w) * rt).sum())
        port.append(ret_step)
        eq_strat *= (1.0 + ret_step)             # maj equity (taper au pas suivant)
        peak_strat = max(peak_strat, eq_strat)
        turn += float(np.abs(w - prev_w).sum())
        gross_hist.append(float(w.sum()))
        prev_w = w
    return {"port": port, "gross_hist": gross_hist, "cov_diags": cov_diags,
            "n_degraded": n_degraded, "turn": turn}


def _cum(series: list) -> list:
    e = np.cumprod(1 + np.asarray(series, dtype=float))
    return [1.0] + [round(float(x), 4) for x in e]


def _sortie(res: dict, cpt: Compteurs, universe, A, L, start, step, *, cov_denoise,
            panel_diag, dd_target, band, tgt_vol, per_year, swing_equity,
            aligner_dates) -> dict:
    """Assemble le résultat : preset, bench équipondéré (même univers) et swing éventuel."""
    port, turn = res["port"], res["turn"]
    out = {"available": True, "step_days": step, "top_k": len(universe),
           # L'univers RETENU, pas seulement son cardinal : sans les noms, impossible de savoir
           # si un titre donné (un délisté, par exemple) a réellement été sélectionné.
           "univers": list(universe),
           "cov_diag": summarize(res["cov_diags"], res["n_degraded"], cov_denoise),
           "panel": panel_diag, "n_steps": len(port),
           "declenchements": dict(cpt.decl),
           # Effet MOYEN appliqué (1,0 = aucun). Un garde-fou à 0,999 s'est déclenché sans rien
           # déplacer : c'est ce qu'il fallait pouvoir lire à côté du compte de déclenchements.
           "ampleur": cpt.moyennes(),
           "preset": _stats(port, per_year),
           "turnover_annual": round(turn / len(port) * per_year, 2),
           "dd_target": dd_target, "band": band, "target_vol": round(tgt_vol, 4),
           "avg_gross": round(float(np.mean(res["gross_hist"])) if res["gross_hist"] else 0.0, 4),
           # Rendements PAR PAS, non arrondis. `curves` est cumulé ET arrondi à 4 décimales :
           # en redériver les rendements perd assez de précision pour fausser une erreur-type.
           # Le test de différence de Sharpe (packages/research/sharpe_diff) en a besoin bruts.
           "rendements": [float(x) for x in port],
           "curves": {"preset": _cum(port)}}
    # bench équipondéré sur le MÊME univers (apples-to-apples : isole l'apport de la construction
    # risk-parity + DD-target + blackout + band vs un simple équipondéré plein-investi)
    #
    # `A[:, n] / A[:, t]` en BRUT donnait NaN dès qu'un titre SÉLECTIONNÉ était radié : sa colonne
    # vaut NaN après sa dernière cotation, `.mean()` propage, et toute la courbe de benchmark
    # partait en NaN à partir de ce pas — d'où le « −100,0 % / nan% » observé le 25/08 sur données
    # réelles. La stratégie, elle, traitait déjà le cas (`dernier_connu`, #341) ; c'est la ligne de
    # comparaison qui n'avait pas été migrée, donc le preset se comparait à RIEN sans le dire.
    # On lui applique exactement le même traitement — sinon le benchmark n'est plus apples-to-apples.
    bench = [float(np.nanmean(_fwd(A, t, min(t + step, L - 1), aligner_dates)))
             for t in range(start, L - 1, step)]
    out["benchmark"] = _stats(bench, per_year)
    out["curves"]["benchmark"] = _cum(bench)
    # swing (depuis sa courbe d'equity), ré-échantillonné sur la même grille
    if swing_equity and len(swing_equity) >= L:
        eq = np.asarray(swing_equity[-L:], float)
        grid = list(range(start, L, step))
        sr = [eq[b] / eq[a] - 1 for a, b in zip(grid[:-1], grid[1:]) if eq[a] > 0]
        if len(sr) >= 3:
            out["swing"] = _stats(sr, per_year)
            out["curves"]["swing"] = _cum(sr)
    return out


def _preparer(data: dict, quality: dict, lookback: int, step: int, top_k: int,
              legacy_quality_universe: bool, aligner_dates: bool, panel_couverture: float):
    """Éligibilité → panel → univers → matrice de prix et indice marché."""
    eligibles = [s for s, b in data.items() if b and len(b) > lookback + 2 * step]
    if len(eligibles) < 5:
        return None
    p = panel_backtest(data, eligibles, aligner_dates, panel_couverture)
    if p is None:
        return None
    syms, L, M, panel_diag = p
    universe = univers_backtest(syms, M, quality, lookback, top_k, legacy_quality_universe)
    A = np.asarray([M[s] for s in universe])                    # n × L
    mkt = np.nanmean(A, axis=0) if aligner_dates else A.mean(axis=0)  # indice marché (régime + DD)
    return universe, A, mkt, L, panel_diag


def preset_backtest(data: dict, quality: dict | None = None, asset_classes: dict | None = None,
                    swing_equity: list | None = None, dd_target: float = 0.25, band: float = 0.03,
                    step: int = 21, lookback: int = 120, top_k: int = 30, k_dd: float = 1.6,
                    blackout_move: float = 0.12, regime_gate: bool = True,
                    mom_tilt: bool = True, legacy_quality_universe: bool = False,
                    breadth_gate: bool = True, risk_overlay: bool = False,
                    ro_dd_soft: float = -0.08, ro_dd_hard: float = -0.20,
                    ewma_lam: float = 0.94, max_weight: float | None = None,
                    corr_tighten: bool = False, exec_lag: int = EXEC_LAG_PAR_DEFAUT,
                    cov_denoise: bool = False,
                    panel_couverture: float = COUVERTURE_DEFAUT,
                    aligner_dates: bool = ALIGNEMENT_PAR_DEFAUT) -> dict:
    """`cov_denoise` (M1, 08/20) : covariance DÉBRUITÉE par théorie des matrices aléatoires,
    avec repli inverse-vol quand moins de 2 directions sont distinguables du bruit. Défaut
    False = chiffres historiques inchangés au bit près ; le DIAGNOSTIC (`cov_diag`), lui, est
    toujours calculé et publié — mesurer d'abord, changer ensuite.

    `exec_lag` (audit 07/17, M-1) : nb de barres entre la DÉCISION (close t, sur info ≤t)
    et l'EXÉCUTION. **1 par défaut depuis le 25/08** = fill au close t+1, réaliste.
    0 = fill au close de la barre de signal — ancien défaut, mini look-ahead documenté : ce
    cours n'était pas exécutable au moment de la décision. Mesuré meilleur sur toutes les
    colonnes une fois l'alignement par date en place (cf. EXEC_LAG_PAR_DEFAUT)."""
    prep = _preparer(data, quality or {}, lookback, step, top_k,
                     legacy_quality_universe, aligner_dates, panel_couverture)
    if prep is None:
        return {"available": False}
    universe, A, mkt, L, panel_diag = prep
    tgt_vol = max(0.0, abs(dd_target)) / k_dd
    per_year = 252.0 / step
    start = max(lookback, 50)
    cpt = Compteurs(max_weight=max_weight, regime_gate=regime_gate,
                    breadth_gate=breadth_gate, risk_overlay=risk_overlay, band=band)
    res = _boucle(A, mkt, A[:, 1:] / A[:, :-1] - 1, universe,
                  couts_univers(universe, asset_classes or {}), cpt,
                  L=L, start=start, step=step, lookback=lookback, cov_denoise=cov_denoise,
                  blackout_move=blackout_move, mom_tilt=mom_tilt, max_weight=max_weight,
                  corr_tighten=corr_tighten, tgt_vol=tgt_vol, regime_gate=regime_gate,
                  breadth_gate=breadth_gate, risk_overlay=risk_overlay,
                  ro_dd_soft=ro_dd_soft, ro_dd_hard=ro_dd_hard, ewma_lam=ewma_lam,
                  per_year=per_year, exec_lag=exec_lag, band=band,
                  aligner_dates=aligner_dates)
    if len(res["port"]) < 3:
        return {"available": False}
    return _sortie(res, cpt, universe, A, L, start, step, cov_denoise=cov_denoise,
                   panel_diag=panel_diag, dd_target=dd_target, band=band,
                   tgt_vol=tgt_vol, per_year=per_year, swing_equity=swing_equity,
                   aligner_dates=aligner_dates)
