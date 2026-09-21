"""Cycle de vie d'un travail de calcul — et l'interdiction qu'une machine reste allumée.

Les deux scénarios EXIGÉS par le cahier des charges (point 63) sont testés ici :
  · échec d'entraînement  → instance arrêtée → travail marqué ÉCHOUÉ → production intacte
  · succès                → artefacts + empreinte valide → instance arrêtée → candidat local
"""

import pathlib

import pytest

from packages.mlops.artefacts import MagasinLocal
from packages.mlops.backends.local import BackendLocal
from packages.mlops.compute import (
    ARRETE,
    ECHOUE,
    EXPIRE,
    REUSSI,
    EtatTravail,
    Superviseur,
    Travail,
)

PY = "python3"


def _travail(code: str, **kw) -> Travail:
    kw.setdefault("max_runtime_s", 30.0)
    return Travail(experience=kw.pop("experience", "EXP-TEST"),
                   commande=[PY, "-c", code], **kw)


ECRIT_MODELE = ('import os,pathlib;'
                'pathlib.Path(os.environ["QUANT_SORTIE"],"modele.pkl").write_bytes(b"ok")')


# ─── Ce qu'un travail refuse d'être ────────────────────────────────────────────────────

def test_un_travail_sans_commande_est_refuse():
    with pytest.raises(ValueError, match="calcule rien"):
        Travail(experience="E", commande=[])


def test_il_n_existe_pas_de_duree_illimitee():
    """Le plafond n'a pas de valeur « infini » par construction : l'oubli le plus coûteux
    chez un loueur de GPU est celui qu'on n'a pas eu à écrire."""
    for mauvais in (0, -1, -3600):
        with pytest.raises(ValueError, match="illimité"):
            Travail(experience="E", commande=["x"], max_runtime_s=mauvais)


def test_un_secret_en_ligne_de_commande_est_refuse():
    """Il apparaîtrait dans `ps` de toute machine partagée — un GPU loué en est une."""
    with pytest.raises(ValueError, match="secret"):
        Travail(experience="E", commande=["python", "--k", "ALPACA_API_KEY=abc"])


def test_la_commande_doit_etre_un_argv():
    """Une chaîne shell laisserait un manifeste distant injecter « ; rm -rf »."""
    with pytest.raises(ValueError, match="argv"):
        Travail(experience="E", commande=["python", 42])


# ─── Scénario 1 : le travail réussit ───────────────────────────────────────────────────

def test_succes_artefact_recupere_et_instance_arretee(tmp_path):
    b = BackendLocal(atelier=tmp_path / "atelier")
    sup = Superviseur(b)
    t = _travail(ECRIT_MODELE, artefacts_attendus=("modele.pkl",))
    e = sup.executer(t, tmp_path / "recolte")
    assert e.etat == REUSSI and e.code_sortie == 0
    assert [pathlib.Path(a).name for a in e.artefacts] == ["modele.pkl"]
    assert (tmp_path / "recolte" / "modele.pkl").read_bytes() == b"ok"
    assert b.etat(t.id).termine, "le travail doit être dans un état FINAL"


def test_le_magasin_recoit_l_artefact_sous_l_experience(tmp_path):
    magasin = MagasinLocal(tmp_path / "magasin")
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"), magasin=magasin)
    t = _travail(ECRIT_MODELE, experience="EXP-2026-09-001",
                 artefacts_attendus=("modele.pkl",))
    sup.executer(t, tmp_path / "recolte")
    assert magasin.lister() == ["EXP-2026-09-001/modele.pkl"]


# ─── Scénario 2 : le travail échoue ────────────────────────────────────────────────────

def test_echec_le_travail_est_marque_echoue_et_rien_n_est_promu(tmp_path):
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    magasin = MagasinLocal(tmp_path / "magasin")
    sup.magasin = magasin
    e = sup.executer(_travail('raise SystemExit(3)'), tmp_path / "recolte")
    assert e.etat == ECHOUE and e.code_sortie == 3
    assert magasin.lister() == [], "un échec ne doit RIEN déposer"


def test_une_commande_introuvable_echoue_proprement(tmp_path):
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    t = Travail(experience="E", commande=["binaire-qui-n-existe-pas"], max_runtime_s=5)
    e = sup.executer(t, tmp_path / "recolte")
    assert e.etat == ECHOUE and "introuvable" in e.message


# ─── Le succès silencieux : sortie 0 mais rien produit ─────────────────────────────────

