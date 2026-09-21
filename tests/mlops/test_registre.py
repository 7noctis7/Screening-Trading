"""Le registre de modèles — persistance, invariants, et rollback RÉEL.

Le défaut mesuré le 16/09 : `governance.ModelRegistry` vit en mémoire et `artifact.py` est
un cache TTL. Aucun des deux ne garde le prédécesseur d'un modèle, donc le rollback n'était
pas « non implémenté » — il était IMPOSSIBLE.
"""

import json

import pytest

from packages.mlops.manifest import Manifest
from packages.mlops.registre import (
    ARCHIVE,
    CANDIDAT,
    PRODUCTION,
    REJETE,
    Registre,
)


def _artefact(tmp_path, nom: str, contenu: bytes = b"modele") -> str:
    p = tmp_path / nom
    p.write_bytes(contenu)
    return str(p)


def _manifest(tmp_path, chemin: str, version: str) -> Manifest:
    from packages.mlops.empreinte import sha256_fichier
    m = Manifest.creer("swing_ml", "EXP-TEST", dataset_hash="d1", feature_version="v1",
                       seed=7, artefact_sha256=sha256_fichier(chemin))
    return Manifest(**{**m.en_dict(), "version": version})


def _enregistrer(reg, tmp_path, version, contenu=b"modele"):
    chemin = _artefact(tmp_path, f"{version}.pkl", contenu)
    return reg.enregistrer(_manifest(tmp_path, chemin, version), chemin)


# ─── Cycle de vie ──────────────────────────────────────────────────────────────────────

def test_un_modele_enregistre_est_candidat_pas_production(tmp_path):
    """Enregistrer n'est PAS promouvoir. Confondre les deux mettrait en production tout
    ce qui sort d'un entraînement."""
    reg = Registre(tmp_path)
    e = _enregistrer(reg, tmp_path, "v1")
    assert e.statut == CANDIDAT
    assert reg.production() is None


