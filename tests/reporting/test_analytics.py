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
    assert 0.0 <= at["alpha_share"] <= 1.0
    # verdict honnête : significativité gatée + flags exposés
    assert isinstance(at["verdict"], str) and at["verdict"]
    assert "alpha_tstat" in at and isinstance(at["alpha_significant"], bool)
    assert isinstance(at["underperforms_benchmark"], bool)
    # un alpha non significatif ne doit JAMAIS être étiqueté « significatif »
    if not at["alpha_significant"] or at["underperforms_benchmark"]:
        assert "significatif)" not in at["verdict"]


def test_attribution_unavailable_without_benchmark():
    at = PerformanceAnalytics.from_curves(_curve()).attribution()
    assert at["available"] is False and at["motif"] == "aucun benchmark"


# ── appariement par date (cinquième occurrence de l'empilement positionnel, 04/09) ──

def _calendrier(n: int) -> list[str]:
    """n dates ouvrées consécutives, format ISO."""
    from datetime import date, timedelta
    out, d = [], date(2020, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _trous(courbe, dates, indices):
    """Retire des séances À L'INTÉRIEUR (un jour férié propre à ce calendrier).

    Retirer des points au DÉBUT ne prouverait rien : les deux séries finissant le
    même jour, l'empilement par la fin retomberait sur ses pieds. Ce sont les trous
    intérieurs qui décalent tout ce qui suit — exactement ce que fait un calendrier
    d'indices face à un calendrier d'univers négociable."""
    ex = set(indices)
    garde = [i for i in range(len(courbe)) if i not in ex]
    return [courbe[i] for i in garde], [dates[i] for i in garde]


def _marche(n=400, seed=7):
    import random
    r = random.Random(seed); v = [100.0]
    for _ in range(n - 1):
        v.append(v[-1] * (1 + 0.0004 + r.uniform(-0.012, 0.012)))
    return v


def test_appariement_par_date_retrouve_le_beta_que_la_position_detruit():
    """Deux fois LA MÊME courbe, deux calendriers : bêta 1 par date, ~0 par position."""
    dates = _calendrier(400)
    marche = _marche(400)
    # le benchmark ne cote pas ces séances-là (calendrier des indices)
    bench, bdates = _trous(marche, dates, [50, 120, 121, 260, 330])

    par_date = PerformanceAnalytics.from_curves(marche, bench, dates=dates,
                                                benchmark_dates=bdates).metrics()
    par_position = PerformanceAnalytics.from_curves(marche, bench).metrics()

    assert abs(par_date.beta - 1.0) < 1e-6 and abs(par_date.corr - 1.0) < 1e-6
    # le bug : la même donnée, appariée par la fin, ne ressemble plus à rien
    assert abs(par_position.corr) < 0.3
    assert abs(par_position.beta) < 0.3


def test_alignement_est_publie_dans_l_attribution():
    dates = _calendrier(400)
    marche = _marche(400)
    bench, bdates = _trous(marche, dates, [50, 120, 260])
    at = PerformanceAnalytics.from_curves(marche, bench, dates=dates,
                                          benchmark_dates=bdates).attribution()
    assert at["alignement"] == "date" and at["n_observations"] == len(bdates) - 1
    sans = PerformanceAnalytics.from_curves(marche, bench).attribution()
    assert sans["alignement"] == "position"


def test_contribution_alpha_ne_gonfle_plus_par_faux_beta():
    """Portefeuille = 1,2 × marché (levier pur, alpha nul) : la contribution alpha doit
    rester petite. Par position elle explose — c'est le « 1072 % » du dashboard."""
    dates = _calendrier(400)
    marche = _marche(400)
    port = [100.0]
    for i in range(1, len(marche)):
        port.append(port[-1] * (1 + 1.2 * (marche[i] / marche[i - 1] - 1.0)))
    bench, bdates = _trous(marche, dates, [40, 41, 150, 300, 301])

    at = PerformanceAnalytics.from_curves(port, bench, dates=dates,
                                          benchmark_dates=bdates).attribution()
    assert abs(at["beta"] - 1.2) < 0.05
    assert at["alpha_share"] < 0.5 and at["verdict"] == "bêta dominant (marché)"

    faux = PerformanceAnalytics.from_curves(port, bench).attribution()
    # comparaison, pas seuil : le positionnel détruit la majorité du bêta réel…
    assert abs(faux["beta"]) < 0.5 * at["beta"]
    # …et le rendement bascule du côté « alpha »
    assert faux["alpha_share"] > at["alpha_share"]


def test_intersection_vide_refuse_de_conclure():
    dates = _calendrier(300)
    autres = _calendrier(300)[:0] + [f"1999-01-{d:02d}" for d in range(1, 29)] * 11
    marche = _marche(300)
    at = PerformanceAnalytics.from_curves(marche, marche[:len(autres)], dates=dates,
                                          benchmark_dates=autres[:len(autres)]).attribution()
    assert at["available"] is False and "séances communes" in at["motif"]
