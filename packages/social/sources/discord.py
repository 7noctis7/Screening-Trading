"""Source Discord — API BOT officielle. Jamais un jeton utilisateur.

DEUX VOIES PROPRES, ET UNE À NE PAS PRENDRE.

Discord n'expose aucune page publique comparable à `t.me/s/<canal>`. Lire un salon
demande donc un bot, et un bot ne voit que les serveurs où un administrateur l'a INVITÉ.
Avoir rejoint un serveur ne suffit pas.

  1. Le serveur vous appartient, ou son administrateur accepte d'y ajouter votre bot.
  2. Le salon est de type ANNONCES : il se « suit » depuis votre PROPRE serveur, où vous
     êtes admin et où votre bot vit. Les messages y arrivent automatiquement. C'est le
     contournement légitime quand on n'est qu'un membre parmi d'autres.

La troisième voie — lire avec le jeton de son compte utilisateur (« self-bot ») — est
interdite par les conditions de Discord, activement détectée, et sanctionnée par le
BANNISSEMENT du compte. Elle n'est pas implémentée ici et ne doit pas l'être : le compte
perdu serait celui de l'utilisateur.

LE JETON EST UN SECRET, ET LE CODE LE TRAITE COMME TEL. Il vient de l'environnement, ne
s'écrit nulle part, et n'apparaît dans AUCUN message d'erreur — un jeton recopié dans un
rapport d'ingestion, un log ou une réponse d'API est un jeton à révoquer. Les erreurs
d'urllib citent l'URL, jamais les en-têtes ; c'est pour cela qu'elles sont reformulées.

TROIS REFUS QUI NE SE RESSEMBLENT PAS, et que Discord distingue par son code HTTP :
  · 401 — le jeton est absent, faux ou révoqué ;
  · 403 — le bot n'est pas dans ce serveur, ou n'a pas le droit de lire l'historique ;
  · 404 — le salon n'existe pas, ou le bot ne le voit pas.
Les fondre en « aucun message » enverrait chercher un problème de flux là où il y a un
problème de permission. Chacun est NOMMÉ.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime

from packages.social import extraction
from packages.social.modele import Publication
from packages.social.sources import sources

API = "https://discord.com/api/v10"
DELAI_S = 20.0
LIMITE = 100

_MOTIFS = {
    401: "jeton absent, faux ou révoqué (DISCORD_BOT_TOKEN)",
    403: "le bot n'est pas dans ce serveur, ou n'a pas le droit de lire l'historique",
    404: "salon introuvable, ou invisible pour ce bot",
    429: "limite de débit atteinte — réessayer plus tard",
}


def _cibles(brut: str) -> list[tuple[str, str]]:
    """« id:compte, id2 » → [(salon, compte)]. Sans « : », compte = identifiant."""
    sorties = []
    for morceau in brut.split(","):
        item = morceau.strip()
        if not item:
            continue
        salon, _, compte = item.partition(":")
        sorties.append((salon.strip(), (compte or salon).strip()))
    return sorties


@sources.register("discord")
class SourceDiscord:
    """`salons` : « id[:compte] » par virgules, sinon `QUANT_DISCORD_SALONS`."""

    def __init__(self, salons: str | None = None, jeton: str | None = None) -> None:
        self.cibles = _cibles(salons or os.environ.get("QUANT_DISCORD_SALONS") or "")
        self._jeton = jeton or os.environ.get("DISCORD_BOT_TOKEN") or ""
        self.rejets: list[str] = []

    def _sans_secret(self, texte: str) -> str:
        """Le dernier filet AVANT d'écrire quoi que ce soit.

        Une `URLError` porte le message que la pile réseau lui a donné, une
        `HTTPError` porte l'URL. Les relayer tels quels a suffi à faire fuiter le
        jeton — un test l'a attrapé. C'est la fuite la plus banale : on croit
        rapporter une panne, on recopie un secret. Rien ne sort d'ici sans passer
        par cette fonction.
        """
        return texte.replace(self._jeton, "***") if self._jeton else texte

    def lire(self) -> list[Publication]:
        self.rejets = []
        if not self._jeton:
            # DIRE l'absence de jeton plutôt que boucler sur des 401 : la cause est
            # ici, pas chez Discord, et le message doit envoyer au bon endroit.
            self.rejets.append(
                "DISCORD_BOT_TOKEN absent — aucun appel tenté. Créer une application "
                "sur discord.com/developers, puis inviter le bot sur le serveur.")
            return []
        publications: list[Publication] = []
        for salon, compte in self.cibles:
            try:
                publications.extend(self._un_salon(salon, compte))
            except urllib.error.HTTPError as e:
                motif = _MOTIFS.get(e.code, f"HTTP {e.code}")
                self._rejeter(f"salon {salon} : {motif}")
            except (urllib.error.URLError, OSError, ValueError) as e:
                self._rejeter(f"salon {salon} : {type(e).__name__} — {e}")
        return publications

    def _rejeter(self, message: str) -> None:
        self.rejets.append(self._sans_secret(message))

    def _un_salon(self, salon: str, compte: str) -> list[Publication]:
        url = f"{API}/channels/{salon}/messages?limit={LIMITE}"
        requete = urllib.request.Request(url, headers={
            "Authorization": f"Bot {self._jeton}",      # jamais journalisé
            "User-Agent": "QuantTerminal (https://github.com, 1.0)",
        })
        with urllib.request.urlopen(requete, timeout=DELAI_S) as r:  # noqa: S310
            charge = json.loads(r.read().decode("utf-8", "replace"))
        if not charge:
            self._rejeter(f"salon {salon} : aucun message (salon vide ou purgé)")
            return []
        return [p for p in (_publication(m, salon, compte) for m in charge)
                if p is not None]


def _quand(brut: str | None) -> datetime:
    if not brut:
        return datetime.now(UTC)
    try:
        d = datetime.fromisoformat(str(brut).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _publication(m: dict, salon: str, compte: str) -> Publication | None:
    """Un message sans texte (image seule, autocollant) n'est pas une publication."""
    texte = str(m.get("content") or "").strip()
    if not texte or not m.get("id"):
        return None
    ident = f"discord:{salon}/{m['id']}"
    tick, sym = extraction.ticker(texte)
    return Publication(
        id=ident, compte=compte, ts=_quand(m.get("timestamp")), texte=texte,
        classification=extraction.classification(texte), ticker=tick, symbole=sym,
        direction=extraction.direction(texte), url=None)
