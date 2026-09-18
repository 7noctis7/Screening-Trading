"""Les frais réels du courtier, conservés jour après jour.

POURQUOI CE STORE EXISTE. Un fill porte une quantité et un prix, jamais son coût de
transaction : chez Alpaca les frais sont des ACTIVITÉS séparées. Un registre reconstruit
depuis les seuls ordres est donc BRUT, et l'identité du compte y perd exactement leur
montant — 810,30 $ mesurés le 18/09 sur 100 973,45 $.
"""

from __future__ import annotations

import packages.execution.frais_store as fs


def _isole(tmp_path, monkeypatch):
    """Le store écrit dans `.cache/` ; un test qui y touche pollue la machine."""
    monkeypatch.setattr(fs, "_F", tmp_path / "frais.json")
    return fs


def test_on_lit_le_DERNIER_cumul_jamais_la_somme_des_points(tmp_path, monkeypatch):
    """Chaque point est déjà un cumul depuis l'ouverture du compte. Les additionner
    multiplierait les frais par le nombre de passages — le même piège que la confusion
    « variation » / « niveau » qui a déjà coûté un panneau entier à ce dépôt."""
    m = _isole(tmp_path, monkeypatch)
    m.record({"disponible": True, "total_usd": -700.0, "par_type": {"CFEE": -700.0}},
             today="2026-09-17")
    m.record({"disponible": True, "total_usd": -810.3, "par_type": {"CFEE": -810.3}},
             today="2026-09-18")
    assert m.dernier()["total_usd"] == -810.3
    assert len(m._load()) == 2, "les points restent, ils ne s'additionnent pas"


def test_un_releve_INDISPONIBLE_n_efface_rien(tmp_path, monkeypatch):
    """Une panne d'API d'une journée effacerait sinon le cumul déjà connu — et un coût
    qui disparaît des comptes est pire qu'un coût qu'on n'a pas encore lu."""
    m = _isole(tmp_path, monkeypatch)
    m.record({"disponible": True, "total_usd": -810.3}, today="2026-09-18")
    m.record({"disponible": False, "motif": "API muette"}, today="2026-09-19")
    assert m.dernier()["total_usd"] == -810.3


def test_deux_releves_le_MEME_jour_ne_font_qu_un_point(tmp_path, monkeypatch):
    """Le snapshot se construit plusieurs fois par jour ; empiler un point par build
    gonflerait l'historique sans rien ajouter."""
    m = _isole(tmp_path, monkeypatch)
    m.record({"disponible": True, "total_usd": -800.0}, today="2026-09-18")
    m.record({"disponible": True, "total_usd": -810.3}, today="2026-09-18")
    assert len(m._load()) == 1 and m.dernier()["total_usd"] == -810.3


def test_sans_aucun_releve_on_DIT_qu_on_ne_sait_pas(tmp_path, monkeypatch):
    """`0,0` affirmerait qu'aucun frais n'a été prélevé. C'est faux de 810,30 $."""
    m = _isole(tmp_path, monkeypatch)
    d = m.dernier()
    assert d["disponible"] is False and d["motif"]