def test_sortir_en_zero_sans_artefact_N_EST_PAS_un_succes(tmp_path):
    """Le plus coûteux des échecs : il promeut du vide. Un travail dont le processus sort
    en 0 mais n'a rien écrit n'a pas fait son travail."""
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    t = _travail("pass", artefacts_attendus=("modele.pkl",))
    e = sup.executer(t, tmp_path / "recolte")
    assert e.etat == ECHOUE and "modele.pkl" in e.message


def test_sans_artefact_attendu_on_ne_reproche_rien(tmp_path):
    """Tous les travaux ne produisent pas de fichier — un balayage d'hyperparamètres peut
    n'écrire que des métriques."""
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    e = sup.executer(_travail("pass"), tmp_path / "recolte")
    assert e.etat == REUSSI


# ─── Plafond de durée ──────────────────────────────────────────────────────────────────

def test_le_plafond_tue_le_processus(tmp_path):
    """Protection 2, version locale : c'est `subprocess` qui tue, pas le travail."""
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    t = Travail(experience="E", commande=[PY, "-c", "import time;time.sleep(30)"],
                max_runtime_s=0.5)
    e = sup.executer(t, tmp_path / "recolte")
    assert e.etat == EXPIRE and "dépassé" in e.message
    assert e.runtime_s < 5.0, "le plafond n'a pas tenu"


# ─── PROTECTION 1 : l'arrêt dans un `finally` ──────────────────────────────────────────

def test_l_instance_est_arretee_MEME_si_la_recolte_leve(tmp_path):
    """Sans le `finally`, une exception entre « entraînement fini » et « artefacts
    récupérés » laisserait la machine allumée, et l'erreur remontée masquerait la facture
    qui court."""
    arrets = []

    class BackendQuiCasse(BackendLocal):
        def recuperer(self, travail_id, vers):
            raise OSError("disque plein")

        def terminer(self, travail_id, motif=""):
            arrets.append((travail_id, motif))
            return super().terminer(travail_id, motif)

    sup = Superviseur(BackendQuiCasse(atelier=tmp_path / "atelier"))
    t = _travail(ECRIT_MODELE)
    with pytest.raises(OSError):
        sup.executer(t, tmp_path / "recolte")
    assert arrets, "terminer() n'a PAS été appelé — la machine resterait allumée"
    assert arrets[0][0] == t.id


def test_une_interruption_clavier_arrete_aussi_l_instance(tmp_path):
    """`KeyboardInterrupt` n'hérite pas d'`Exception` : un `except Exception` seul la
    laisserait passer sans arrêter la machine."""
    arrets = []

    class BackendInterrompu(BackendLocal):
        def recuperer(self, travail_id, vers):
            raise KeyboardInterrupt

        def terminer(self, travail_id, motif=""):
            arrets.append(travail_id)
            return super().terminer(travail_id, motif)

    sup = Superviseur(BackendInterrompu(atelier=tmp_path / "atelier"))
    with pytest.raises(KeyboardInterrupt):
        sup.executer(_travail(ECRIT_MODELE), tmp_path / "recolte")
    assert arrets


def test_terminer_est_idempotent(tmp_path):
    """Le superviseur l'appelle dans un `finally` : il sera appelé sur des travaux déjà
    terminés, et cela ne doit rien réécrire."""
    b = BackendLocal(atelier=tmp_path / "atelier")
    t = _travail(ECRIT_MODELE)
    e = b.soumettre(t)
    assert e.etat == REUSSI
    assert b.terminer(t.id, "un") and b.terminer(t.id, "deux")
    assert b.etat(t.id).etat == REUSSI, "un travail FINI ne doit pas repasser à ARRÊTÉ"


def test_terminer_un_travail_inconnu_rend_False(tmp_path):
    assert BackendLocal(atelier=tmp_path / "atelier").terminer("jamais-vu") is False


def test_un_travail_non_termine_passe_a_ARRETE(tmp_path):
    b = BackendLocal(atelier=tmp_path / "atelier")
    b._etats["x"] = EtatTravail(travail_id="x", etat="en_cours")
    b.terminer("x", "plafond")
    assert b.etat("x").etat == ARRETE and b.etat("x").message == "plafond"


# ─── Capacité du backend, et ce qu'il avoue ────────────────────────────────────────────

def test_un_backend_sans_plafond_INFRA_est_signale(tmp_path):
    """On n'interdit pas — un backend local n'a pas de facture. On le DIT, parce qu'un
    défaut de protection silencieux est ce qui coûte cher chez un loueur."""
    class BackendSansPlafond(BackendLocal):
        nom = "factice-sans-plafond"

        def impose_max_runtime(self):
            return False

    sup = Superviseur(BackendSansPlafond(atelier=tmp_path / "atelier"))
    sup.executer(_travail("pass"), tmp_path / "recolte")
    assert any("n'impose pas de plafond" in a for a in sup.avertissements)
    assert any("GPU facturé" in a for a in sup.avertissements)