def test_promotion_puis_remplacement_archive_le_precedent(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    _enregistrer(reg, tmp_path, "v2", b"autre")
    assert reg.promouvoir("v1", "premier modèle")[0]
    assert reg.production().version == "v1"
    assert reg.promouvoir("v2", "meilleur DSR")[0]
    assert reg.production().version == "v2"
    assert reg.entrees["v1"].statut == ARCHIVE


def test_un_seul_modele_en_production_a_la_fois(tmp_path):
    """C'est l'invariant du registre : deux productions, et le serving ne sait plus lequel
    charger — sans qu'aucune erreur ne soit levée."""
    reg = Registre(tmp_path)
    for v in ("v1", "v2", "v3"):
        _enregistrer(reg, tmp_path, v, v.encode())
        reg.promouvoir(v, "test")
    assert len(reg.par_statut(PRODUCTION)) == 1
    assert reg.incoherences() == []


def test_une_version_ne_peut_pas_etre_enregistree_deux_fois(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    with pytest.raises(ValueError):
        _enregistrer(reg, tmp_path, "v1")


# ─── Rollback — la raison d'être du registre ───────────────────────────────────────────

def test_rollback_revient_a_la_production_precedente(tmp_path):
    reg = Registre(tmp_path)
    for v in ("v1", "v2"):
        _enregistrer(reg, tmp_path, v, v.encode())
        reg.promouvoir(v, "test")
    ok, msg = reg.rollback("v2 dégrade en paper")
    assert ok and "v1" in msg
    assert reg.production().version == "v1"
    assert reg.entrees["v2"].statut == ARCHIVE


def test_rollback_recule_si_l_archive_a_disparu(tmp_path):
    """Un rollback sert à RÉTABLIR un service. Si le fichier le plus récent a disparu, il
    doit reculer encore, pas abandonner."""
    reg = Registre(tmp_path)
    for v in ("v1", "v2", "v3"):
        _enregistrer(reg, tmp_path, v, v.encode())
        reg.promouvoir(v, "test")
    (tmp_path / "v2.pkl").unlink()            # l'archive la plus récente n'existe plus
    ok, msg = reg.rollback()
    assert ok and "v1" in msg
    assert reg.production().version == "v1"


def test_rollback_sans_archive_echoue_clairement(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    reg.promouvoir("v1", "test")
    ok, msg = reg.rollback()
    assert not ok and "aucune archive" in msg
    assert reg.production().version == "v1"    # on ne casse PAS la production en échouant


# ─── Intégrité : l'empreinte est revérifiée à la promotion ─────────────────────────────

def test_un_artefact_modifie_ne_peut_pas_etre_promu(tmp_path):
    """Entre l'enregistrement et la promotion, le fichier a pu être écrasé, tronqué par un
    disque plein, ou copié à moitié. Promouvoir sans revérifier mettrait en production un
    objet que personne n'a mesuré."""
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    (tmp_path / "v1.pkl").write_bytes(b"CORROMPU")
    ok, msg = reg.promouvoir("v1", "test")
    assert not ok and "empreinte NON conforme" in msg
    assert reg.production() is None


def test_un_artefact_absent_ne_peut_pas_etre_promu(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    (tmp_path / "v1.pkl").unlink()
    ok, msg = reg.promouvoir("v1", "test")
    assert not ok and "absent" in msg


def test_un_manifeste_sans_empreinte_reste_promouvable_mais_le_dit(tmp_path):
    """Refuser rendrait tout l'historique ANTÉRIEUR au contrat impromouvable — on perdrait
    la traçabilité en voulant l'améliorer."""
    reg = Registre(tmp_path)
    chemin = _artefact(tmp_path, "vieux.pkl")
    m = Manifest.creer("swing_ml", "EXP", dataset_hash="d", feature_version="v")
    reg.enregistrer(Manifest(**{**m.en_dict(), "version": "vieux"}), chemin)
    ok, pourquoi = reg._artefact_valide(reg.entrees["vieux"])
    assert ok and "antérieur au contrat" in pourquoi


# ─── Rejet ─────────────────────────────────────────────────────────────────────────────

def test_une_version_rejetee_ne_peut_plus_etre_promue(tmp_path):
    """Un rejet est une DÉCISION. La contourner par une promotion l'annulerait en silence."""
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    assert reg.rejeter("v1", "PBO 0,88")[0]
    ok, msg = reg.promouvoir("v1", "test")
    assert not ok and "rejetée" in msg


def test_la_production_ne_peut_pas_etre_rejetee_directement(tmp_path):
    """Sinon le serving se retrouve sans modèle, sans que personne l'ait décidé."""
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    reg.promouvoir("v1", "test")
    ok, msg = reg.rejeter("v1", "mauvais")
    assert not ok and "rollback" in msg


# ─── Persistance ───────────────────────────────────────────────────────────────────────

def test_le_registre_survit_au_processus(tmp_path):
    """Le défaut d'origine : `ModelRegistry` était en mémoire, donc n'a jamais rien gardé."""
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    reg.promouvoir("v1", "test")
    relu = Registre(tmp_path)
    assert relu.production() is not None
    assert relu.production().version == "v1"
    assert relu.entrees["v1"].manifest["dataset_hash"] == "d1"


def test_l_historique_des_statuts_est_conserve(tmp_path):
    """Un registre qui écrase son historique ne répond plus à « pourquoi celui-ci ? »."""
    reg = Registre(tmp_path)
    for v in ("v1", "v2"):
        _enregistrer(reg, tmp_path, v, v.encode())
        reg.promouvoir(v, f"promotion {v}")
    h = Registre(tmp_path).entrees["v1"].historique
    assert [x["vers"] for x in h] == [CANDIDAT, PRODUCTION, ARCHIVE]
    assert "remplacée par v2" in h[-1]["motif"]


def test_un_registre_illisible_n_est_pas_ecrase(tmp_path):
    """Perdre l'historique parce qu'un octet est corrompu serait le pire des deux maux."""
    (tmp_path / "registre.json").write_text("{ ceci n'est pas du json", encoding="utf-8")
    reg = Registre(tmp_path)
    assert reg.entrees == {}
    assert "ceci n'est pas du json" in (tmp_path / "registre.json").read_text(encoding="utf-8")


def test_l_ecriture_est_atomique_et_ne_laisse_pas_de_temporaire(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    assert list(tmp_path.glob("*.tmp")) == []
    json.loads((tmp_path / "registre.json").read_text(encoding="utf-8"))


def test_incoherences_voit_deux_productions(tmp_path):
    reg = Registre(tmp_path)
    for v in ("v1", "v2"):
        _enregistrer(reg, tmp_path, v, v.encode())
    reg.entrees["v1"].statut = PRODUCTION      # état impossible, forcé à la main
    reg.entrees["v2"].statut = PRODUCTION
    soucis = reg.incoherences()
    assert any("2 versions en production" in s for s in soucis)


def test_statut_rejete_exporte_son_motif(tmp_path):
    reg = Registre(tmp_path)
    _enregistrer(reg, tmp_path, "v1")
    reg.rejeter("v1", "DSR 0,00 — aucun edge OOS")
    e = Registre(tmp_path).entrees["v1"]
    assert e.statut == REJETE
    assert "DSR 0,00" in e.historique[-1]["motif"]
