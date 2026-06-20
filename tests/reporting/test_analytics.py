"""Reporting QuantStats (calculs purs + sorties HTML/Markdown)."""
import math
from packages.reporting.analytics import PerformanceAnalytics


def _curve(n=300, drift=0.0006, seed=1):
    import random
    r = random.Random(seed); v = [100.0]
    for _ in range(n):
        v.append(v[-1] * (1 + drift + r.uniform(-0.01, 0.01)))
    return v


def test_metrics_pure():
    pa = PerformanceAnalytics.from_curves(_curve(), _curve(seed=2))
    m = pa.metrics()
    assert -1.0 <= m.max_drawdown <= 0.0
    assert m.n_days > 0 and m.beta is not None and 0.0 <= (m.corr or 0) <= 1.0
    assert m.sortino is not None and m.calmar is not None


def test_markdown_summary_front_matter():
    md = PerformanceAnalytics.from_curves(_curve(), _curve(seed=3)).to_markdown_summary("X")
    assert md.startswith("---") and "type: performance_report" in md
    assert "Sortino" in md and "Alpha annualisé" in md and "Max Drawdown" in md


def test_html_snippet():
    html = PerformanceAnalytics.from_curves(_curve()).to_html_snippet("X")
    assert html.startswith("<table") and "Sharpe" in html and "Max Drawdown" in html


def test_empty_is_safe():
    m = PerformanceAnalytics([], []).metrics()
    assert m.n_days == 0 and m.sharpe == 0


def test_attribution_decomposes_alpha_beta():
    at = PerformanceAnalytics.from_curves(_curve(), _curve(seed=2)).attribution()
    assert at["available"] is True
    # cohérence : contribution bêta + alpha = rendement portefeuille
    assert abs((at["beta_contribution"] + at["alpha_contribution"]) - at["portfolio_return"]) < 1e-6
    assert 0.0 <= at["alpha_share"] <= 1.0 and at["verdict"] in (
        "alpha dominant (compétence)", "bêta dominant (marché)")


def test_attribution_unavailable_without_benchmark():
    assert PerformanceAnalytics.from_curves(_curve()).attribution() == {"available": False}
