"""Deviner le moins possible : ticker, sens, intention — ou l'aveu qu'on ne sait pas.

AUCUN MODÈLE GÉNÉRATIF ICI. Le dépôt interdit qu'un composant LLM se trouve dans une
chaîne de décision ; ce module n'y est pas non plus, mais la raison de s'en passer est
autre : un classifieur qui invente une étiquette plausible est pire qu'un `UNKNOWN`.
L'étiquette fausse se filtre, s'affiche, et se croit. Des règles explicites se lisent,
se testent, et se corrigent.

RÈGLE DE PRUDENCE, appliquée partout : au moindre doute, `UNKNOWN` ou `None`. Un message
qui contient « long » dans « longtemps » n'est pas un signal d'achat ; un message qui
parle de deux actifs n'a pas un ticker, il en a deux — donc aucun ne sera retenu.

Ce module ne sert qu'à PRÉ-REMPLIR. Toute étiquette présente dans la source ingérée
l'emporte : une donnée lue bat toujours une donnée déduite.
"""

from __future__ import annotations

import re

from packages.social.modele import Classification, Direction

# Paires explicites (BTCUSDT) d'abord : moins ambiguës qu'un jeton nu.
_PAIRE = re.compile(r"\b([A-Z]{2,10})(USDT|USDC|USD|PERP)\b")
_CASHTAG = re.compile(r"\$([A-Za-z]{2,10})\b")
_NOMS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "ripple": "XRP",
         "cardano": "ADA", "dogecoin": "DOGE", "litecoin": "LTC"}

# LE GROUPE NON CAPTURANT N'EST PAS DÉCORATIF : sans lui, les lookarounds ne portent
# que sur la PREMIÈRE alternative — « Longtemps » se lisait alors comme « long », et le
# message héritait d'une direction que personne n'avait écrite.
_MOT = r"(?<![\w-])(?:{})(?![\w-])"
_LONG = re.compile(_MOT.format(r"long|longs|achat|buy|bullish|haussier"), re.I)
_SHORT = re.compile(_MOT.format(r"short|shorts|vente|sell|bearish|baissier"), re.I)

# L'ORDRE COMPTE : la première règle qui accroche gagne. Les intentions les plus
# SPÉCIFIQUES passent devant — « je déplace mon stop » est aussi une mise à jour de
# trade, mais le dire `TRADE_UPDATE` perdrait ce qui fait sa valeur.
_REGLES: tuple[tuple[Classification, re.Pattern[str]], ...] = (
    (Classification.CANCEL_SIGNAL, re.compile(r"annul|invalid|cancel|on oublie", re.I)),
    (Classification.MOVE_STOP, re.compile(r"stop (à|a|au|sur|remont|déplac|deplac)"
                                          r"|remonte mon stop|sl (à|a) l'entr", re.I)),
    (Classification.TAKE_PROFIT_UPDATE,
     re.compile(r"\btp\d?\b.*(atteint|touch|pris)|take profit (atteint|touch)", re.I)),
    (Classification.CLOSE_POSITION, re.compile(r"je (clôtur|clotur|ferme|sors)"
                                               r"|position (fermée|fermee|clôturée)"
                                               r"|closed?\b", re.I)),
    (Classification.TRADE_SIGNAL, re.compile(r"\b(entr[ée]e?|entry|je prends|setup)\b"
                                             r"|\bsl\b|\btp\d?\b", re.I)),
    (Classification.TRADE_UPDATE,
     re.compile(r"\b(en cours|toujours en position|update)\b", re.I)),
    (Classification.NEWS,
     re.compile(r"\b(annonce|communiqué|communique|breaking|la fed)\b"
                r"|etf approuv", re.I)),
    (Classification.EDUCATIONAL, re.compile(r"\b(rappel|leçon|lecon|tutoriel|comment "
                                            r"(lire|faire)|pédagog|pedagog)\b", re.I)),
)


def ticker(texte: str) -> tuple[str | None, str | None]:
    """(ticker, symbole). DEUX actifs cités → (None, None) : on ne choisit pas."""
    paires = {(m.group(1).upper(), m.group(0).upper()) for m in _PAIRE.finditer(texte)}
    if len(paires) == 1:
        return next(iter(paires))
    if paires:
        return None, None
    nus = {m.group(1).upper() for m in _CASHTAG.finditer(texte)}
    nus |= {v for k, v in _NOMS.items() if re.search(_MOT.format(k), texte, re.I)}
    nus |= {m.group(1)
            for m in re.finditer(r"\b(BTC|ETH|SOL|XRP|ADA|DOGE|LTC)\b", texte)}
    return (next(iter(nus)), None) if len(nus) == 1 else (None, None)


def direction(texte: str) -> Direction | None:
    """Les deux sens cités, ou aucun → `None`. Jamais un arbitrage silencieux."""
    a_long, a_short = bool(_LONG.search(texte)), bool(_SHORT.search(texte))
    if a_long == a_short:
        return None
    return Direction.LONG if a_long else Direction.SHORT


def classification(texte: str) -> Classification:
    """Première règle qui accroche. Aucune → `UNKNOWN`, jamais un fourre-tout."""
    for etiquette, motif in _REGLES:
        if motif.search(texte):
            return etiquette
    return Classification.UNKNOWN
