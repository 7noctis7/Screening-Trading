"""Correctifs vérifiés de l'audit du 17/11 : chacun reproduit le défaut constaté."""
import os
import stat

import pytest


def test_le_plafond_de_ligne_tient_malgre_la_conviction():
    """`final_weight` multipliait APRÈS le plafond : 0,30 pour un plafond de 0,20."""
    from packages.portfolio.sizing.vol_target import final_weight
    w = final_weight(asset_vol=0.10, p_calibrated=1.0, dd_mult=1.0, corr_mult=1.0)
    assert w == pytest.approx(0.20)
    assert final_weight(0.10, 1.0, 1.0, 1.5) == pytest.approx(0.20)   # multiplicateur > 1
    assert final_weight(0.10, 1.0, 0.5, 1.0) == pytest.approx(0.10)   # le risque réduit


def test_le_cac_40_n_a_qu_une_definition_l_indice_avant_les_trackers():
    """Déclaré deux fois : la seconde clé écrasait la première, et deux alias de l'indice
    n'étaient jamais essayés. Le dictionnaire garde la dernière ; on vérifie la SOURCE."""
    from pathlib import Path

    from packages.portfolio.comparaison_benchmark import REFERENCES
    src = Path("packages/portfolio/comparaison_benchmark.py").read_text(encoding="utf-8")
    assert src.count('"CAC 40":') == 1
    assert REFERENCES["CAC 40"] == ["^FCHI", "PX1", "CAC.PA", "CAC", "EWQ"]


@pytest.mark.skipif(os.name != "posix", reason="permissions POSIX")
def test_un_pickle_ecrit_par_le_depot_n_est_lisible_que_par_son_proprietaire(tmp_path):
    """Avec l'umask d'Ubuntu (002), les artefacts naissaient en 664 et `load` avertissait
    à chaque lecture. Écrits en 600 — y compris quand le fichier existait déjà en 664."""
    from packages.common import safe_pickle
    p = tmp_path / "a.pkl"
    p.write_bytes(b"")
    os.chmod(p, 0o664)
    ancien = os.umask(0o002)
    try:
        safe_pickle.dump({"x": 1}, p)
    finally:
        os.umask(ancien)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert safe_pickle.load(p) == {"x": 1}


def test_le_jeton_du_webhook_est_compare_a_temps_constant(monkeypatch):
    """`==` s'arrête au premier caractère différent ; `hmac.compare_digest` non."""
    from types import SimpleNamespace

    import apps.api.main as M
    monkeypatch.setattr(M, "_WEBHOOK_TOKEN", "secret-du-test")
    vus = []
    import hmac
    vrai = hmac.compare_digest
    monkeypatch.setattr(hmac, "compare_digest", lambda a, b: vus.append(1) or vrai(a, b))
    req = SimpleNamespace(headers={"X-Webhook-Token": "secret-du-test"}, client=None)
    assert M._webhook_authorized(req) is True and vus
    assert M._webhook_authorized(SimpleNamespace(headers={}, client=None)) is False
    hostile = SimpleNamespace(headers={"X-Webhook-Token": "sécret-\u00e9"}, client=None)
    assert M._webhook_authorized(hostile) is False      # refus, pas une TypeError (500)
