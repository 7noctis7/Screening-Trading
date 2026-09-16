"""Le moteur NLP. La garantie testée ici : il rend TOUJOURS un signal, jamais une exception.

Une classification de dépêche n'a pas à pouvoir interrompre les prix, la stratégie, le
risque ou l'exécution — qui passent tous avant elle dans la hiérarchie du projet.
"""

import asyncio
import time

import pytest

from packages.nlp.config import ConfigNLP
from packages.nlp.disjoncteur import OUVERT, Disjoncteur
from packages.nlp.moteur import MoteurNLP

BON = {"ticker": "AAPL", "sentiment": "BULLISH", "confidence_score": 0.7,
       "impact_horizon": "SWING", "catalyst_summary": "Résultats."}


class PiloteFactice:
    """Répond ce qu'on lui dit, compte ses appels, n'ouvre aucune connexion."""

    nom = "factice"

    def __init__(self, reponse=BON, lever=None, lenteur=0.0):
        self.reponse, self.lever, self.lenteur = reponse, lever, lenteur
        self.appels = 0

    def disponible(self, timeout=3.0):
        return True

    def classer(self, systeme, utilisateur, timeout):
        self.appels += 1
        if self.lenteur:
            time.sleep(self.lenteur)
        if self.lever:
            raise self.lever
        return self.reponse


def _moteur(pilote, **kw):
    cfg = ConfigNLP(modele="test", timeout_s=kw.pop("timeout_s", 5.0),
                    concurrence=kw.pop("concurrence", 2),
                    cache_max=kw.pop("cache_max", 8))
    return MoteurNLP(cfg=cfg, pilote=pilote, **kw)


def _run(coro):
    return asyncio.run(coro)


# ─── Le chemin nominal ─────────────────────────────────────────────────────────────────

def test_un_signal_valide_remonte_avec_sa_provenance():
    m = _moteur(PiloteFactice())
    s = _run(m.classer("AAPL", "texte"))
    assert s.sentiment == "BULLISH" and not s.repli
    assert s.modele == "test" and s.version_invite == "nlp_v1"
    assert s.latence_ms is not None


# ─── Les quatre façons d'échouer, et le repli à chaque fois ────────────────────────────

def test_aucun_fournisseur_donne_un_repli_nomme():
    m = MoteurNLP(cfg=ConfigNLP(modele="test"), pilote=None)
    m._pilote_resolu = True                     # aucun fournisseur détecté
    s = _run(m.classer("AAPL", "texte"))
    assert s.repli and "AUCUN_FOURNISSEUR" in s.resume


def test_une_exception_du_pilote_ne_remonte_JAMAIS():
    m = _moteur(PiloteFactice(lever=RuntimeError("boum")))
    s = _run(m.classer("AAPL", "texte"))
    assert s.repli and "ERREUR_FOURNISSEUR" in s.resume
    assert s.sentiment == "NEUTRAL" and s.confiance == 0.0


def test_un_depassement_de_delai_donne_un_repli_TIMEOUT():
    m = _moteur(PiloteFactice(lenteur=0.3), timeout_s=0.01)
    s = _run(m.classer("AAPL", "texte"))
    assert s.repli and "TIMEOUT" in s.resume
    assert m.metriques()["timeouts"] == 1


def test_une_reponse_illisible_donne_un_repli():
    m = _moteur(PiloteFactice(reponse=None))
    s = _run(m.classer("AAPL", "texte"))
    assert s.repli and "ILLISIBLE" in s.resume


# ─── Disjoncteur ───────────────────────────────────────────────────────────────────────