def test_le_backend_local_impose_bien_son_plafond(tmp_path):
    assert BackendLocal(atelier=tmp_path / "atelier").impose_max_runtime() is True


def test_le_cout_local_est_zero_PAS_inconnu(tmp_path):
    """`None` voudrait dire « je ne sais pas » — ce qui est faux : une machine qu'on
    possède ne facture rien à l'heure."""
    assert BackendLocal(atelier=tmp_path / "atelier").cout_estime(3600.0) == 0.0


def test_chaque_travail_a_son_atelier(tmp_path):
    """Deux entraînements concurrents écrivant au même endroit se voleraient leurs
    fichiers."""
    b = BackendLocal(atelier=tmp_path / "atelier")
    t1, t2 = _travail(ECRIT_MODELE), _travail(ECRIT_MODELE)
    b.soumettre(t1)
    b.soumettre(t2)
    assert b._sortie(t1.id) != b._sortie(t2.id)
    assert b._sortie(t1.id).exists() and b._sortie(t2.id).exists()


def test_le_nettoyage_n_est_JAMAIS_automatique(tmp_path):
    """Un artefact détruit avant vérification est irrécupérable (point 7)."""
    b = BackendLocal(atelier=tmp_path / "atelier")
    sup = Superviseur(b)
    t = _travail(ECRIT_MODELE, artefacts_attendus=("modele.pkl",))
    sup.executer(t, tmp_path / "recolte")
    assert b._sortie(t.id).exists(), "l'atelier ne doit pas être effacé tout seul"
    assert b.nettoyer(t.id) is True and b.nettoyer(t.id) is False


# ─── Sécurité : un calcul ne peut pas trader ───────────────────────────────────────────

def test_le_backend_n_offre_aucun_chemin_d_execution():
    racine = pathlib.Path(__file__).resolve().parents[2]
    for f in (racine / "packages" / "mlops" / "compute.py",
              racine / "packages" / "mlops" / "backends" / "local.py"):
        src = f.read_text(encoding="utf-8")
        for interdit in ("submit_notional", "close_position", "AlpacaBroker",
                         "--live --yes", "shell=True"):
            assert interdit not in src, f"{f.name} contient « {interdit} »"


def test_le_superviseur_n_ECRASE_PAS_le_verdict_du_backend(tmp_path):
    """« processus tué à l'échéance » dit CE QUI s'est passé ; « durée 1 s > plafond 0 s »
    n'est qu'une comparaison — et elle était fausse à l'affichage, l'arrondi à la seconde
    rendant le message absurde."""
    sup = Superviseur(BackendLocal(atelier=tmp_path / "atelier"))
    t = Travail(experience="E", commande=[PY, "-c", "import time;time.sleep(30)"],
                max_runtime_s=0.5)
    e = sup.executer(t, tmp_path / "recolte")
    assert e.etat == EXPIRE
    assert "processus tué" in e.message
    # Le plafond doit s'afficher au centième : « plafond de 0 s dépassé » serait absurde,
    # et une comparaison illisible ne se vérifie pas. (« 0 s » est une sous-chaîne de
    # « 0.50 s » — d'où l'assertion POSITIVE plutôt que négative.)
    assert "0.50 s" in e.message


def test_le_superviseur_rattrape_un_backend_qui_ne_detecte_PAS_l_expiration(tmp_path):
    """Son plafond reste utile : c'est le filet pour un backend distant qui rendrait un
    succès alors que la durée a explosé."""
    class BackendMenteur(BackendLocal):
        def soumettre(self, travail):
            e = super().soumettre(travail)
            e.etat, e.runtime_s = REUSSI, travail.max_runtime_s * 10
            return e

    sup = Superviseur(BackendMenteur(atelier=tmp_path / "atelier"))
    e = sup.executer(_travail("pass", max_runtime_s=1.0), tmp_path / "recolte")
    assert e.etat == EXPIRE and "superviseur" in e.message


@pytest.mark.parametrize("secondes,attendu", [(0.5, "0.50 s"), (5.25, "5.25 s"),
                                              (42.0, "42 s"), (900.0, "15 min")])
def test_les_durees_sont_lisibles_a_toutes_les_echelles(secondes, attendu):
    from packages.mlops.compute import _duree
    assert _duree(secondes) == attendu
    assert _duree(None) == "—"
