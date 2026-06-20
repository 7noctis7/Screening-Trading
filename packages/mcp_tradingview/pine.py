"""Traducteur **preset YAML → Pine Script v5** pour cross-validation sur TradingView.

Le preset de production est multi-facteurs ET cross-sectionnel (qualité top-K → risk-parity ERC →
DD-target → no-trade band). Pine s'exécute **par symbole** : la sélection qualité et l'ERC (qui
comparent les actifs entre eux) ne sont PAS exprimables en Pine — on les documente en commentaire.
On reproduit fidèlement la couche **par actif** : EXPOSITION pilotée par la volatilité (DD-cible) +
**no-trade band** (hystérésis anti-churn) + plafond de poids. Objectif : recouper la logique Python.

`generate_pine_script` est PURE (aucun réseau) et déterministe → testable hors-ligne.
"""

from __future__ import annotations

import math
from typing import Any

# Défauts alignés sur la PRODUCTION (cf. preset_backtest / env QUANT_DD_TARGET=0.45).
_DEFAULTS: dict[str, float] = {
    "dd_target": 0.45, "k_dd": 2.5, "band": 0.03, "max_weight": 0.10,
    "lookback": 120, "top_k": 30, "blackout_move": 0.12,
}


def _coerce_config(yaml_config: Any) -> dict:
    """Accepte un dict, ou une chaîne YAML (parsée si PyYAML dispo), ou None → {}."""
    if yaml_config is None:
        return {}
    if isinstance(yaml_config, dict):
        return yaml_config
    if isinstance(yaml_config, str):
        try:
            import yaml  # type: ignore
            parsed = yaml.safe_load(yaml_config)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:  # noqa: BLE001 — PyYAML absent ou YAML invalide → défauts
            return {}
    raise TypeError(f"yaml_config doit être dict | str | None (reçu {type(yaml_config).__name__})")


def _params(cfg: dict) -> dict[str, float]:
    """Fusionne params (racine + section 'params') avec les défauts de production."""
    flat: dict[str, Any] = {}
    flat.update(cfg.get("params", {}) if isinstance(cfg.get("params"), dict) else {})
    flat.update({k: v for k, v in cfg.items() if k != "params"})
    out = dict(_DEFAULTS)
    for k in _DEFAULTS:
        if k in flat and flat[k] is not None:
            try:
                out[k] = float(flat[k])
            except (TypeError, ValueError):
                pass
    return out


def generate_pine_script(strategy_name: str, yaml_config: Any = None) -> str:
    """Génère un script Pine v5 (string) reproduisant la couche exposition du preset.

    Args:
        strategy_name: nom lisible (titre de la stratégie TradingView).
        yaml_config:  dict ou YAML décrivant les params (dd_target, k_dd, band, max_weight, lookback…).

    Returns:
        Code Pine Script v5 prêt à coller dans l'éditeur TradingView.
    """
    name = (str(strategy_name).strip() or "preset").replace('"', "'")
    p = _params(_coerce_config(yaml_config))
    tgt_vol = round(p["dd_target"] / p["k_dd"], 4)          # vol-cible ≈ DD/k_dd (cohérent Python)
    return f"""//@version=5
// ─────────────────────────────────────────────────────────────────────────────
// Auto-généré par Quant Terminal — cross-validation du preset « {name} ».
// NOTE : la sélection QUALITÉ (top-{int(p['top_k'])}) et le RISK-PARITY (ERC) sont CROSS-SECTIONNELS
//        (comparaison entre actifs) → non exprimables en Pine (par symbole). Voir le moteur Python.
//        Ce script reproduit la couche PAR ACTIF : exposition vol-target (DD-cible) + no-trade band.
// POINT-IN-TIME : n'utilise que des données passées (ta.* sur barres clôturées) — pas de look-ahead.
// ─────────────────────────────────────────────────────────────────────────────
strategy("{name} — Quant Terminal", overlay=true, default_qty_type=strategy.percent_of_equity,
     default_qty_value=100, calc_on_every_tick=false, process_orders_on_close=true)

// === Paramètres (miroir du preset de production) ===
ddTarget = input.float({p['dd_target']}, "DD-cible (drawdown visé)", minval=0.05, maxval=1.0)
kDd      = input.float({p['k_dd']}, "k (vol-cible = DD/k)", minval=1.0, maxval=5.0)
band     = input.float({p['band']}, "No-trade band (hystérésis)", minval=0.0, maxval=0.20)
maxW     = input.float({p['max_weight']}, "Plafond d'exposition", minval=0.05, maxval=1.0)
lookback = input.int({int(p['lookback'])}, "Fenêtre de volatilité (j)", minval=20, maxval=300)
blackoutMove = input.float({p['blackout_move']}, "Blackout |move 2j| (earnings proxy)", minval=0.0)

// === Volatilité réalisée annualisée (point-in-time) ===
ret = math.log(close / close[1])
realizedVol = ta.stdev(ret, lookback) * math.sqrt(252)
targetVol = ddTarget / kDd                                  // ≈ {tgt_vol}

// === Exposition cible = min(plafond, vol-cible / vol réalisée) ===
rawExposure = realizedVol > 0 ? targetVol / realizedVol : 0.0
targetExposure = math.min(maxW, math.max(0.0, rawExposure))

// === Earnings blackout (proxy) : on n'augmente pas l'expo après un choc binaire récent ===
move2d = math.abs(close / close[2] - 1)
inBlackout = move2d > blackoutMove

// === No-trade band : on ne rebalance que si l'écart dépasse `band` (réduit le churn) ===
var float heldExposure = 0.0
needRebalance = math.abs(targetExposure - heldExposure) > band
heldExposure := (needRebalance and not inBlackout) ? targetExposure : heldExposure

// Mapping exposition → position (proxy long-only, sans levier ; cohérent avec le preset)
if heldExposure > 0.0
    strategy.entry("L", strategy.long, qty=heldExposure * 100)
else
    strategy.close("L")

// === Visualisation ===
plot(heldExposure, "Exposition tenue", color=color.new(color.teal, 0), linewidth=2)
plot(targetExposure, "Exposition cible", color=color.new(color.gray, 40))
bgcolor(inBlackout ? color.new(color.orange, 85) : na, title="Blackout earnings")
"""


