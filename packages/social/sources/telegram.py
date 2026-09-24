"""Source Telegram — la page PUBLIQUE d'un canal, sans clé ni compte.

Telegram publie lui-même un aperçu HTML de tout canal public : `https://t.me/s/<canal>`.
Aucune authentification, aucun jeton, aucun risque pour un compte — c'est la page que
n'importe quel visiteur voit. C'est la voie gratuite la plus solide des trois : le RSS
dépend d'un miroir tiers qui peut mourir, l'export navigateur demande un clic, celle-ci
ne dépend que de Telegram.

DEUX CHOIX QUI VIENNENT DE CE QUE LA SOURCE N'EST PAS X.

1. LE CANAL N'EST PAS LE COMPTE. « crypto_eliz883 » sur Telegram est le compte X
   « eliz883 » ; « walshwealth1122 » ne ressemble à rien de connu. Laisser le nom du
   canal dans la colonne « compte » casserait le filtre : l'utilisateur y cherche les
   pseudos X qu'il connaît. La configuration accepte donc `canal:compte`, et retombe sur
   le nom du canal quand la correspondance n'est pas donnée.

2. UN CANAL SANS APERÇU N'EST PAS UN CANAL VIDE. Un canal privé, renommé, supprimé, ou
   dont l'aperçu est désactivé rend une page valide SANS message. C'est indiscernable de
   « rien publié cette semaine » — et c'est ainsi qu'un flux se tarit sans que personne
   ne s'en aperçoive. Chaque cas est NOMMÉ dans `rejets`.

L'identifiant est le lien canonique `t.me/<canal>/<n>`, jamais le rang : la page
republie les mêmes messages à chaque appel, et numéroter ferait mentir l'idempotence.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser

from packages.social import extraction
from packages.social.modele import Publication
from packages.social.sources import sources

DELAI_S = 20.0
AGENT = "Mozilla/5.0 (compatible; QuantTerminal/1.0)"
BASE = "https://t.me/s/"


class _Aperçu(HTMLParser):
    """Extrait (post, horodatage, texte) des blocs `tgme_widget_message`.

    Un analyseur plutôt qu'une expression régulière : le texte d'un message contient des
    balises (`<br>`, liens, emoji) et une regex sur du HTML imbriqué finit toujours par
    couper au mauvais endroit.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[dict] = []
        self._courant: dict | None = None
        self._profondeur = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        classe = a.get("class", "") or ""
        if "tgme_widget_message " in f"{classe} " and a.get("data-post"):
            self._courant = {"post": a["data-post"], "ts": None, "texte": []}
        if self._courant is None:
            return
        if "tgme_widget_message_text" in classe:
            self._profondeur = 1
        elif self._profondeur:
            self._profondeur += 1
        if tag == "time" and a.get("datetime") and not self._courant["ts"]:
            self._courant["ts"] = a["datetime"]
        if tag == "br" and self._profondeur:
            self._courant["texte"].append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._profondeur:
            self._profondeur -= 1
            if self._profondeur == 0 and self._courant is not None:
                self.messages.append(self._courant)
                self._courant = None

    def handle_data(self, data: str) -> None:
        if self._profondeur and self._courant is not None:
            self._courant["texte"].append(data)


def _cibles(brut: str) -> list[tuple[str, str]]:
    """« canal:compte, canal2 » → [(canal, compte)]. Sans « : », compte = canal."""
    sorties = []
    for morceau in brut.split(","):
        item = morceau.strip()
        if not item:
            continue
        canal, _, compte = item.partition(":")
        sorties.append((canal.strip().lstrip("@"), (compte or canal).strip()))
    return sorties


@sources.register("telegram")
class SourceTelegram:
    """`canaux` : « canal[:compte] » séparés par virgules, sinon `QUANT_TG_CANAUX`."""

    def __init__(self, canaux: str | None = None) -> None:
        self.cibles = _cibles(canaux or os.environ.get("QUANT_TG_CANAUX") or "")
        self.rejets: list[str] = []

    def lire(self) -> list[Publication]:
        self.rejets = []
        publications: list[Publication] = []
        for canal, compte in self.cibles:
            try:
                publications.extend(self._un_canal(canal, compte))
            except (urllib.error.URLError, OSError) as e:
                self.rejets.append(f"{canal} : {type(e).__name__} — {e}")
        return publications

    def _un_canal(self, canal: str, compte: str) -> list[Publication]:
        requete = urllib.request.Request(BASE + canal, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(requete, timeout=DELAI_S) as r:  # noqa: S310
            html = r.read().decode("utf-8", "replace")
        lecteur = _Aperçu()
        lecteur.feed(html)
        if not lecteur.messages:
            # NOMMER le cas : privé, supprimé, renommé ou aperçu désactivé rendent tous
            # une page valide sans message — indiscernable de « rien publié ».
            self.rejets.append(
                f"{canal} : aucun message (canal privé, supprimé, ou aperçu désactivé)")
            return []
        return [p for p in (_publication(m, compte) for m in lecteur.messages)
                if p is not None]


def _quand(brut: str | None) -> datetime:
    if not brut:
        return datetime.now(UTC)
    try:
        d = datetime.fromisoformat(brut.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _publication(m: dict, compte: str) -> Publication | None:
    texte = unescape("".join(m["texte"])).strip()
    if not texte:
        return None
    lien = f"https://t.me/{m['post']}"
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=lien, compte=compte, ts=_quand(m["ts"]), texte=texte,
        classification=extraction.classification(texte), ticker=tick, symbole=sym,
        direction=extraction.direction(texte), url=lien)
