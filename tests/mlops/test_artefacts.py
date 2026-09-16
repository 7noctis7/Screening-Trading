"""Le magasin d'artefacts. Une règle : rien n'est accepté sans vérification d'empreinte.

Un transfert coupé à 99 % laisse un fichier de taille plausible et de contenu faux. Un
modèle tronqué se dépickle parfois, prédit n'importe quoi, et RIEN ne le signale.
"""

import pytest

from packages.mlops.artefacts import MagasinLocal, transferer
from packages.mlops.empreinte import sha256_fichier


def _source(tmp_path, nom="m.pkl", contenu=b"modele entraine"):
    p = tmp_path / nom
    p.write_bytes(contenu)
    return p


def test_deposer_rend_l_empreinte_a_reverifier(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    src = _source(tmp_path)
    d = m.deposer("exp/v1.pkl", src)
    assert d.empreinte == sha256_fichier(src) and d.octets == len(b"modele entraine")


def test_recuperer_avec_la_bonne_empreinte_publie_le_fichier(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    d = m.deposer("exp/v1.pkl", _source(tmp_path))
    r = m.recuperer("exp/v1.pkl", tmp_path / "out.pkl", d.empreinte)
    assert r.conforme and r.chemin.read_bytes() == b"modele entraine"


def test_une_empreinte_fausse_N_ECRIT_RIEN(tmp_path):
    """Poser le fichier à sa place définitive puis constater qu'il est faux laisserait un
    artefact corrompu là où on va le chercher."""
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("exp/v1.pkl", _source(tmp_path))
    dest = tmp_path / "out.pkl"
    r = m.recuperer("exp/v1.pkl", dest, "0" * 64)
    assert not r.conforme and "NON conforme" in r.motif
    assert not dest.exists(), "un fichier rejeté ne doit JAMAIS être publié"


def test_aucune_empreinte_fournie_est_DIT(tmp_path):
    """Ne pas vérifier est un choix de l'appelant ; le taire en ferait un défaut."""
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("exp/v1.pkl", _source(tmp_path))
    r = m.recuperer("exp/v1.pkl", tmp_path / "out.pkl")
    assert r.conforme and "non vérifié" in r.motif


def test_un_artefact_absent_est_signale_pas_inventé(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    r = m.recuperer("jamais/depose.pkl", tmp_path / "out.pkl")
    assert not r.conforme and "absent" in r.motif


def test_deposer_une_source_absente_leve(tmp_path):
    with pytest.raises(FileNotFoundError):
        MagasinLocal(tmp_path / "magasin").deposer("x.pkl", tmp_path / "rien.pkl")


# ─── Sécurité des clés ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cle", ["../evasion.pkl", "a/../../b.pkl", "/etc/passwd", "", "   "])
def test_une_cle_qui_sort_du_magasin_est_refusee(tmp_path, cle):
    """La clé vient d'un manifeste, potentiellement produit par une machine distante :
    elle n'est pas de confiance par construction."""
    m = MagasinLocal(tmp_path / "magasin")
    with pytest.raises(ValueError):
        m.deposer(cle, _source(tmp_path))


def test_les_sous_dossiers_legitimes_passent(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("EXP-2026-09-001/swing/v12.pkl", _source(tmp_path))
    assert m.existe("EXP-2026-09-001/swing/v12.pkl")


# ─── Dépôt atomique ────────────────────────────────────────────────────────────────────

def test_aucun_fichier_partiel_ne_subsiste(tmp_path):
    """Un dépôt interrompu ne doit pas laisser un artefact partiel SOUS SA CLÉ DÉFINITIVE,
    où il serait pris pour complet."""
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("exp/v1.pkl", _source(tmp_path))
    assert list((tmp_path / "magasin").rglob("*.partiel")) == []


def test_lister_ignore_les_partiels(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("exp/v1.pkl", _source(tmp_path))
    (tmp_path / "magasin" / "exp" / "v2.pkl.partiel").write_bytes(b"incomplet")
    assert m.lister() == ["exp/v1.pkl"]


def test_lister_filtre_par_prefixe(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("A/x.pkl", _source(tmp_path))
    m.deposer("B/y.pkl", _source(tmp_path, "y.pkl", b"autre"))
    assert m.lister("A/") == ["A/x.pkl"]


def test_supprimer_dit_s_il_a_supprime(tmp_path):
    m = MagasinLocal(tmp_path / "magasin")
    m.deposer("exp/v1.pkl", _source(tmp_path))
    assert m.supprimer("exp/v1.pkl") is True
    assert m.supprimer("exp/v1.pkl") is False


# ─── Transfert de bout en bout ─────────────────────────────────────────────────────────

def test_un_transfert_est_verifie_de_bout_en_bout(tmp_path):
    """Le chemin qu'empruntera un modèle entraîné sur GPU distant."""
    a, b = MagasinLocal(tmp_path / "A"), MagasinLocal(tmp_path / "B")
    a.deposer("exp/v1.pkl", _source(tmp_path))
    r = transferer(a, b, "exp/v1.pkl", tmp_path / "tampon.pkl")
    assert r.conforme and "bout en bout" in r.motif
    assert b.existe("exp/v1.pkl")


def test_un_transfert_altere_RETIRE_l_artefact_de_la_destination(tmp_path):
    """Laisser un artefact corrompu dans le magasin de destination serait pire que de ne
    rien transférer : on irait l'y chercher."""
    class MagasinQuiCorrompt(MagasinLocal):
        def deposer(self, cle, source):
            d = super().deposer(cle, source)
            self._chemin(cle).write_bytes(b"CORROMPU")
            return d

    a = MagasinLocal(tmp_path / "A")
    b = MagasinQuiCorrompt(tmp_path / "B")
    a.deposer("exp/v1.pkl", _source(tmp_path))
    r = transferer(a, b, "exp/v1.pkl", tmp_path / "tampon.pkl")
    assert not r.conforme and "retiré" in r.motif
    assert not b.existe("exp/v1.pkl")


def test_transferer_un_artefact_absent_echoue_proprement(tmp_path):
    a, b = MagasinLocal(tmp_path / "A"), MagasinLocal(tmp_path / "B")
    r = transferer(a, b, "rien.pkl", tmp_path / "tampon.pkl")
    assert not r.conforme and "source" in r.motif


def test_le_magasin_ne_depickle_RIEN():
    """Il déplace des octets et compare des empreintes. C'est ce qui permet de l'appeler
    depuis un chemin non fiable sans y réfléchir à deux fois."""
    import ast
    import pathlib
    chemin = (pathlib.Path(__file__).resolve().parents[2] / "packages" / "mlops"
              / "artefacts.py")
    # On inspecte le CODE, pas le texte : la docstring dit « ne dépickle rien », et
    # chercher le mot y trouverait sa propre négation.
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    importes: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            importes |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            importes.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id not in ("eval", "exec", "__import__"), f"appel {n.func.id}"
    assert "pickle" not in importes
    assert not any(m.startswith("packages") and "pickle" in m for m in importes)
