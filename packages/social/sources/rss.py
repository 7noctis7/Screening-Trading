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
# Un flux joint ses visuels de trois façons selon le générateur : <enclosure>,
# <media:content>, ou une <img> dans la description. N'en lire qu'une perdrait les
# messages dont le graphique EST le contenu, sans que rien ne le signale.
_IMG_HTML = re.compile(r"<img[^>]+src=['\"]([^'\"]+)", re.I)
_IMAGE = re.compile(r"^image/", re.I)
_COMPTE_URL = re.compile(r"(?:^|/)@?([A-Za-z0-9_]{1,15})(?:/|$)")
# Dublin Core : le champ STANDARD de l'auteur d'un élément, que les générateurs de flux
# X renseignent. Seul un pseudonyme EXPLICITE (« @handle ») est comparé. Le « @ » n'est
# pas décoratif : sans lui, un nom affiché d'un seul mot (« MacroAlf » pour micro2macr0)
# passait pour un pseudonyme, et TOUS les messages du compte étaient écartés comme
# des reprises. Relevé en revue de #408.
_DC_AUTEUR = "{http://purl.org/dc/elements/1.1/}creator"
_PSEUDO = re.compile(r"^@([A-Za-z0-9_]{1,15})$")


@sources.register("rss")
class SourceRSS:
    """`flux` : URL séparées par des virgules, sinon `QUANT_X_RSS`."""

    def __init__(self, flux: str | None = None, compte: str | None = None) -> None:
        brut = flux or os.environ.get("QUANT_X_RSS") or ""
        self.flux = [u.strip() for u in brut.split(",") if u.strip()]
        self.compte = compte
        self.rejets: list[str] = []

    @property
    def configuree(self) -> bool:
        return bool(self.flux)

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
        propres, note = _sans_reprises(items, compte, sur=self.compte is not None)
        if note:
            self.rejets.append(f"{url} : {note}")
        lues = (_publication(i, compte) for i in propres)
        gardes = [p for p in lues if p is not None]
        ecartes = len(propres) - len(gardes)
        if ecartes:
            self.rejets.append(
                f"{url} : {ecartes} élément(s) écarté(s) — sans lien, sans texte, ou "
                "sans pubDate lisible. Une date inventée les mettrait en tête.")
        return gardes


def _auteur(item) -> str | None:
    """Le pseudonyme EXPLICITE de l'auteur déclaré, en minuscules — sinon `None`."""
    n = item.find(_DC_AUTEUR)
    m = _PSEUDO.match((n.text or "").strip()) if n is not None else None
    return m.group(1).lower() if m else None


def _sans_reprises(items: list, compte: str, sur: bool) -> tuple[list, str | None]:
    """Écarte les éléments dont l'AUTEUR déclaré n'est pas le compte du flux.

    Vérifié sur le gabarit de Nitter (moteur de twiiit, xcancel…) : pour un retweet,
    l'élément porte le texte et le lien du tweet D'ORIGINE, et `dc:creator` nomme son
    auteur. Sans ce tri, le signal d'un inconnu retweeté par trendspider entrait dans
    la base comme un signal DE trendspider (AGENTS.md §9).

    MAIS LE COMPTE DU FLUX EST SOUVENT DEVINÉ, pas su : `_compte_depuis` lit l'URL, et
    une URL opaque (`…/feeds/AbCdEf123.xml`) rend « feeds ». Trier sur un compte deviné
    écarterait alors TOUT le flux (relevé en revue de #408). Le tri n'a donc lieu que si
    le compte est donné explicitement, ou CONFIRMÉ par le flux lui-même — au moins un
    élément signé de sa main. Sinon on garde tout, et on le DIT.
    """
    auteurs = [_auteur(i) for i in items]
    cible = compte.lstrip("@").lower()
    if not sur and cible not in auteurs:
        if any(auteurs):
            return items, (f"compte « {compte} » deviné de l'URL et jamais signataire "
                           "dans le flux — reprises NON triées, faute de savoir.")
        return items, None
    propres = [i for i, a in zip(items, auteurs, strict=True) if a in (None, cible)]
    n = len(items) - len(propres)
    if not n:
        return propres, None
    return propres, (f"{n} reprise(s) d'autres comptes écartée(s) — un retweet "
                     f"n'est pas un message de {compte} (AGENTS.md §9).")


def _texte(item, balise: str) -> str:
    n = item.find(balise)
    return "" if n is None or n.text is None else n.text.strip()


def _compte_depuis(url: str) -> str:
    """Le compte se déduit de l'URL du flux, jamais d'un rang ni d'un défaut muet."""
    chemin = url.split("?")[0].rstrip("/").removesuffix("/rss")
    trouve = _COMPTE_URL.findall(chemin)
    return trouve[-1] if trouve else "inconnu"


def _quand(item) -> datetime | None:
    """`None` plutôt que `datetime.now()`. INVENTER UNE DATE EST PIRE QUE REFUSER.

    Un élément sans `pubDate` daté de maintenant s'affiche comme le plus récent — donc
    en tête, à l'endroit le plus lu — et `INSERT OR REPLACE` le rajeunit à chaque
    ingestion. Un vieux billet deviendrait ainsi éternellement la dernière nouvelle.
    """
    brut = _texte(item, "pubDate")
    if not brut:
        return None
    try:
        d = parsedate_to_datetime(brut)
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _images(item, brut: str) -> tuple[str, ...]:
    """Les trois emplacements possibles, dédoublonnés en gardant l'ordre de lecture."""
    urls: list[str] = []
    for n in item.findall("enclosure"):
        if _IMAGE.match(n.get("type") or "") and n.get("url"):
            urls.append(n.get("url"))
    for n in item.iter():
        est_media = n.tag.endswith("content") and _IMAGE.match(n.get("type") or "")
        if est_media and n.get("url"):
            urls.append(n.get("url"))
    urls += _IMG_HTML.findall(brut)
    return tuple(dict.fromkeys(urls))


def _publication(item, compte: str) -> Publication | None:
    lien = _texte(item, "link")
    brut = _texte(item, "description") or _texte(item, "title")
    texte = _BALISES.sub("", brut).strip()
    ts = _quand(item)
    images = _images(item, brut)
    if not lien or ts is None or (not texte and not images):
        return None
    if not texte:
        texte = f"[{len(images)} image(s) sans texte]"
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=lien, compte=compte.lstrip("@"), ts=ts, texte=texte,
        classification=extraction.classification(texte), ticker=tick, symbole=sym,
        direction=extraction.direction(texte), url=lien, images=images)
