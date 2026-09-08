"""Le script de validation ne doit pas casser au moment où on en a besoin.

Il tourne UNE fois, un matin, sur la machine qui détient les bases — pas ici. Un
plantage à ce moment-là coûte la séance. On vérifie donc la PLOMBERIE de chaque étape
sur un panneau fabriqué : que les fonctions acceptent la forme attendue, produisent une
sortie, et ne modifient rien.

Le panneau est synthétique et le reste : il sert à exercer le code, pas à mesurer un
marché. C'est précisément la distinction que le garde-fou du script impose au vrai
lancement — et qui est testée en premier ici.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

_spec = importlib.util.spec_from_file_location(
    "valider_nouveautes", RACINE / "scripts" / "valider_nouveautes.py")
valider = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(valider)


@pytest.fixture
def panneau():
    g = np.random.default_rng(0)
    t, n = 420, 14
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {
        "open": close * (1 + g.normal(0, 0.002, (t, n))),
        "high": close * (1 + np.abs(g.normal(0, 0.006, (t, n)))),
        "low": close * (1 - np.abs(g.normal(0, 0.006, (t, n)))),
        "close": close,
        "volume": np.abs(g.lognormal(10, 0.5, (t, n))),
    }
    return champs, [f"ACT{i:02d}" for i in range(n)]


def test_le_script_refuse_de_mesurer_sur_du_synthetique() -> None:
    """LE garde-fou. Sans base réelle, il doit s'arrêter — pas produire des chiffres
    d'apparence sérieuse qui ne voudraient rien dire."""
    with pytest.raises(SystemExit) as e:
        valider.charger_panel(jours=60)
    assert "RÉELLE" in str(e.value)


def test_l_etape_anomalies_tourne_et_ne_modifie_rien(panneau, capsys) -> None:
    champs, symboles = panneau
    avant = {k: v.copy() for k, v in champs.items()}
    valider.etape_anomalies(champs, symboles)
    assert all(np.array_equal(avant[k], champs[k]) for k in champs), (
        "l'étape a modifié le panneau : un audit ne corrige jamais en silence"
    )
    assert "ANOMALIES CROISÉES" in capsys.readouterr().out


def test_l_etape_cvar_compare_bien_les_allocateurs(panneau, capsys) -> None:
    valider.etape_cvar(*panneau)
    sortie = capsys.readouterr().out
    for attendu in ("Mean-CVaR", "min-variance", "risk parity", "HRP", "équipondéré"):
        assert attendu in sortie, f"« {attendu} » absent de la comparaison"


def test_l_etape_generateur_n_ecrit_pas_sans_appliquer(panneau, capsys) -> None:
    """Par défaut le registre RÉEL ne doit pas bouger : sinon lancer le script « pour
    voir » gonflerait le compte d'essais, donc resserrerait la déflation de tous les
    travaux passés."""
    from packages.research.ledger import trial_count
    avant = trial_count()
    valider.etape_generateur(panneau[0], appliquer=False)
    assert trial_count() == avant, "le registre réel a été modifié sans --appliquer"
    assert "TEMPORAIRE" in capsys.readouterr().out


def test_l_etape_explicabilite_tourne(panneau, capsys) -> None:
    valider.etape_explication(*panneau)
    assert "EXPLICABILITÉ" in capsys.readouterr().out


def test_une_etape_en_echec_n_emporte_pas_les_suivantes(monkeypatch, capsys) -> None:
    """LE défaut vu en production le 08/09 : scikit-learn absent du VPS a fait planter
    l'étape 2, qui a emporté les étapes 3 et 4. Or l'ordre du script sert justement à
    obtenir les mesures SANS RISQUE d'abord — les perdre à cause d'une dépendance
    optionnelle manquante plus loin est l'inverse du but recherché."""
    g = np.random.default_rng(1)
    t, n = 300, 10
    close = 100.0 * np.exp(np.cumsum(g.normal(0, 0.015, (t, n)), axis=0))
    champs = {c: close.copy() for c in ("open", "high", "low", "close", "volume")}

    noms = [f"A{i}" for i in range(n)]
    monkeypatch.setattr(valider, "charger_panel",
                        lambda jours=1500: (champs, noms, "réel"))

    def _explose(*a, **k):
        raise ModuleNotFoundError("No module named 'sklearn'", name="sklearn")

    monkeypatch.setattr(valider, "etape_explication", _explose)
    monkeypatch.setattr(sys, "argv", ["valider_nouveautes.py"])

    assert valider.main() == 0, "le script s'arrête au lieu de continuer"
    sortie = capsys.readouterr().out
    assert "sklearn" in sortie and "ignorée" in sortie
    assert "MEAN-CVaR" in sortie, "l'étape 3 n'a pas tourné après l'échec de l'étape 2"
    assert "GÉNÉRATEUR" in sortie, "l'étape 4 n'a pas tourné"
    assert "ÉTAPES NON ABOUTIES" in sortie, "l'échec n'est pas récapitulé à la fin"


def test_une_serie_figee_annonce_sa_vraie_duree() -> None:
    """Vu sur données réelles : une série figée annonçait « 5 séances » quelle que soit
    sa durée, parce que l'entrée était publiée au moment où le compteur ATTEIGNAIT le
    seuil. Le chiffre était faux dans le sens qui minimise le problème."""
    from packages.storage.anomalies_panel import series_figees
    g = np.random.default_rng(2)
    p = 100.0 * np.exp(np.cumsum(g.normal(0, 0.01, (120, 6)), axis=0))
    p[40:100, 2] = p[39, 2]                     # 60 séances figées
    trouve = [f for f in series_figees(p) if f["actif_index"] == 2]
    assert trouve, "série figée non détectée"
    assert trouve[0]["jours"] >= 55, (
        f"durée annoncée {trouve[0]['jours']} pour 60 séances figées : le chiffre "
        "minimise le problème."
    )
