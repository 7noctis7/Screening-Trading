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
