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
import re
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

# Telegram place les visuels en fond CSS, pas en <img> : `background-image:url('…')`
# sur le bloc photo ou sur la vignette vidéo. Les chercher ailleurs ne rendrait rien,
# et un message réduit à son graphique paraîtrait vide.
_FOND = re.compile(r"background-image\s*:\s*url\((['\"]?)(.+?)\1\)")


class _Aperçu(HTMLParser):
    """Extrait (post, horodatage, texte) des blocs `tgme_widget_message`.

    Un analyseur plutôt qu'une expression régulière : le texte d'un message contient des
    balises (`<br>`, liens, emoji) et une regex sur du HTML imbriqué finit toujours par
    couper au mauvais endroit.

    L'ENREGISTREMENT SE FERME AU BLOC MESSAGE, PAS AU BLOC TEXTE. Première version : on
    empilait le message dès que `tgme_widget_message_text` se refermait. Or dans le
    balisage réel, `<time>` est un FRÈRE qui vient APRÈS ce bloc, dans le pied. Chaque
    publication partait donc sans horodatage et héritait de l'heure d'ingestion — la
    chronologie était fausse, et `INSERT OR REPLACE` redatait le même message à chaque
    passage. Le défaut était invisible : mes huit tests vérifiaient le texte, le compte,
    l'identifiant, jamais la date.

    On vide donc le tampon à l'ouverture du message SUIVANT et à la fin du document.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[dict] = []
        self._courant: dict | None = None
        self._profondeur = 0
        self._dans_date = False

    def _clore(self) -> None:
        if self._courant is not None:
            self.messages.append(self._courant)
        self._courant = None
        self._profondeur = 0
        self._dans_date = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        classe = a.get("class", "") or ""
        if a.get("data-post") and "tgme_widget_message " in f"{classe} ":
            self._clore()
            self._courant = {"post": a["data-post"], "ts": None, "texte": [],
                             "images": []}
            return
        if self._courant is None:
            return
        if ("photo_wrap" in classe or "video_thumb" in classe) and a.get("style"):
            fond = _FOND.search(a["style"])
            if fond:
                self._courant["images"].append(fond.group(2))
        if "tgme_widget_message_date" in classe:
            # Cibler la date DU MESSAGE : un en-tête de transfert peut porter un autre
            # `<time>`, et prendre le premier venu daterait le message de sa source.
            self._dans_date = True
        prendre = self._dans_date or not self._courant["ts"]
        if tag == "time" and a.get("datetime") and prendre:
            self._courant["ts"] = a["datetime"]
        if "tgme_widget_message_text" in classe:
            self._profondeur = 1
        elif self._profondeur:
            self._profondeur += 1
        if tag == "br" and self._profondeur:
            self._courant["texte"].append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._dans_date:
            self._dans_date = False
        if self._profondeur:
            self._profondeur -= 1

    def handle_data(self, data: str) -> None:
        if self._profondeur and self._courant is not None:
            self._courant["texte"].append(data)

    def close(self) -> None:
        super().close()
        self._clore()


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
        lecteur.close()
        if not lecteur.messages:
            # NOMMER le cas : privé, supprimé, renommé ou aperçu désactivé rendent tous
            # une page valide sans message — indiscernable de « rien publié ».
            self.rejets.append(
                f"{canal} : aucun message (canal privé, supprimé, ou aperçu désactivé)")
            return []
        gardees = [p for p in (_publication(m, compte) for m in lecteur.messages)
                   if p is not None]
        ecartes = len(lecteur.messages) - len(gardees)
        if ecartes:
            self.rejets.append(
                f"{canal} : {ecartes} message(s) écarté(s) — sans texte ou sans date "
                "lisible. Une date inventée les placerait en tête de liste.")
        return gardees


def _quand(brut: str | None) -> datetime | None:
    """`None` plutôt que `datetime.now()`. INVENTER UNE DATE EST PIRE QUE REFUSER.

    Une date fabriquée place le message en tête de liste — donc à l'endroit le plus lu —
    et `INSERT OR REPLACE` la rafraîchit à chaque ingestion : le même message rajeunit
    indéfiniment. C'est une donnée de marché inventée, ce que le dépôt interdit.
    """
    if not brut:
        return None
    try:
        d = datetime.fromisoformat(brut.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _publication(m: dict, compte: str) -> Publication | None:
    texte = unescape("".join(m["texte"])).strip()
    ts = _quand(m["ts"])
    images = m.get("images") or []
    # UN GRAPHIQUE SEUL EST UN MESSAGE. Écarter les publications sans texte perdrait
    # exactement celles dont tout le contenu est l'image — le cas le plus fréquent chez
    # un compte de signaux. Le texte devient alors une mention, pas une invention.
    if ts is None or (not texte and not images):
        return None
    if not texte:
        texte = f"[{len(images)} image(s) sans texte]"
    lien = f"https://t.me/{m['post']}"
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=lien, compte=compte, ts=ts, texte=texte,
        classification=extraction.classification(texte), ticker=tick, symbole=sym,
        direction=extraction.direction(texte), url=lien,
        images=tuple(dict.fromkeys(m.get("images") or ())))
