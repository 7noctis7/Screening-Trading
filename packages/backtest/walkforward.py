"""Walk-forward + out-of-sample — discipline anti-surapprentissage (López de Prado).

Fenêtres roulantes (train → test). Sur chaque train : sélection du meilleur jeu de
paramètres (Sharpe in-sample). Sur le test correspondant : évaluation OUT-OF-SAMPLE.
Les segments OOS sont concaténés → métriques OOS globales + **deflated Sharpe** sur
le nombre total de configurations essayées (correction du multiple testing).

Warm-up : chaque run reçoit un préfixe d'historique pour que les indicateurs soient
valides à l'entrée de la fenêtre (pas de NaN à `t0`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from packages.backtest.engine import BacktestEngine
from packages.backtest.statistics import deflated_sharpe_ratio, probabilistic_sharpe_ratio
from packages.execution.sim_broker import SimBroker
from packages.portfolio import metrics
from packages.risk.engine import RiskEngine


def make_windows(n: int, train: int, test: int) -> list[tuple[int, int, int, int]]:
    """(train_start, train_end, test_start, test_end) roulants, test non chevauchants."""
    out = []
    start = 0
    while start + train + test <= n:
        out.append((start, start + train, start + train, start + train + test))
        start += test
    return out


@dataclass
class WalkForwardResult:
    oos_returns: list[float] = field(default_factory=list)
    oos_metrics: dict = field(default_factory=dict)
    chosen_params: list[dict] = field(default_factory=list)
    n_trials: int = 0
    deflated_sharpe: float = 0.0
    psr: float = 0.0


class WalkForwardRunner:
    def __init__(self, strategy_factory: Callable[..., object],
                 sizer, risk_factory: Callable[[], RiskEngine],
                 broker_factory: Callable[[], SimBroker],
                 train: int = 504, test: int = 126, warmup: int = 252) -> None:
        self.strategy_factory = strategy_factory
        self.sizer = sizer
        self.risk_factory = risk_factory
        self.broker_factory = broker_factory
        self.train, self.test, self.warmup = train, test, warmup

    def _returns(self, data: dict, params: dict) -> np.ndarray:
        engine = BacktestEngine(self.strategy_factory(**params), self.sizer,
                                self.risk_factory(), self.broker_factory())
        res = engine.run(data)
        return metrics.returns_from_equity(res.equity_curve)

    def _slice(self, data: dict, a: int, b: int) -> dict:
        return {s: bars[max(0, a): b] for s, bars in data.items()}

    def run(self, data: dict, param_grid: list[dict]) -> WalkForwardResult:
        n = max(len(b) for b in data.values())
        windows = make_windows(n, self.train, self.test)
        oos: list[float] = []
        chosen: list[dict] = []
        trial_sharpes: list[float] = []
        for tr_s, tr_e, te_s, te_e in windows:
            # 1) sélection in-sample
            best, best_sr = param_grid[0], -1e9
            for params in param_grid:
                r = self._returns(self._slice(data, tr_s, tr_e), params)
                sr = float(r.mean() / r.std(ddof=1)) if r.size > 2 and r.std(ddof=1) > 0 else 0.0
                trial_sharpes.append(sr)
                if sr > best_sr:
                    best, best_sr = params, sr
            chosen.append(best)
            # 2) évaluation out-of-sample (avec warm-up, mesurée sur la fenêtre test)
            r_oos = self._returns(self._slice(data, te_s - self.warmup, te_e), best)
            oos.extend(r_oos[-self.test:].tolist() if r_oos.size >= self.test
                       else r_oos.tolist())
        oos_arr = np.asarray(oos, float)
        equity = (1 + oos_arr).cumprod() * 100 if oos_arr.size else np.array([100.0])
        return WalkForwardResult(
            oos_returns=oos, oos_metrics=metrics.summary(list(equity), []),
            chosen_params=chosen, n_trials=len(trial_sharpes),
            deflated_sharpe=deflated_sharpe_ratio(oos_arr, trial_sharpes)
                if oos_arr.size > 2 else 0.0,
            psr=probabilistic_sharpe_ratio(oos_arr) if oos_arr.size > 2 else 0.0)
