"""Source RSS générique — la voie GRATUITE, qui survit au décès d'un miroir.

L'API X ne permet pas de LIRE gratuitement : son palier libre sert à publier. Les voies
sans frais passent donc par un tiers qui, lui, expose du RSS — une instance Nitter
survivante, xcancel, RSSHub, RSS.app. Ces miroirs MEURENT régulièrement, c'est leur
nature : ils dépendent du bon vouloir de X.

D'où la forme de ce module : il ne connaît AUCUN fournisseur. Il lit une liste d'URL
données en configuration. Quand un miroir tombe, on change une URL — pas une ligne de
code. Coder « nitter.net » en dur reviendrait à dater le fichier.

DEUX GARDE-FOUS QUI VIENNENT DE LA FRAGILITÉ DE LA SOURCE.

1. UN FLUX MORT N'EST PAS UN FLUX VIDE. Une instance éteinte rend une erreur réseau, une
   page HTML d'excuse ou un XML sans item — et les trois ressemblent à « ce compte n'a
   rien publié ». `lire()` les compte dans `rejets` en les NOMMANT, pour que l'écran
   puisse dire « le miroir ne répond plus » plutôt que « rien de neuf ».

2. L'IDENTIFIANT VIENT DU LIEN, PAS DU RANG. Un flux RSS republie les mêmes éléments à
   chaque appel, dans un ordre qui peut changer. Numéroter les publications dans l'ordre
   d'arrivée en créerait de nouvelles à chaque passage ; le lien canonique, lui, est
   stable — et c'est lui qui rend l'ingestion idempotente.

Note d'usage : ces miroirs sont des tiers. Les interroger relève de leurs conditions à
eux, pas de celles de X — mais c'est une zone grise, et un flux gratuit peut disparaître
du jour au lendemain. Telegram, quand le compte y double ses messages, est plus solide.
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from packages.social import extraction
from packages.social.modele import Publication
from packages.social.sources import sources

DELAI_S = 15.0
AGENT = "Mozilla/5.0 (compatible; QuantTerminal/1.0)"
_BALISES = re.compile(r"<[^>]+>")
_COMPTE_URL = re.compile(r"(?:^|/)@?([A-Za-z0-9_]{1,15})(?:/|$)")


@sources.register("rss")
class SourceRSS:
    """`flux` : URL séparées par des virgules, sinon `QUANT_X_RSS`."""

    def __init__(self, flux: str | None = None, compte: str | None = None) -> None:
        brut = flux or os.environ.get("QUANT_X_RSS") or ""
        self.flux = [u.strip() for u in brut.split(",") if u.strip()]
        self.compte = compte
        self.rejets: list[str] = []

    def lire(self) -> list[Publication]:
        self.rejets = []
        publications: list[Publication] = []
        for url in self.flux:
            try:
                publications.extend(self._un_flux(url))
            except (urllib.error.URLError, OSError, ElementTree.ParseError) as e:
                # NOMMER le miroir mort : « rien de neuf » et « plus de miroir » ne
                # doivent jamais s'afficher pareil.
                self.rejets.append(f"{url} : {type(e).__name__} — {e}")
        return publications

    def _un_flux(self, url: str) -> list[Publication]:
        requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(requete, timeout=DELAI_S) as r:  # noqa: S310
            brut = r.read()
        racine = ElementTree.fromstring(brut)
        items = racine.findall(".//item")
        if not items:
            self.rejets.append(
                f"{url} : flux sans élément (miroir éteint ou compte vide)")
            return []
        compte = self.compte or _compte_depuis(url)
        return [p for p in (_publication(i, compte) for i in items) if p is not None]


def _texte(item, balise: str) -> str:
    n = item.find(balise)
    return "" if n is None or n.text is None else n.text.strip()


def _compte_depuis(url: str) -> str:
    """Le compte se déduit de l'URL du flux, jamais d'un rang ni d'un défaut muet."""
    chemin = url.split("?")[0].rstrip("/").removesuffix("/rss")
    trouve = _COMPTE_URL.findall(chemin)
    return trouve[-1] if trouve else "inconnu"


def _quand(item) -> datetime:
    brut = _texte(item, "pubDate")
    if not brut:
        return datetime.now(UTC)
    try:
        d = parsedate_to_datetime(brut)
    except (TypeError, ValueError):
        return datetime.now(UTC)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _publication(item, compte: str) -> Publication | None:
    lien = _texte(item, "link")
    brut = _texte(item, "description") or _texte(item, "title")
    texte = _BALISES.sub("", brut).strip()
    if not lien or not texte:
        return None
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=lien, compte=compte.lstrip("@"), ts=_quand(item), texte=texte,
        classification=extraction.classification(texte), ticker=tick, symbole=sym,
        direction=extraction.direction(texte), url=lien)
