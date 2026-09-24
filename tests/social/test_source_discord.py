"""Un jeton recopié dans un message d'erreur est un jeton à révoquer.

C'est la fuite la plus banale et la plus silencieuse : une exception réseau porte l'URL
et parfois les en-têtes, on la relaie telle quelle dans un rapport d'ingestion, et le
secret part dans un log, une réponse d'API, ou une capture d'écran collée dans un chat.
Le dépôt est PUBLIC ; gitleaks garde les fichiers, pas les messages d'exécution.

Ce que ces tests épinglent :
  1. le jeton n'apparaît dans AUCUN rejet, quelle que soit la panne ;
  2. 401, 403 et 404 sont TROIS causes différentes, nommées séparément — les fondre en
     « aucun message » enverrait chercher un problème de flux là où il y a un problème
     de permission ;
  3. un jeton absent le DIT et ne tente aucun appel ;
  4. un message sans texte (image seule, autocollant) n'est pas une publication ;
  5. l'identifiant est stable, donc réingérer ne duplique pas.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from packages.social.modele import Classification, Direction
from packages.social.sources import charger_plugins, sources

JETON = "MTIzNDU2Nzg5.SECRET_A_NE_PAS_FUITER.xyz"

MESSAGES = [
    {"id": "901", "content": "BTCUSDT long, entrée 64000 SL 61000",
     "timestamp": "2026-09-24T10:00:00.000000+00:00"},
    {"id": "902", "content": "Rappel : comment lire un carnet d'ordres",
     "timestamp": "2026-09-24T09:00:00.000000+00:00"},
    {"id": "903", "content": "", "timestamp": "2026-09-24T08:00:00.000000+00:00"},
]


@pytest.fixture(autouse=True)
def _plugins():
    charger_plugins()


def _brancher(monkeypatch, charge):
    import packages.social.sources.discord as D

    def faux(requete, timeout=None):  # noqa: ARG001
        if isinstance(charge, Exception):
            raise charge
        rep = io.BytesIO(json.dumps(charge).encode())
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(D.urllib.request, "urlopen", faux)


def _http(code: int) -> urllib.error.HTTPError:
    """Une vraie HTTPError, dont l'URL contient le jeton — le cas qu'on redoute."""
    return urllib.error.HTTPError(
        url=f"https://discord.com/api/v10/channels/1?token={JETON}",
        code=code, msg="refus", hdrs=None, fp=None)


# ---- 1. le secret ----------------------------------------------------------------

@pytest.mark.parametrize("code", [401, 403, 404, 429, 500])
def test_le_JETON_ne_fuite_dans_AUCUN_rejet(monkeypatch, code):
    _brancher(monkeypatch, _http(code))
    src = sources.create("discord", salons="1:eliz883", jeton=JETON)
    src.lire()
    assert src.rejets, "une panne doit toujours être rapportée"
    for r in src.rejets:
        assert JETON not in r, f"fuite du jeton dans : {r}"
        assert "SECRET_A_NE_PAS_FUITER" not in r


def test_le_jeton_ne_fuite_pas_non_plus_sur_une_panne_reseau(monkeypatch):
    _brancher(monkeypatch, urllib.error.URLError(f"échec vers ...token={JETON}"))
    src = sources.create("discord", salons="1", jeton=JETON)
    src.lire()
    assert all(JETON not in r for r in src.rejets), src.rejets


# ---- 2. et 3. les refus ne se ressemblent pas ------------------------------------

def test_401_403_et_404_sont_TROIS_causes_distinctes(monkeypatch):
    attendus = {401: "révoqué", 403: "n'est pas dans ce serveur", 404: "introuvable"}
    for code, mot in attendus.items():
        _brancher(monkeypatch, _http(code))
        src = sources.create("discord", salons="1", jeton=JETON)
        src.lire()
        assert mot in src.rejets[0], (code, src.rejets)


def test_un_jeton_ABSENT_le_dit_et_ne_tente_AUCUN_appel(monkeypatch):
    """La cause est locale : le message doit envoyer chez Discord, pas au réseau."""
    appels = []

    import packages.social.sources.discord as D
    monkeypatch.setattr(D.urllib.request, "urlopen",
                        lambda *a, **k: appels.append(1))
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    src = sources.create("discord", salons="1")
    assert src.lire() == []
    assert appels == []
    assert "DISCORD_BOT_TOKEN absent" in src.rejets[0]


def test_un_salon_VIDE_est_nomme_et_non_confondu_avec_un_refus(monkeypatch):
    _brancher(monkeypatch, [])
    src = sources.create("discord", salons="1", jeton=JETON)
    assert src.lire() == []
    assert "aucun message" in src.rejets[0]


# ---- 4. et 5. le contenu ---------------------------------------------------------

def test_un_message_SANS_texte_n_est_pas_une_publication(monkeypatch):
    """Une image seule ou un autocollant ne porte aucun propos à classer."""
    _brancher(monkeypatch, MESSAGES)
    pubs = sources.create("discord", salons="1:eliz883", jeton=JETON).lire()
    assert {p.id.split("/")[-1] for p in pubs} == {"901", "902"}


def test_le_compte_vient_de_la_correspondance_pas_de_l_identifiant(monkeypatch):
    """Un identifiant de salon à 18 chiffres dans le filtre serait illisible."""
    _brancher(monkeypatch, MESSAGES)
    src = sources.create("discord", salons="123456789012345678:eliz883", jeton=JETON)
    assert {p.compte for p in src.lire()} == {"eliz883"}


def test_l_identifiant_est_STABLE_donc_relire_ne_duplique_pas(monkeypatch):
    _brancher(monkeypatch, MESSAGES)
    src = sources.create("discord", salons="1", jeton=JETON)
    assert [p.id for p in src.lire()] == [p.id for p in src.lire()]
    assert src.lire()[0].id == "discord:1/901"


def test_l_extraction_pre_remplit_depuis_le_texte(monkeypatch):
    _brancher(monkeypatch, MESSAGES)
    pubs = sources.create("discord", salons="1", jeton=JETON).lire()
    assert (pubs[0].ticker, pubs[0].symbole) == ("BTC", "BTCUSDT")
    assert pubs[0].direction is Direction.LONG
    assert pubs[0].classification is Classification.TRADE_SIGNAL
    assert pubs[1].classification is Classification.EDUCATIONAL


def test_le_self_bot_n_est_PAS_implemente():
    """Lire avec un jeton UTILISATEUR fait bannir le compte. Le code s'y refuse."""
    from pathlib import Path
    code = Path("packages/social/sources/discord.py").read_text()
    assert 'f"Bot {self._jeton}"' in code, "l'en-tête doit déclarer un BOT"
    assert "Authorization\": self._jeton" not in code