def pine_equiv_backtest(times: list[str], closes: list[float], dd_target: float | None = None,
                        k_dd: float | None = None, band: float | None = None,
                        max_weight: float | None = None, lookback: int | None = None) -> dict:
    """Reproduit EN PYTHON la logique PAR SYMBOLE du script Pine (vol-target DD-cible + no-trade band),
    pour CHIFFRER l'écart avec le backtest TradingView. Point-in-time : l'exposition du jour t+1 n'utilise
    que l'info ≤ t. Long-only, sans levier. Renvoie des métriques nettes (pas de frais ici : comparaison
    de LOGIQUE, pas de perf absolue). Pur (stdlib)."""
    p = _params({})
    dd = dd_target if dd_target is not None else p["dd_target"]
    k = k_dd if k_dd is not None else p["k_dd"]
    bd = band if band is not None else p["band"]
    mw = max_weight if max_weight is not None else p["max_weight"]
    lb = int(lookback if lookback is not None else p["lookback"])
    n = min(len(times), len(closes))
    c = [float(x) for x in closes[:n]]
    if n < lb + 5:
        return {"available": False, "reason": "série trop courte"}
    rets = [c[i] / c[i - 1] - 1.0 for i in range(1, n)]            # rendements simples (j → j+1)
    logr = [math.log(c[i] / c[i - 1]) for i in range(1, n) if c[i - 1] > 0 and c[i] > 0]
    target_vol = dd / k
    held = 0.0
    eq = 1.0
    curve = [1.0]
    n_reb = 0
    expo_sum = 0.0
    expo_days = 0
    for j in range(lb, len(rets)):                                 # j indexe rets ; vol estimée sur logr[j-lb:j]
        win = logr[j - lb:j]
        if len(win) < 2:
            continue
        m = sum(win) / len(win)
        sd = math.sqrt(sum((x - m) ** 2 for x in win) / (len(win) - 1))
        vol = sd * math.sqrt(252)
        target = min(mw, max(0.0, target_vol / vol)) if vol > 0 else 0.0
        if abs(target - held) > bd:                                # no-trade band (hystérésis)
            held = target
            n_reb += 1
        eq *= (1.0 + held * rets[j])                              # applique l'expo tenue au rendement du jour
        curve.append(eq)
        expo_sum += held
        expo_days += 1
    if len(curve) < 3:
        return {"available": False, "reason": "pas assez de points"}
    # métriques
    dr = [curve[i] / curve[i - 1] - 1.0 for i in range(1, len(curve))]
    mu = sum(dr) / len(dr)
    sd = math.sqrt(sum((x - mu) ** 2 for x in dr) / (len(dr) - 1)) if len(dr) > 1 else 0.0
    sharpe = (mu / sd * math.sqrt(252)) if sd > 0 else 0.0
    peak = curve[0]; mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1.0)
    years = len(curve) / 252.0
    cagr = curve[-1] ** (1 / years) - 1.0 if years > 0 and curve[-1] > 0 else 0.0
    return {"available": True, "total_return": round(curve[-1] - 1.0, 4), "cagr": round(cagr, 4),
            "sharpe": round(sharpe, 2), "max_drawdown": round(mdd, 4),
            "avg_exposure": round(expo_sum / expo_days, 4) if expo_days else 0.0,
            "n_rebalances": n_reb, "n_days": len(curve),
            "params": {"dd_target": dd, "k_dd": k, "band": bd, "max_weight": mw, "lookback": lb}}
