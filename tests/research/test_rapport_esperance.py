"""Rapport d'une page : bout en bout sur le vrai rejeu, et verdict mécanique."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from packages.research.rapport_esperance import NM, markdown, verdict
from tests.backtest.test_preset_diag import Bar

T0 = datetime(2019, 1, 1, tzinfo=UTC)


def _univers(n=24, barres=700, graine=0) -> dict:
    rng = np.random.default_rng(graine)
    out = {}
    for k in range(n + 1):
        nom = "QQQ" if k == n else f"S{k:02d}"
        px = 100 * np.cumprod(1 + rng.normal(0.0004, 0.015, barres))
        out[nom] = [Bar(T0 + timedelta(days=j), *(4 * [float(px[j])]), 2e6)
                    for j in range(barres)]
    return out


def test_page_vide_dit_non_mesure_partout():
    page = markdown({})
    assert page.count(NM) >= 6 and "Verdict" in page
    assert len(page.splitlines()) < 40                    # une page


@pytest.mark.parametrize("q1, q2, etabli", [
    ({"available": True, "ic95": [0.001, 0.003]},
     {"available": True, "ic95": [0.01, 0.03], "dsr_ecart": 0.97}, True),
    ({"available": True, "ic95": [-0.001, 0.003]},
     {"available": True, "ic95": [0.01, 0.03], "dsr_ecart": 0.97}, False),
    ({"available": True, "ic95": [0.001, 0.003]},
     {"available": True, "ic95": [0.01, 0.03], "dsr_ecart": 0.80}, False),  # déflaté
    ({"available": False}, {"available": False}, False),
])
def test_verdict_exige_les_deux_et_la_deflation(q1, q2, etabli):
    v = verdict(q1, q2)
    assert v["etabli"] is etabli
    assert ("NON établi" in v["texte"]) is (not etabli)


def test_bout_en_bout_sur_le_rejeu_de_production(monkeypatch, tmp_path):
    from packages.research import ledger
    from scripts import rapport_esperance as script
    chemin = tmp_path / "h.jsonl"
    monkeypatch.setattr(ledger.append_record, "__defaults__", (chemin,))
    monkeypatch.setenv("QUANT_CORE_SPEC", "qqq:0.5")
    data = _univers()
    acmap = {s: ("etf" if s == "QQQ" else "equity") for s in data}
    r = script._calculer(data, acmap, "synthetic", pas=20)
    assert r is not None and r["meta"]["allers_retours"] > 0
    assert r["q2_dd"]["available"] and 0 < r["q2_dd"]["alpha_qqq"] <= 1
    assert r["q3"]["available"] and r["q3"]["n_eff_median"] >= 1
    assert {x["horizon"] for x in r["ic"]["resultats"]} == {1, 5, 10, 20, 60}
    assert not chemin.exists()                       # synthétique : rien au registre
    page = markdown(r)
    assert "Verdict" in page and "livre − QQQ+cash" in page
    assert "frais seuls, sans impact" in page and "participation q / ADV" in page
    f, y10 = r["q1_frais"], r["q1_y10"]
    assert f["esperance_ponderee"] >= y10["esperance_ponderee"]   # l'impact coûte