def test_le_disjoncteur_ouvert_repond_SANS_appeler_le_fournisseur():
    """C'est toute sa raison d'être : ne pas payer le délai quand on sait déjà."""
    p = PiloteFactice(lever=RuntimeError("mort"))
    m = _moteur(p, disjoncteur=Disjoncteur(seuil=2, refroidissement_s=999.0))
    for _ in range(2):
        _run(m.classer("AAPL", "t"))
    appels_avant = p.appels
    s = _run(m.classer("MSFT", "t"))
    assert s.repli and "DISJONCTEUR_OUVERT" in s.resume
    assert p.appels == appels_avant, "le fournisseur ne devait PAS être appelé"
    assert m.metriques()["disjoncteur"]["etat"] == OUVERT


def test_un_succes_referme_le_disjoncteur():
    p = PiloteFactice()
    m = _moteur(p, disjoncteur=Disjoncteur(seuil=2))
    _run(m.classer("AAPL", "t"))
    assert m.metriques()["disjoncteur"]["etat"] == "CLOSED"


# ─── Cache ─────────────────────────────────────────────────────────────────────────────

def test_le_cache_evite_un_second_appel():
    p = PiloteFactice()
    m = _moteur(p)
    _run(m.classer("AAPL", "même texte"))
    _run(m.classer("AAPL", "même texte"))
    assert p.appels == 1 and m.metriques()["cache"] == 1


def test_le_cache_est_BORNE():
    """Sans borne, classer deux cents titres par jour pendant un mois garde tout en RAM."""
    m = _moteur(PiloteFactice(), cache_max=3)
    for i in range(10):
        _run(m.classer("AAPL", f"texte {i}"))
    assert m.metriques()["cache_taille"] == 3


def test_un_repli_n_est_PAS_mis_en_cache():
    """Le mettre en cache figerait une panne passagère pour toute la session."""
    p = PiloteFactice(lever=RuntimeError("x"))
    m = _moteur(p)
    _run(m.classer("AAPL", "t"))
    _run(m.classer("AAPL", "t"))
    assert p.appels == 2 and m.metriques()["cache_taille"] == 0


def test_changer_d_invite_invalide_le_cache():
    """Comparer deux versions d'invite sur des réponses mises en cache par l'ancienne ne
    comparerait rien."""
    p = PiloteFactice()
    m = _moteur(p)
    _run(m.classer("AAPL", "t", "nlp_v1"))
    assert m._cle("AAPL", "t", "nlp_v1") != m._cle("AAPL", "t", "nlp_v2")


def test_un_texte_different_n_est_pas_le_meme_cache():
    p = PiloteFactice()
    m = _moteur(p)
    _run(m.classer("AAPL", "a"))
    _run(m.classer("AAPL", "b"))
    assert p.appels == 2


# ─── Concurrence bornée ────────────────────────────────────────────────────────────────

def test_la_concurrence_est_effectivement_bornee():
    """Deux requêtes simultanées sur un 7B quantifié saturent déjà la mémoire unifiée
    d'un Mac 16 Go ; au-delà, macOS échange sur disque."""
    ensemble = {"max": 0, "courant": 0}

    class PiloteCompteur(PiloteFactice):
        def classer(self, systeme, utilisateur, timeout):
            ensemble["courant"] += 1
            ensemble["max"] = max(ensemble["max"], ensemble["courant"])
            time.sleep(0.05)
            ensemble["courant"] -= 1
            return BON

    m = _moteur(PiloteCompteur(), concurrence=2)
    items = [(f"T{i}", f"texte {i}") for i in range(8)]
    signaux = _run(m.classer_lot(items))
    assert len(signaux) == 8
    assert ensemble["max"] <= 2, f"concurrence observée {ensemble['max']} > 2"


def test_un_lot_survit_a_une_panne_sur_un_titre():
    """Une panne sur un titre ne doit pas annuler les autres."""
    class PiloteCapricieux(PiloteFactice):
        def classer(self, systeme, utilisateur, timeout):
            if "AAPL" in utilisateur:
                raise RuntimeError("ce titre casse")
            return BON

    m = _moteur(PiloteCapricieux())
    s = _run(m.classer_lot([("AAPL", "a"), ("MSFT", "b"), ("TSLA", "c")]))
    assert len(s) == 3
    assert s[0].repli and not s[1].repli and not s[2].repli


