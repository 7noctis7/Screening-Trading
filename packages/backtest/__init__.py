"""packages.backtest — moteur event-driven (parité backtest↔live via mêmes interfaces)."""
from packages.backtest.engine import BacktestEngine, BacktestResult
from packages.backtest.statistics import deflated_sharpe_ratio, probabilistic_sharpe_ratio
from packages.backtest.walkforward import WalkForwardRunner, make_windows

__all__ = ["BacktestEngine", "BacktestResult", "WalkForwardRunner",
           "make_windows", "deflated_sharpe_ratio", "probabilistic_sharpe_ratio"]
