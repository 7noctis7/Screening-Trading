"""Un miroir MORT et un compte SILENCIEUX rendent la même chose : rien.

C'est le piège propre aux flux gratuits. Les instances qui republient X meurent
régulièrement — c'est leur nature, elles dépendent du bon vouloir de X — et une
instance éteinte rend une erreur réseau, une page d'excuse ou un XML sans élément.
Les trois ressemblent trait pour trait à « ce compte n'a rien publié depuis hier ».
Confondus, ils laissent l'onglet se vider en silence pendant des semaines.

Ce que ces tests épinglent :
  1. un flux vide ou injoignable est NOMMÉ dans `rejets`, pas avalé ;
  2. l'identifiant vient du LIEN, jamais du rang — sinon chaque passage recréerait
     les mêmes publications sous de nouveaux identifiants ;
  3. le compte se déduit de l'URL du flux, pas d'un défaut muet ;
  4. les balises HTML de la description sont retirées ;
  5. aucun fournisseur n'est codé en dur : les URL viennent de la configuration.
"""
from __future__ import annotations

import io
import urllib.error

import pytest

from packages.social.sources import charger_plugins, sources

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>t1</title><link>https://x.com/astekz/status/111</link>
<description>&lt;p&gt;BTCUSDT long, TP1 65000&lt;/p&gt;</description>
<pubDate>Wed, 24 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>t2</title><link>https://x.com/astekz/status/222</link>
<description>Rappel sur les volumes</description>
<pubDate>Wed, 24 Sep 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

VIDE = """<?xml version="1.0"?><rss><channel><title>rien</title></channel></rss>"""


@pytest.fixture(autouse=True)
def _plugins():
    charger_plugins()


def _brancher(monkeypatch, charge: str | Exception):
    import packages.social.sources.rss as R

    def faux(requete, timeout=None):  # noqa: ARG001
        if isinstance(charge, Exception):
            raise charge
        rep = io.BytesIO(charge.encode())
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(R.urllib.request, "urlopen", faux)


def test_un_flux_lisible_donne_des_publications(monkeypatch):
    _brancher(monkeypatch, RSS)
    src = sources.create("rss", flux="https://miroir.test/astekz/rss")
    pubs = src.lire()
    assert len(pubs) == 2 and src.rejets == []
    assert pubs[0].compte == "astekz"


def test_l_identifiant_vient_du_LIEN_pas_du_RANG(monkeypatch):
    """Un flux republie les mêmes éléments : numéroter en recréerait à chaque fois."""
    _brancher(monkeypatch, RSS)
    src = sources.create("rss", flux="https://miroir.test/astekz/rss")
    ids_1 = [p.id for p in src.lire()]
    ids_2 = [p.id for p in src.lire()]
    assert ids_1 == ids_2 == ["https://x.com/astekz/status/111",
                              "https://x.com/astekz/status/222"]


def test_un_miroir_MORT_est_nomme_et_non_confondu_avec_un_compte_muet(monkeypatch):
    _brancher(monkeypatch, urllib.error.URLError("connexion refusée"))
    src = sources.create("rss", flux="https://mort.test/astekz/rss")
    assert src.lire() == []
    assert len(src.rejets) == 1 and "mort.test" in src.rejets[0]


def test_un_flux_SANS_element_est_signale_lui_aussi(monkeypatch):
    """XML valide mais vide : l'instance répond encore, elle ne sert plus rien."""
    _brancher(monkeypatch, VIDE)
    src = sources.create("rss", flux="https://eteint.test/astekz/rss")
    assert src.lire() == []
    assert "sans élément" in src.rejets[0]


def test_les_balises_HTML_de_la_description_sont_retirees(monkeypatch):
    _brancher(monkeypatch, RSS)
    texte = sources.create("rss", flux="https://m.test/astekz/rss").lire()[0].texte
    assert "<p>" not in texte and texte.startswith("BTCUSDT long")