def test_une_annulation_reste_une_annulation():
    """`CancelledError` est une DÉCISION de l'appelant : l'avaler en repli empêcherait
    d'arrêter proprement une boucle."""
    async def scenario():
        m = _moteur(PiloteFactice(lenteur=1.0), timeout_s=5.0)
        t = asyncio.create_task(m.classer("AAPL", "t"))
        await asyncio.sleep(0.05)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    _run(scenario())


# ─── Observabilité ─────────────────────────────────────────────────────────────────────

def test_les_metriques_exposent_ce_qu_il_faut_surveiller():
    m = _moteur(PiloteFactice())
    _run(m.classer("AAPL", "t"))
    mx = m.metriques()
    for cle in ("taux_repli", "taux_neutre", "taux_cache", "latence_mediane_ms",
                "cache_taille", "disjoncteur", "config", "appels", "succes"):
        assert cle in mx


def test_le_taux_de_neutres_est_compte():
    """Un taux de neutres qui s'envole est le premier symptôme visible d'un problème de
    source, d'invite ou de modèle — sans qu'on puisse conclure lequel."""
    m = _moteur(PiloteFactice(reponse={**BON, "sentiment": "NEUTRAL"}))
    for i in range(4):
        _run(m.classer(f"T{i}", "t"))
    assert m.metriques()["taux_neutre"] == 1.0


def test_le_delai_annonce_est_le_delai_REEL():
    """Défaut trouvé par le test précédent : `wait_for` avait deux secondes de marge
    « par prudence », donc configurer 12 s en attendait 14. Un plafond qui ment n'est
    pas un plafond.

    La mesure se fait DANS la boucle : `asyncio.run` attend l'arrêt de son exécuteur à la
    fermeture, donc mesurer autour de lui mesurerait le fil orphelin, pas le plafond.
    """
    async def scenario():
        m = _moteur(PiloteFactice(lenteur=1.0), timeout_s=0.2)
        debut = time.perf_counter()
        s = await m.classer("AAPL", "t")
        return s, time.perf_counter() - debut

    s, ecoule = _run(scenario())
    assert s.repli and "TIMEOUT" in s.resume
    assert ecoule < 0.6, f"le plafond de 0,2 s n'a pas tenu : {ecoule:.2f} s"


def test_le_semaphore_est_libere_des_l_expiration():
    """Le fil du pilote survit à l'expiration (`to_thread` ne s'annule pas), mais la PLACE
    de concurrence, elle, doit être rendue tout de suite — sinon un fournisseur bloqué
    gèlerait tout le lot au lieu d'un seul titre."""
    async def scenario():
        m = _moteur(PiloteFactice(lenteur=1.0), timeout_s=0.15, concurrence=1)
        debut = time.perf_counter()
        await m.classer_lot([("A", "a"), ("B", "b"), ("C", "c")])
        return time.perf_counter() - debut

    ecoule = _run(scenario())
    # Trois expirations SÉQUENTIELLES à 0,15 s ≈ 0,45 s. Si la place n'était pas rendue,
    # il faudrait attendre les fils d'une seconde chacun, soit trois fois plus.
    assert ecoule < 1.0, f"la place de concurrence n'est pas rendue : {ecoule:.2f} s"


def test_le_pilote_recoit_aussi_un_delai():
    """`to_thread` ne s'annule pas : sans délai côté pilote, chaque expiration laisserait
    un fil orphelin qui attend indéfiniment sa socket."""
    vus = []

    class PiloteQuiNoteLeDelai(PiloteFactice):
        def classer(self, systeme, utilisateur, timeout):
            vus.append(timeout)
            return BON

    m = _moteur(PiloteQuiNoteLeDelai(), timeout_s=7.0)
    _run(m.classer("AAPL", "t"))
    assert vus == [7.0]
