"""Un lot rattrapé doit rentrer dans la calibration s'il a retrouvé sa décision.

`completer_ouvertures` reconstitue une ouverture depuis les seuls ordres du courtier.
Le courtier ne connaît ni le rang du titre, ni le régime, ni le prix de décision :
jusqu'au
22/09 le lot rattrapé était donc écrit `legacy=1`, aveugle, hors de l'échantillon de
calibration ML — tombé à QUATRE lots ce jour-là.

`decisions_store` conserve ce que le run SAVAIT en envoyant l'ordre. Ces tests
vérifient le
câblage des deux bouts : le run dépose, le rattrapage rattache — et `legacy` répond
enfin à
sa propre question (« ce lot porte-t-il les features de la décision ? ») plutôt qu'à
celle
du chemin d'écriture.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

from packages.execution.decisions_store import enregistrer

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _module(nom: str, chemin: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def magasin(tmp_path, monkeypatch):
    """Le magasin sur disque, isolé du vrai `.cache`."""
    import packages.execution.decisions_store as ds
    f = tmp_path / "decisions.json"
    monkeypatch.setattr(ds, "_F", f)
    return f


@pytest.fixture
def co():
    return _module("_co_ctx", "scripts/completer_ouvertures.py")


def _lot(sym="TTEK", date="2026-09-22T19:08:00Z", qty=94.614, prix=35.70):
    return {"symbole": sym, "date": date, "qty": qty, "prix": prix, "venue": "Alpaca"}


def _decision(sym="TTEK"):
    return {"symbol": sym, "venue": "Alpaca", "regime": "expansion/risk_on",
            "features": {"rank_score": 1.5, "target_weight": 0.02}}


# --- le rattrapage rattache ------------------------------------------------

def test_un_lot_rattrape_retrouve_ses_features_et_son_regime(co, magasin):
    enregistrer([_decision()], "2026-09-22", fichier=magasin)
    rec = co._record(_lot())
    assert rec.features_snapshot == {"rank_score": 1.5, "target_weight": 0.02}
    assert rec.regime == "expansion/risk_on"


def test_le_lot_DIT_de_quand_vient_le_contexte_qu_il_porte(co, magasin):
    """Un rattachement muet serait aussi opaque qu'une absence."""
    enregistrer([_decision()], "2026-09-22", fichier=magasin)
    assert "contexte de décision du 2026-09-22" in co._record(_lot()).entry_reason


def test_sans_decision_conservee_le_lot_reste_aveugle_et_ne_ment_pas(co, magasin):
    rec = co._record(_lot())
    assert rec.features_snapshot == {} and rec.regime is None
    assert "contexte de décision" not in rec.entry_reason


def test_une_decision_d_un_AUTRE_symbole_ne_contamine_pas(co, magasin):
    enregistrer([_decision(sym="DUOL")], "2026-09-22", fichier=magasin)
    assert co._record(_lot(sym="TTEK")).features_snapshot == {}


# --- `legacy` répond à SA question ------------------------------------------

class _Journal:
    def __init__(self):
        self.ecrits = []

    def append(self, rec, *, legacy=False):
        self.ecrits.append((rec.id, legacy, bool(rec.features_snapshot)))


def test_le_lot_qui_a_retrouve_sa_decision_vaut_legacy_ZERO(co, magasin, capsys):
    """ADR-0188 : le PRÉFIXE dit d'où vient l'écriture, `legacy` dit ce que
    l'enregistrement PORTE. Les deux ne se déduisent pas l'un de l'autre."""
    enregistrer([_decision()], "2026-09-22", fichier=magasin)
    j = _Journal()
    co._ecrire(j, [_lot()])
    (ident, legacy, avec_features) = j.ecrits[0]
    assert ident.startswith("C-")       # provenance de l'écriture : reconstituée
    assert legacy is False and avec_features    # …mais elle PORTE la décision
    assert "1 AVEC le contexte de décision retrouvé" in capsys.readouterr().out


def test_le_lot_sans_decision_reste_legacy_UN_et_c_est_DIT(co, magasin, capsys):
    j = _Journal()
    co._ecrire(j, [_lot()])
    assert j.ecrits[0][1] is True
    sortie = capsys.readouterr().out
    assert "0 AVEC le contexte" in sortie and "1 sans (legacy=1)" in sortie
    assert "decisions_store" in sortie      # le motif, pas seulement le compte


def test_les_deux_cas_coexistent_dans_un_meme_passage(co, magasin, capsys):
    enregistrer([_decision(sym="TTEK")], "2026-09-22", fichier=magasin)
    j = _Journal()
    co._ecrire(j, [_lot(sym="TTEK"), _lot(sym="DUOL", prix=147.93)])
    assert sorted(l for _i, l, _f in j.ecrits) == [False, True]
    assert "1 AVEC" in capsys.readouterr().out


# --- le run dépose, et le dit s'il échoue -----------------------------------

def test_le_run_depose_les_decisions_du_jour(magasin):
    from packages.execution.decisions_store import retrouver
    rl = _module("_rl_ctx", "scripts/run_live.py")
    rl._garder_les_decisions([_decision()], "2026-09-22")
    assert retrouver("TTEK", "Alpaca", "2026-09-22", fichier=magasin) is not None


def test_un_depot_qui_echoue_est_ANNONCE(monkeypatch, capsys):
    """Un magasin muet ferait croire à une mémoire alimentée alors qu'elle est vide,
    et le manque ne se découvrirait qu'au moment d'entraîner."""
    rl = _module("_rl_ctx2", "scripts/run_live.py")
    import packages.execution.decisions_store as ds
    monkeypatch.setattr(ds, "enregistrer", lambda *a, **k: False)
    rl._garder_les_decisions([_decision()], "2026-09-22")
    assert "NON enregistrées" in capsys.readouterr().out


def test_un_depot_qui_LEVE_ne_casse_pas_le_run(monkeypatch, capsys):
    rl = _module("_rl_ctx3", "scripts/run_live.py")
    import packages.execution.decisions_store as ds

    def boom(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr(ds, "enregistrer", boom)
    rl._garder_les_decisions([_decision()], "2026-09-22")
    assert "non enregistrées" in capsys.readouterr().out
