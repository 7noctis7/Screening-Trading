"""Un miroir MORT répond souvent 200. C'est ce qui rend le sondage nécessaire.

Une instance éteinte sert une page d'excuse, ou un flux valide sans le moindre élément.
Juger sur le code HTTP conclurait donc « vivant » sur une source qui ne rend rien — et
l'utilisateur configurerait un miroir inutile en croyant l'avoir mesuré.

Ce que ces tests épinglent :
  1. le verdict repose sur le NOMBRE D'ÉLÉMENTS, jamais sur le code HTTP ;
  2. un XML valide mais vide est un échec, pas une réussite silencieuse ;
  3. une réponse non-XML (page d'excuse) est nommée comme telle ;
  4. aucun miroir n'est imposé : la liste est un point de départ remplaçable en ligne
     de commande, et le module de SOURCE, lui, n'en connaît toujours aucun.
"""
from __future__ import annotations

import io
import urllib.error

from scripts.x_miroirs import CANDIDATS, sonder

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>a</title></item><item><title>b</title></item></channel></rss>"""
VIDE = """<?xml version="1.0"?><rss><channel><title>rien</title></channel></rss>"""
EXCUSE = "<html><body>Instance temporairement indisponible</body></html>"


def _brancher(monkeypatch, charge):
    import scripts.x_miroirs as M

    def faux(requete, timeout=None):  # noqa: ARG001
        if isinstance(charge, Exception):
            raise charge
        rep = io.BytesIO(charge.encode())
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(M.urllib.request, "urlopen", faux)


def test_un_flux_lisible_compte_ses_elements(monkeypatch):
    _brancher(monkeypatch, RSS)
    assert sonder("https://m.test/a/rss") == (2, "ok")


def test_un_XML_VALIDE_mais_VIDE_est_un_echec_pas_un_silence(monkeypatch):
    """C'est le cas qui piège : 200 OK, XML correct, et rien à lire."""
    _brancher(monkeypatch, VIDE)
    n, motif = sonder("https://m.test/a/rss")
    assert n == 0 and motif == "flux vide"


def test_une_page_d_excuse_est_NOMMEE_et_non_comptee_comme_un_flux(monkeypatch):
    """Une page d'excuse minimale est du XML PARFAITEMENT VALIDE : sans regarder la
    racine, elle passait pour un « flux vide », indiscernable d'un compte muet."""
    _brancher(monkeypatch, EXCUSE)
    n, motif = sonder("https://m.test/a/rss")
    assert n == 0 and "pas un flux" in motif


def test_un_XML_CASSE_est_distingue_d_une_page_qui_n_est_pas_un_flux(monkeypatch):
    _brancher(monkeypatch, "<rss><channel>jamais fermé")
    n, motif = sonder("https://m.test/a/rss")
    assert n == 0 and "illisible" in motif


def test_un_refus_HTTP_porte_son_code(monkeypatch):
    _brancher(monkeypatch, urllib.error.HTTPError(
        url="https://m.test", code=429, msg="trop de requêtes", hdrs=None, fp=None))
    assert sonder("https://m.test/a/rss") == (0, "HTTP 429")


def test_une_panne_reseau_ne_fait_pas_tomber_le_sondage(monkeypatch):
    """Sonder six miroirs dont un injoignable doit rendre cinq résultats, pas zéro."""
    _brancher(monkeypatch, urllib.error.URLError("hôte inconnu"))
    assert sonder("https://mort.test/a/rss") == (0, "URLError")


def test_les_candidats_sont_un_POINT_DE_DEPART_pas_une_recommandation():
    """Chacun porte {compte} : la liste se remplace entièrement en ligne de commande."""
    assert all("{compte}" in c for c in CANDIDATS)
    assert len(CANDIDATS) >= 3, "un seul candidat ne se sonde pas, il se subit"


def test_le_module_de_SOURCE_ne_connait_toujours_AUCUN_fournisseur():
    """Le sondeur a le droit de nommer des miroirs — c'est son objet. `rss.py` non :
    en coder un le daterait, et c'est précisément ce que ce sondeur évite."""
    from pathlib import Path
    code = Path("packages/social/sources/rss.py").read_text()
    corps = code.split('"""')[-1]        # hors docstring de module
    for hote in ("nitter", "xcancel", "twiiit", "openrss", "rsshub"):
        assert hote not in corps, f"{hote} codé en dur dans la source"