def test_l_extraction_pre_remplit_depuis_le_texte(monkeypatch):
    _brancher(monkeypatch, RSS)
    p = sources.create("rss", flux="https://m.test/astekz/rss").lire()[0]
    assert (p.ticker, p.symbole) == ("BTC", "BTCUSDT")
    assert str(p.classification) == "TRADE_SIGNAL"


def test_le_compte_se_deduit_de_l_URL_du_flux(monkeypatch):
    _brancher(monkeypatch, RSS)
    cas = [("https://m.test/trendspider/rss", "trendspider"),
           ("https://m.test/@eliz883", "eliz883"),
           ("https://exemple.test/twitter/user/micro2macr0", "micro2macr0")]
    for url, attendu in cas:
        src = sources.create("rss", flux=url)
        assert src.lire()[0].compte == attendu


def test_aucun_fournisseur_n_est_code_EN_DUR():
    """Coder « nitter.net » dans le module reviendrait à le dater."""
    from pathlib import Path
    code = Path("packages/social/sources/rss.py").read_text()
    corps = "\n".join(x for x in code.splitlines() if not x.strip().startswith("#"))
    corps = corps.split('"""')[-1]        # hors docstring de module
    for fournisseur in ("nitter.net", "xcancel.com", "rsshub.app", "rss.app"):
        assert fournisseur not in corps, f"{fournisseur} codé en dur"


# ── Reprises (retweets) ─────────────────────────────────────────────────────────────
# Forme relevée sur le gabarit de Nitter (src/views/rss.nimf), moteur de twiiit : pour
# un retweet, l'élément porte le texte et le lien du tweet D'ORIGINE, le titre préfixé
# « RT by @compte: », et `dc:creator` nomme l'auteur d'origine.
AVEC_REPRISE = """<?xml version="1.0"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item><title>propre</title><dc:creator>@trendspider</dc:creator>
<link>https://x.com/trendspider/status/1</link>
<description>SPY breakout above 580</description>
<pubDate>Wed, 24 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>RT by @trendspider: BTC long now</title><dc:creator>@inconnu42</dc:creator>
<link>https://x.com/inconnu42/status/2</link>
<description>BTCUSDT long, TP1 70000</description>
<pubDate>Wed, 24 Sep 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_un_RETWEET_n_est_pas_range_sous_le_compte_qui_le_reprend(monkeypatch):
    """Le signal d'un inconnu entrait comme un signal DE trendspider."""
    _brancher(monkeypatch, AVEC_REPRISE)
    src = sources.create("rss", flux="https://miroir.test/trendspider/rss")
    pubs = src.lire()
    assert [p.url for p in pubs] == ["https://x.com/trendspider/status/1"]


def test_une_reprise_ecartee_est_COMPTEE_et_NOMMEE(monkeypatch):
    _brancher(monkeypatch, AVEC_REPRISE)
    src = sources.create("rss", flux="https://miroir.test/trendspider/rss")
    src.lire()
    assert any("1 reprise(s)" in r and "trendspider" in r for r in src.rejets)


def test_l_auteur_se_compare_SANS_la_casse(monkeypatch):
    """« @TrendSpider » est le même compte que « trendspider » dans l'URL."""
    _brancher(monkeypatch, AVEC_REPRISE.replace("@trendspider</dc", "@TrendSpider</dc"))
    pubs = sources.create("rss", flux="https://miroir.test/trendspider/rss").lire()
    assert len(pubs) == 1


def test_un_NOM_AFFICHE_ne_fait_rien_ecarter(monkeypatch):
    """« Trend Spider » n'est pas un pseudonyme : le comparer viderait un flux."""
    flux = AVEC_REPRISE.replace("@inconnu42", "Un Nom Affiché")
    _brancher(monkeypatch, flux)
    pubs = sources.create("rss", flux="https://miroir.test/trendspider/rss").lire()
    assert len(pubs) == 2


def test_un_flux_SANS_auteur_declare_garde_tout(monkeypatch):
    """Sans `dc:creator`, on ne sait pas : écarter sur un doute serait muet."""
    _brancher(monkeypatch, RSS)
    assert len(sources.create("rss", flux="https://miroir.test/astekz/rss").lire()) == 2
