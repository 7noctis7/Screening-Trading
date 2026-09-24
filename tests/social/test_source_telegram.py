"""Un canal SANS APERÇU rend une page valide et vide — comme un canal qui se tait.

Privé, supprimé, renommé, ou aperçu désactivé : les quatre rendent `200 OK` avec zéro
message. C'est indiscernable de « rien publié cette semaine », et c'est ainsi qu'un flux
se tarit pendant des mois sans que personne ne s'en aperçoive. Chaque cas est NOMMÉ.

L'autre piège est propre à cette source : LE CANAL N'EST PAS LE COMPTE.
« crypto_eliz883 »
sur Telegram est le compte X « eliz883 ». Laisser le nom du canal dans la colonne
« compte » casserait le filtre, où l'utilisateur cherche les pseudos X qu'il connaît.
"""
from __future__ import annotations

import urllib.error

import pytest

from packages.social.modele import Classification, Direction
from packages.social.sources import charger_plugins, sources

PAGE = """<html><body>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="crypto_eliz883/101">
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      BTCUSDT long &amp; solide<br/>Entrée 64000, SL 61000, TP1 68000
    </div>
    <a class="tgme_widget_message_date" href="https://t.me/crypto_eliz883/101">
      <time datetime="2026-09-24T10:00:00+00:00" class="time">10:00</time></a>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message js-widget_message" data-post="crypto_eliz883/102">
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      Rappel : comment lire un carnet d&#39;ordres
    </div>
    <a class="tgme_widget_message_date" href="https://t.me/crypto_eliz883/102">
      <time datetime="2026-09-24T09:00:00+00:00" class="time">09:00</time></a>
  </div>
</div>
</body></html>"""

SANS_APERCU = """<html><body><div class="tgme_page">
<div class="tgme_page_title">Canal privé</div></div></body></html>"""


@pytest.fixture(autouse=True)
def _plugins():
    charger_plugins()


def _brancher(monkeypatch, charge):
    import packages.social.sources.telegram as T

    def faux(requete, timeout=None):  # noqa: ARG001
        if isinstance(charge, Exception):
            raise charge
        import io
        rep = io.BytesIO(charge.encode())
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(T.urllib.request, "urlopen", faux)


def test_l_apercu_public_donne_les_messages(monkeypatch):
    _brancher(monkeypatch, PAGE)
    src = sources.create("telegram", canaux="crypto_eliz883")
    pubs = src.lire()
    assert len(pubs) == 2 and src.rejets == []
    assert pubs[0].texte.startswith("BTCUSDT long & solide")
    assert "Entrée 64000" in pubs[0].texte      # le <br/> est préservé


def test_le_CANAL_n_est_pas_le_COMPTE(monkeypatch):
    """« crypto_eliz883 » doit se ranger sous « eliz883 », le pseudo que l'on filtre."""
    _brancher(monkeypatch, PAGE)
    src = sources.create("telegram", canaux="crypto_eliz883:eliz883")
    assert {p.compte for p in src.lire()} == {"eliz883"}


def test_sans_correspondance_le_compte_retombe_sur_le_canal(monkeypatch):
    _brancher(monkeypatch, PAGE)
    src = sources.create("telegram", canaux="crypto_eliz883")
    assert {p.compte for p in src.lire()} == {"crypto_eliz883"}


def test_un_canal_SANS_APERCU_est_nomme_et_non_confondu_avec_un_canal_muet(monkeypatch):
    _brancher(monkeypatch, SANS_APERCU)
    src = sources.create("telegram", canaux="prive")
    assert src.lire() == []
    assert "aperçu désactivé" in src.rejets[0]


def test_un_canal_INJOIGNABLE_est_nomme(monkeypatch):
    _brancher(monkeypatch, urllib.error.URLError("hôte inconnu"))
    src = sources.create("telegram", canaux="disparu")
    assert src.lire() == []
    assert len(src.rejets) == 1 and "disparu" in src.rejets[0]


def test_l_identifiant_est_le_LIEN_donc_relire_ne_duplique_pas(monkeypatch):
    _brancher(monkeypatch, PAGE)
    src = sources.create("telegram", canaux="crypto_eliz883")
    assert [p.id for p in src.lire()] == [p.id for p in src.lire()]
    assert src.lire()[0].id == "https://t.me/crypto_eliz883/101"


def test_l_extraction_pre_remplit_depuis_le_texte(monkeypatch):
    _brancher(monkeypatch, PAGE)
    pubs = sources.create("telegram", canaux="crypto_eliz883").lire()
    assert (pubs[0].ticker, pubs[0].symbole) == ("BTC", "BTCUSDT")
    assert pubs[0].direction is Direction.LONG
    assert pubs[0].classification is Classification.TRADE_SIGNAL
    assert pubs[1].classification is Classification.EDUCATIONAL


def test_plusieurs_canaux_se_donnent_separes_par_une_virgule(monkeypatch):
    _brancher(monkeypatch, PAGE)
    src = sources.create("telegram", canaux="crypto_eliz883:eliz883, walshwealth1122")
    assert len(src.lire()) == 4          # la fixture est servie pour les deux
    assert {c for _, c in src.cibles} == {"eliz883", "walshwealth1122"}
