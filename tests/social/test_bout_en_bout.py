"""La question de l'utilisateur, posée au code : « les canaux Telegram arriveront-ils
bien dans l'onglet X ? »

Chaque maillon est testé séparément — la source lit, le store écrit, les filtres
filtrent, la route sert. Mais une chaîne dont chaque maillon est bon peut être rompue :
il suffit qu'un champ change de nom entre deux étages. Ce test parcourt la chaîne
ENTIÈRE, du HTML de l'aperçu Telegram jusqu'à la charge que le navigateur reçoit, et
n'admet qu'une seule simulation : l'appel réseau lui-même.

Il épingle en particulier la correspondance `canal:compte`. `crypto_eliz883` doit
apparaître sous `eliz883` — le pseudo que l'utilisateur connaît et sur lequel il filtre.
Sans elle, le filtre par compte proposerait des noms de canaux méconnaissables, et
chercher « eliz883 » ne rendrait rien alors que ses messages sont là.
"""
from __future__ import annotations

import io

import pytest

from apps.api.social_x import construire_filtre, publications
from packages.social.sources import charger_plugins, sources
from packages.social.store import StorePublications


def _page(canal: str, num: int, texte: str, quand: str) -> str:
    return f"""<html><body><div class="tgme_widget_message_wrap">
    <div class="tgme_widget_message" data-post="{canal}/{num}">
      <div class="tgme_widget_message_text">{texte}</div>
      <div class="tgme_widget_message_footer"><a class="tgme_widget_message_date">
        <time datetime="{quand}"></time></a></div>
    </div></div></body></html>"""


PAGES = {
    "crypto_eliz883": _page("crypto_eliz883", 101,
                            "BTCUSDT long — entrée 64000, SL 61000, TP1 68000",
                            "2026-09-24T10:00:00+00:00"),
    "walshwealth1122": _page("walshwealth1122", 7, "SHORT Ethereum, support cassé",
                             "2026-09-24T09:15:00+00:00"),
}


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Ingère les deux canaux dans une base neuve. Seul le réseau est simulé."""
    import packages.social.sources.telegram as T

    def faux(requete, timeout=None):  # noqa: ARG001
        rep = io.BytesIO(PAGES[requete.full_url.rsplit("/", 1)[-1]].encode())
        rep.__enter__ = lambda: rep      # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(T.urllib.request, "urlopen", faux)
    charger_plugins()
    src = sources.create("telegram", canaux="crypto_eliz883:eliz883,walshwealth1122")
    chemin = str(tmp_path / "x.db")
    store = StorePublications(chemin)
    store.ecrire(src.lire())
    store.close()
    return chemin


def test_les_canaux_telegram_arrivent_bien_dans_l_onglet(base):
    r = publications(construire_filtre(), db=base)
    assert r["disponible"] is True
    assert r["n"] == 2


def test_le_CANAL_apparait_sous_le_PSEUDO_que_l_utilisateur_filtre(base):
    """`crypto_eliz883` → `eliz883`. Sinon chercher « eliz883 » ne rendrait rien."""
    r = publications(construire_filtre(), db=base)
    assert r["comptes"] == ["eliz883", "walshwealth1122"]
    assert publications(construire_filtre(accounts="eliz883"), db=base)["n"] == 1


def test_les_filtres_se_combinent_sur_de_la_DONNEE_TELEGRAM(base):
    r = publications(construire_filtre(accounts="eliz883", q="BTC"), db=base)
    assert r["n"] == 1
    assert "BTCUSDT" in r["publications"][0]["texte"]


def test_la_recherche_retrouve_un_NIVEAU_extrait_du_message_telegram(base):
    """« 68000 » est un TP1 du texte : l'extraction puis la recherche le retrouvent."""
    assert publications(construire_filtre(q="68000"), db=base)["n"] == 1


def test_l_horodatage_TELEGRAM_survit_a_toute_la_chaine(base):
    """Le défaut trouvé en revue portait exactement là — jusqu'à la charge servie."""
    r = publications(construire_filtre(accounts="eliz883"), db=base)
    assert r["publications"][0]["ts"].startswith("2026-09-24T10:00")


def test_chaque_publication_TELEGRAM_porte_son_verdict(base):
    """AGENTS.md §9 vaut pour toutes les sources, pas seulement pour X."""
    for p in publications(construire_filtre(), db=base)["publications"]:
        assert p["verdict"]["exploitable"] is False
        assert p["verdict"]["niveau_source"] == "E"     # réserve non levée


def test_reingerer_les_memes_canaux_ne_duplique_rien(base, monkeypatch):
    import packages.social.sources.telegram as T

    def faux(requete, timeout=None):  # noqa: ARG001
        rep = io.BytesIO(PAGES[requete.full_url.rsplit("/", 1)[-1]].encode())
        rep.__enter__ = lambda: rep      # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False  # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(T.urllib.request, "urlopen", faux)
    src = sources.create("telegram", canaux="crypto_eliz883:eliz883,walshwealth1122")
    store = StorePublications(base)
    store.ecrire(src.lire())
    store.close()
    assert publications(construire_filtre(), db=base)["n"] == 2
