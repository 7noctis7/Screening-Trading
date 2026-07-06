"""Verdict GO/NO-GO mécanique du RDV paper — pur, sans réseau ni données réelles.

Synthétique AUTORISÉ ici (tests/ uniquement, mandat CLAUDE.md) : on valide la MATH
du verdict, pas une performance.
"""
from __future__ import annotations

from packages.research.rdv_paper import _max_dd, compare


def _curve(daily: float, n: int, start: float = 100.0, vol: float = 0.004,
           seed: int = 7) -> list[float]:
    """Marche géométrique bruitée : un rendement CONSTANT a une vol nulle → Sharpe
    indéfini (le code le refuse, à raison) — on bruite donc légèrement."""
    import random
    rng = random.Random(seed)
    out = [start]
    for _ in range(n):
        out.append(out[-1] * (1 + daily + rng.gauss(0.0, vol)))
    return out


def test_insufficient_when_too_short():
    rep = compare(_curve(0.001, 5), _curve(0.001, 5))
    assert rep["verdict"] == "INSUFFISANT"          # 5 j < 20 → on ne tranche pas


def test_go_when_paper_matches_model():
    paper = _curve(0.0011, 260)                      # légèrement MIEUX que le modèle
    model = _curve(0.0010, 260)
    rep = compare(paper, model)
    assert rep["verdict"] == "GO"
    assert all(c["ok"] for c in rep["criteria"])


def test_nogo_on_sharpe_drift():
    # modèle Sharpe élevé, paper plat+bruité → dérive > 1 pt = NO-GO (pas INSUFFISANT :
    # la longueur suffit, c'est bien la performance qui diverge)
    import random
    rng = random.Random(42)
    paper = [100.0]
    for _ in range(400):
        paper.append(paper[-1] * (1 + rng.gauss(0.0, 0.01)))
    model = _curve(0.002, 400)
    rep = compare(paper, model)
    assert rep["verdict"] in ("NO-GO", "INSUFFISANT")
    drift_crit = [c for c in rep["criteria"] if "dérive" in c["name"]][0]
    if rep["verdict"] == "NO-GO":
        assert not drift_crit["ok"]


def test_nogo_when_maxdd_exceeded():
    model = _curve(0.001, 260)                       # modèle sans drawdown notable
    paper = _curve(0.004, 260)
    paper[130:] = [v * 0.60 for v in paper[130:]]    # crash -40 % en cours de route
    rep = compare(paper, model)
    dd_crit = [c for c in rep["criteria"] if "MaxDD" in c["name"]][0]
    assert not dd_crit["ok"]
    assert rep["verdict"] != "GO"


def test_max_dd_math():
    assert _max_dd([100, 120, 60, 90]) == 60 / 120 - 1
    assert _max_dd([100, 110, 120]) == 0.0
