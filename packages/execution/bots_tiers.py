"""Bots TIERS : les comptes Alpaca paper d'AUTRES robots, lus comme des benchmarks.

CE QUE C'EST. Un second robot de trading (« XIII indic ») tourne sur son propre compte
Alpaca paper. On veut le voir à côté du nôtre : sa courbe sur le tableau de bord, ses
positions sur « Mes positions ». C'est une RÉFÉRENCE de plus, comme le S&P 500 — pas une
poche du portefeuille.

TROIS RÈGLES, et elles sont testées.

1. **LECTURE SEULE.** Ce module n'appelle que `equity`, `positions_detailed` et
   `portfolio_history`. Aucun ordre, aucune clôture, aucune annulation : le compte d'un
   autre robot ne se pilote pas d'ici. `run_live.py` ne l'importe pas.
2. **JAMAIS DANS LE TOTAL.** Ses positions et son equity restent dans leur propre bloc.
   Additionnées au robot, elles feraient mesurer au tableau de bord deux stratégies à la
   fois — et le benchmark disparaîtrait dans ce qu'il est censé juger.
3. **UN COMPTE SÉPARÉ, OU RIEN.** Si les clés du bot sont celles du robot, ce n'est pas
   un benchmark : c'est le même compte compté deux fois. On le DIT et on ne lit rien.
   (Sur un compte partagé, `run_live` solde chaque jour ce qui n'est pas dans ses
   cibles : les positions de l'autre bot y seraient liquidées.)

AJOUTER UN BOT = une ligne dans `BOTS` et deux variables dans `.env`. Les clés restent
locales (dépôt public) : le build du site en ligne ne les a pas, il n'affiche donc rien.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class BotTiers:
    cle: str            # identifiant stable dans les payloads
    nom: str            # nom affiché — aussi la clé de couleur du front (lib/couleurs)
    env_cle: str
    env_secret: str

    def cles(self) -> tuple[str, str]:
        return (os.environ.get(self.env_cle, "").strip(),
                os.environ.get(self.env_secret, "").strip())

    def configure(self) -> bool:
        return all(self.cles())

    def meme_compte_que_le_robot(self) -> bool:
        """Mêmes clés que le compte du robot (`ALPACA_API_KEY`) → même compte."""
        robot = os.environ.get("ALPACA_API_KEY", "").strip()
        return bool(robot) and self.cles()[0] == robot


BOTS: tuple[BotTiers, ...] = (
    BotTiers("xiii", "XIII indic", "ALPACA_XIII_API_KEY", "ALPACA_XIII_API_SECRET"),
)


def _alpaca(bot: BotTiers):
    from packages.execution.alpaca_broker import AlpacaBroker
    cle, secret = bot.cles()
    return AlpacaBroker(api_key=cle, api_secret=secret, paper=True)


def lire(bot: BotTiers, historique: bool = True,
         fabrique: Callable[[BotTiers], object] | None = None) -> dict:
    """État d'un bot tiers. `ok=False` + `error` nommée plutôt qu'un zéro silencieux."""
    d = {"cle": bot.cle, "nom": bot.nom, "configure": bot.configure(), "ok": False,
         "equity": None, "positions": [], "history": [], "error": None}
    if not d["configure"]:
        d["error"] = f"clés absentes (.env) : {bot.env_cle}, {bot.env_secret}"
        return d
    if bot.meme_compte_que_le_robot():
        d["error"] = ("mêmes clés que le compte du robot : ce n'est pas un compte "
                      "séparé, donc pas un benchmark")
        return d
    try:
        b = (fabrique or _alpaca)(bot)
        d["equity"] = round(float(b.equity()), 2)
        d["positions"] = b.positions_detailed()
        if historique:
            d["history"] = b.portfolio_history()
        d["ok"] = True
    except Exception as e:  # noqa: BLE001 — un bot muet ne fait pas tomber la page
        d["error"] = f"{type(e).__name__}: {str(e)[:140]}"
    return d


def lire_tous(historique: bool = True,
              fabrique: Callable[[BotTiers], object] | None = None) -> list[dict]:
    """Les bots CONFIGURÉS seulement : sans clés, hors périmètre — pas en panne."""
    return [lire(b, historique, fabrique) for b in BOTS if b.configure()]
