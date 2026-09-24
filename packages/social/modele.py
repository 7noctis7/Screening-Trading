"""Ce qu'est une publication X dans ce dépôt, et ce qu'elle n'est PAS.

Une publication est un DIRE, jamais une donnée. Le dépôt possède déjà une couche qui
encode cette distinction (`packages/intelligence/classify`) : une opinion d'une source
excellente reste une opinion. Le présent module en est le pendant pour le flux social —
il STOCKE et CLASSE ce qui a été dit, et n'autorise personne à en tirer un ordre.

La taxonomie ci-dessous décrit L'INTENTION DÉCLARÉE d'un message, pas sa véracité :
`TRADE_SIGNAL` veut dire « ce message annonce une prise de position », pas « cette prise
de position est bonne ». Rien dans ce paquet ne doit alimenter `scripts/run_live.py`.

DEUX ABSENCES QUI NE SONT PAS DES VALEURS :
  · `UNKNOWN` = on n'a pas su classer. Ce n'est pas une onzième catégorie, c'est
    l'aveu que la règle n'a pas tranché. Le confondre avec `EDUCATIONAL` — fourre-tout
    plausible — ferait disparaître le doute de l'écran.
  · `direction = None` = le message ne dit pas le sens. Ce n'est NI long NI short, et
    surtout pas « neutre » : un message qui ne dit rien du sens n'a pas d'avis, il n'a
    pas de contenu directionnel du tout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Classification(StrEnum):
    """Intention DÉCLARÉE du message. `UNKNOWN` est un aveu, pas une catégorie."""

    TRADE_SIGNAL = "TRADE_SIGNAL"
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    TRADE_UPDATE = "TRADE_UPDATE"
    CLOSE_POSITION = "CLOSE_POSITION"
    MOVE_STOP = "MOVE_STOP"
    TAKE_PROFIT_UPDATE = "TAKE_PROFIT_UPDATE"
    CANCEL_SIGNAL = "CANCEL_SIGNAL"
    NEWS = "NEWS"
    EDUCATIONAL = "EDUCATIONAL"
    UNKNOWN = "UNKNOWN"


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class Publication:
    """Une publication telle qu'elle a été LUE. Aucun champ n'est deviné.

    `ticker` est le jeton nu (« BTC ») et `symbole` la paire échangeable (« BTCUSDT ») :
    les confondre empêcherait de chercher « BTC » et de trouver aussi les messages qui
    n'écrivent que la paire. Les deux sont facultatifs, et leur absence se dit `None`.

    `extraits` porte les niveaux cités par le message (entrée, TP, SL…) TELS QUELS.
    Ce sont des nombres écrits par un inconnu sur internet, pas des paramètres d'ordre.

    `images` porte les ADRESSES des visuels joints, jamais les visuels eux-mêmes. Rien
    n'est téléchargé ni réhébergé : le navigateur du lecteur va les chercher là où le
    message les a publiés. Un graphique posté en image EST souvent tout le message —
    « [Pièce jointe] Doge Long » sans l'image ne dit rien — mais une adresse peut
    expirer, et une image absente reste préférable à une image recopiée sans droit.
    """

    id: str
    compte: str
    ts: datetime
    texte: str
    classification: Classification = Classification.UNKNOWN
    ticker: str | None = None
    symbole: str | None = None
    direction: Direction | None = None
    extraits: dict[str, float] = field(default_factory=dict)
    url: str | None = None
    images: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.compte:
            raise ValueError(
                "une publication sans identifiant ni compte n'est pas traçable")
