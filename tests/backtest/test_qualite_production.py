"""QML-022 — des fondamentaux FACTICES ne doivent jamais choisir l'univers de production.

`_fundamentals_section` retombe sur `SyntheticFundamentalsProvider` quand moins de cinq titres
répondent (réseau coupé, quota d'API). Le score était transmis tel quel à la sélection top-12
de `make live`, et le diagnostic affichait « 30 titres scorés → top-12 par qualité » : des
ordres paper décidés sur des bilans inventés, sans une ligne pour le dire.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from packages.core.models import Bar


def _section(source: str, n: int = 30) -> dict:
    return {"available": True, "source": source,
            "rows": [{"symbol": f"T{k:02d}", "combined_score": float(k)} for k in range(n)]}


def test_un_score_synthetique_n_est_jamais_transmis():
    from packages.backtest.preset_weights import qualite_de_production
    assert qualite_de_production(_section("synthétique (repli — hors-ligne)")) == {}
    assert qualite_de_production({"available": False}) == {}
    assert qualite_de_production({}) == {}


def test_un_score_reel_est_transmis():
    from packages.backtest.preset_weights import qualite_de_production
    q = qualite_de_production(_section("réel multi-source : yfinance 30"))
    assert len(q) == 30 and q["T29"] == 29.0


def _panel(n: int = 30, jours: int = 320) -> dict:
    rng = np.random.default_rng(1)
    d0 = datetime(2020, 1, 1, tzinfo=UTC)
    return {f"T{k:02d}": [Bar(f"T{k:02d}", "1d", d0 + timedelta(days=i), p, p, p, p, 1e6)
                          for i, p in enumerate(40 * np.exp(np.cumsum(
                              rng.normal(0.0005, 0.01, jours))))]
            for k in range(n)}


def _etape(diag, nom):
    return [e["detail"] for e in diag.as_dict()["etapes"] if e["etape"] == nom]


def test_couverture_partielle_repli_momentum():
    """Huit titres scorés sur trente : l'univers ne se réduit pas à ceux que l'API a servis."""
    from packages.backtest.preset_weights import preset_latest_weights_explique
    q = {f"T{k:02d}": float(k) for k in range(8)}
    _, d = preset_latest_weights_explique(_panel(), q, top_k=12)
    assert "MOMENTUM" in _etape(d, "score qualité")[0]


def test_la_selection_qualite_se_declare_non_calibree():
    from packages.backtest.preset_weights import preset_latest_weights_explique
    q = {f"T{k:02d}": float(k) for k in range(30)}
    _, d = preset_latest_weights_explique(_panel(), q, top_k=12)
    assert "UNCALIBRATED" in _etape(d, "score qualité")[0]
