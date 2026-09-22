"""L'attente des fills : ce qu'elle garantit, et ce qu'elle refuse de taire.

Le 22/09, six achats envoyés ont produit deux ouvertures au journal, dont deux tronquées
— 22 695,70 $ de prix de revient absent pour une séance. Les fills étaient lisibles
quarante minutes plus tard : la journalisation lisait un compte qui n'avait pas fini
d'exécuter.

Contrats épinglés ici :
  1. rien à attendre → aucune lecture, aucun sommeil (le dry-run ne paie rien) ;
  2. tout déjà lisible → UNE lecture, aucun sommeil (le cas normal est gratuit) ;
  3. lisible au bout de N lectures → on s'arrête à N, pas au délai ;
  4. délai dépassé → on rend la main en NOMMANT ce qui manque, sans jamais le dépasser ;
  5. une lecture qui LÈVE ne casse rien, et n'est pas confondue avec « rien de nouveau » ;
  6. on n'attend que ce qu'on a envoyé ;
  7. le message parle AUSSI quand tout va bien — c'est le silence qui a coûté quatre jours.
"""
from __future__ import annotations

import pytest

from packages.execution.attente_fills import attendre, message


class Horloge:
    """Temps simulé : `dormir` avance l'horloge, rien n'attend réellement."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sommeils: list[float] = []

    def __call__(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.sommeils.append(s)
        self.t += s


def _lecteur(pages: list[set]):
    """Rend les pages l'une après l'autre, puis répète la dernière."""
    etat = {"i": 0}

    def lire() -> set:
        i = min(etat["i"], len(pages) - 1)
        etat["i"] += 1
        return pages[i]
    return lire


def test_rien_a_attendre_ne_lit_rien():
    h = Horloge()
    lu = {"n": 0}

    def lire():
        lu["n"] += 1
        return set()
    r = attendre(lire, set(), horloge=h, dormir=h.dormir)
    assert lu["n"] == 0 and h.sommeils == []
    assert r["tours"] == 0 and r["manquants"] == set()


def test_tout_deja_lisible_ne_dort_pas():
    """Le cas normal — un run tardif, un marché calme — doit être GRATUIT."""
    h = Horloge()
    r = attendre(_lecteur([{"a", "b"}]), {"a", "b"}, horloge=h, dormir=h.dormir)
    assert r["tours"] == 1 and h.sommeils == []
    assert r["lisibles"] == {"a", "b"} and r["manquants"] == set()
    assert r["attendu_s"] == 0.0


def test_s_arrete_des_que_tout_est_lisible():
    h = Horloge()
    r = attendre(_lecteur([set(), {"a"}, {"a", "b"}]), {"a", "b"},
                 pas_s=3.0, horloge=h, dormir=h.dormir)
    assert r["tours"] == 3 and h.sommeils == [3.0, 3.0]
    assert r["manquants"] == set() and r["attendu_s"] == 6.0


def test_le_delai_est_une_borne_JAMAIS_depassee():
    """On ne dort pas si le réveil tomberait après le délai : le run n'est pas retenu."""
    h = Horloge()
    r = attendre(_lecteur([set()]), {"a"}, delai_s=10.0, pas_s=3.0,
                 horloge=h, dormir=h.dormir)
    assert r["attendu_s"] <= 10.0 and h.t <= 10.0
    assert r["manquants"] == {"a"} and r["lisibles"] == set()


def test_une_lecture_qui_leve_ne_casse_pas_l_attente():
    h = Horloge()

    def lire():
        raise RuntimeError("courtier muet")
    r = attendre(lire, {"a"}, delai_s=7.0, pas_s=3.0, horloge=h, dormir=h.dormir)
    assert r["manquants"] == {"a"}
    assert r["lectures_illisibles"] == r["tours"] > 0


def test_courtier_muet_et_courtier_vide_ne_se_confondent_pas():
    """ABSENT n'est pas ZÉRO : une panne de lecture ne doit pas ressembler à
    « les ordres ne sont pas encore prêts »."""
    h = Horloge()
    vide = attendre(_lecteur([set()]), {"a"}, delai_s=4.0, pas_s=3.0,
                    horloge=h, dormir=h.dormir)
    assert vide["lectures_illisibles"] == 0
    assert vide["manquants"] == {"a"}          # même résultat…
    h2 = Horloge()

    def leve():
        raise OSError("timeout")
    muet = attendre(leve, {"a"}, delai_s=4.0, pas_s=3.0, horloge=h2, dormir=h2.dormir)
    assert muet["lectures_illisibles"] > 0     # …mais le motif est distinct


def test_on_n_attend_que_ce_qu_on_a_envoye():
    h = Horloge()
    r = attendre(_lecteur([{"a", "zzz"}]), {"a"}, horloge=h, dormir=h.dormir)
    assert r["lisibles"] == {"a"}              # « zzz » n'est pas à nous


def test_les_identifiants_sont_normalises_en_texte():
    """Le courtier peut rendre un UUID : la comparaison doit rester possible."""
    import uuid
    u = uuid.uuid4()
    h = Horloge()
    r = attendre(_lecteur([{str(u)}]), {u}, horloge=h, dormir=h.dormir)
    assert r["manquants"] == set()


@pytest.mark.parametrize("attendus", [set(), None])
def test_aucun_ordre_rend_un_resultat_neutre(attendus):
    r = attendre(lambda: set(), attendus)
    assert r == {"lisibles": set(), "manquants": set(), "tours": 0,
                 "attendu_s": 0.0, "lectures_illisibles": 0}


def test_le_message_parle_AUSSI_quand_tout_va_bien():
    h = Horloge()
    m = message(attendre(_lecteur([{"a"}]), {"a"}, horloge=h, dormir=h.dormir))
    assert "1 ordre(s) lisible(s)" in m and "ILLISIBLE" not in m


def test_le_message_NOMME_les_manquants_et_dit_le_rattrapage():
    h = Horloge()
    r = attendre(_lecteur([set()]), {"id-1", "id-2"}, delai_s=4.0, pas_s=3.0,
                 horloge=h, dormir=h.dormir)
    m = message(r, {"id-1": "TTEK", "id-2": "DUOL"})
    assert "TTEK" in m and "DUOL" in m
    assert "completer-ouvertures" in m


def test_le_message_signale_un_courtier_muet():
    h = Horloge()

    def leve():
        raise OSError("timeout")
    m = message(attendre(leve, {"a"}, delai_s=4.0, pas_s=3.0, horloge=h, dormir=h.dormir))
    assert "sans réponse du courtier" in m
