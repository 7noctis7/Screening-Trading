"""Le verrou doit être résolu SUR la machine qui entraîne — et on le vérifie.

CE QUI S'EST PASSÉ (18/09). `make verrou-regen` dit depuis toujours « à lancer sur la
machine qui entraîne » et ne vérifiait rien. Lancé sur le Mac (Darwin/arm64, Python
3.12), il a produit un `constraints.txt` de 140 paquets qui a remplacé celui du VPS
(Linux/x86_64, Python 3.14, 159 paquets) : plus de roues CUDA, épinglages résolus pour
une autre mineure de Python.

LE PIRE : `make verrou` restait VERT des deux côtés, parce que les sept bibliothèques
d'entraînement étaient épinglées ici comme là-bas. Rien n'invitait à regarder. Un
avertissement écrit dans une phrase d'aide ne s'exécute pas ; une garde, si.

CE QUE CES TESTS TIENNENT : la comparaison porte sur ce qui change la résolution (OS,
architecture, mineure de Python) et pas sur ce qui ne la change pas ; une absence de
trace donne INDÉTERMINÉ et jamais « compatible » ; et la garde tourne AVANT la
compilation du verrou, sinon elle arrive après les dégâts.
"""

from __future__ import annotations

import pathlib

from packages.mlops.environnement import machine_compatible, machine_de_reference

VPS = {"os": "Linux 7.0.0-28-generic", "machine": "x86_64", "python": "3.14.4"}
MAC = {"os": "Darwin 25.2.0", "machine": "arm64", "python": "3.12.12"}


def test_la_MEME_machine_passe():
    ok, motif = machine_compatible(VPS, VPS)
    assert ok is True
    assert "x86_64" in motif and "Linux" in motif


def test_le_CAS_REEL_du_18_09_est_refuse():
    """Mac contre VPS : trois écarts d'un coup, et chacun suffit à lui seul."""
    ok, motif = machine_compatible(VPS, MAC)
    assert ok is False
    assert "OS Linux ≠ Darwin" in motif
    assert "architecture x86_64 ≠ arm64" in motif
    assert "Python 3.14 ≠ 3.12" in motif


def test_le_NOYAU_ne_compte_pas_le_CORRECTIF_non_plus():
    """Un noyau mis à jour ou un Python 3.14.4 → 3.14.7 ne changent pas la résolution.
    Refuser là-dessus rendrait la garde insupportable, donc contournée, donc inutile."""
    ok, _ = machine_compatible(
        VPS, {"os": "Linux 7.0.0-31-generic", "machine": "x86_64", "python": "3.14.7"})
    assert ok is True


def test_la_MINEURE_de_Python_compte():
    """Elle change les roues disponibles et les bornes de compatibilité : c'est
    exactement ce qui sépare le verrou du Mac de celui du VPS."""
    ok, motif = machine_compatible(
        VPS, {"os": "Linux 7.0.0-28-generic", "machine": "x86_64", "python": "3.12.12"})
    assert ok is False
    assert "Python" in motif


def test_SANS_TRACE_le_verdict_est_INDETERMINE_jamais_compatible():
    """« On ne sait pas » et « c'est la bonne machine » ne sont pas la même chose. Les
    confondre ferait passer la garde pour un feu vert le jour où le registre est vide —
    c'est-à-dire précisément avant le premier entraînement."""
    verdict, motif = machine_compatible(None)
    assert verdict is None, "ni True ni False : indéterminé"
    assert "absence" in motif


def test_la_reference_vient_du_REGISTRE_pas_d_une_constante(tmp_path, monkeypatch):
    """Une constante écrite à la main se désynchronise en silence ; une trace
    d'entraînement dit ce qui s'est réellement passé."""
    import json

    monkeypatch.setenv("QUANT_MODELS_DIR", str(tmp_path))
    (tmp_path / "registre.json").write_text(json.dumps({
        "version_format": 1,
        "entrees": {
            "m-20260101-aaa": {"statut": "archived", "chemin": "", "historique": [],
                               "manifest": {"env": MAC}},
            "m-20260916-bbb": {"statut": "rejected", "chemin": "", "historique": [],
                               "manifest": {"env": VPS}},
        }}), encoding="utf-8")

    ref = machine_de_reference()
    assert ref is not None
    assert ref["machine"] == "x86_64", "la DERNIÈRE version fait référence"
    assert ref["version"] == "m-20260916-bbb"


def test_la_garde_tourne_AVANT_la_compilation_du_verrou():
    """Après, elle arriverait une fois `constraints.txt` déjà écrasé."""
    mk = (pathlib.Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8")
    recette = mk.split("\nverrou-regen:", 1)[1].split("\nsetup:", 1)[0]
    lignes = [x.strip() for x in recette.splitlines() if x.startswith("\t")
              and not x.strip().startswith(("@#", "@echo"))]
    garde = next(i for i, x in enumerate(lignes) if "verrou_regen_garde" in x)
    compile_ = next(i for i, x in enumerate(lignes) if "pip compile" in x)
    assert garde < compile_
