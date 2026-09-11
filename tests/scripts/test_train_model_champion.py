"""Un ré-entraînement qui échoue ne doit PAS laisser `models/` vide.

CE QUE CE TEST PROTÈGE. `train_model.py` supprimait les artefacts AVANT d'entraîner,
pour forcer un entraînement frais (sinon `artifact.load()` sert le cache et la commande
ne fait rien). Conséquence : un échantillon jugé insuffisant, ou n'importe quelle
exception pendant l'entraînement, laissait le dossier VIDE — plus de champion. Et
`cron_daily.sh` terminait la ligne par `|| true` : la panne ne laissait aucune trace.
L'API retombait alors sur un entraînement inline à chaque requête, c'est-à-dire la
situation exacte que le découplage entraînement/serving devait supprimer.

On teste les trois chemins : mise de côté, restauration, oubli.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "train_model_sous_test", RACINE / "scripts" / "train_model.py")
    mod = importlib.util.module_from_spec(spec)
    # `main()` n'est jamais appelée : on charge le module, on n'entraîne rien.
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def champion(tmp_path: Path) -> Path:
    (tmp_path / "ml_abc.pkl").write_bytes(b"modele")
    (tmp_path / "ml_abc.pkl.sha256").write_text("empreinte")
    return tmp_path


def test_l_empreinte_part_avec_le_modele(champion: Path):
    """`ml_*.pkl` ne matche pas `ml_*.pkl.sha256` : les deux doivent être pris."""
    mod = _module()
    noms = {p.name for p in mod._artefacts(champion)}
    assert noms == {"ml_abc.pkl", "ml_abc.pkl.sha256"}


def test_mettre_de_cote_retire_du_chemin_de_chargement(champion: Path):
    """Écarté, donc `artifact.load()` ne le voit plus — mais pas détruit."""
    mod = _module()
    abri = mod._mettre_de_cote(champion)
    assert list(champion.glob("ml_*")) == []          # invisible pour le chargeur
    assert (abri / "ml_abc.pkl").read_bytes() == b"modele"   # et toujours là


def test_un_echec_rend_le_champion(champion: Path):
    mod = _module()
    abri = mod._mettre_de_cote(champion)
    assert mod._restaurer(abri) == 2
    assert (champion / "ml_abc.pkl").read_bytes() == b"modele"
    assert (champion / "ml_abc.pkl.sha256").read_text() == "empreinte"
    assert not abri.exists()


def test_un_succes_oublie_l_ancien(champion: Path):
    mod = _module()
    abri = mod._mettre_de_cote(champion)
    (champion / "ml_neuf.pkl").write_bytes(b"remplacant")   # ce qu'écrit l'entraînement
    mod._oublier(abri)
    assert not abri.exists()
    assert {p.name for p in champion.glob("ml_*")} == {"ml_neuf.pkl"}


def test_un_run_tue_en_plein_vol_ne_perd_rien(champion: Path):
    """L'abri survit à un kill -9 ; le run suivant doit le vider avant de commencer."""
    mod = _module()
    mod._mettre_de_cote(champion)        # abri laissé en place, personne ne restaure
    assert mod._restaurer(champion / mod.ABRI) == 2
    assert (champion / "ml_abc.pkl").exists()


def test_sans_champion_il_n_y_a_rien_a_mettre_de_cote(tmp_path: Path):
    mod = _module()
    assert mod._mettre_de_cote(tmp_path) is None
    assert mod._restaurer(None) == 0
    mod._oublier(None)                              # ne doit pas lever
