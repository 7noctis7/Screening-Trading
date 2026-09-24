"""Faire passer chaque publication par le qualifieur du dépôt. Pas de seconde voie.

AGENTS.md §9 le dit sans détour : « Point d'entrée unique :
`packages.intelligence.pipeline.qualifier()` · règles encodées, à ne pas contourner ».

L'onglet X livré sans ce passage créait exactement ce que cette règle interdit : un
SECOND chemin d'intelligence X, qui affichait des propos sans plafond d'authenticité,
sans déduplication d'origine et sans exigence de corroboration. Le mécanisme par lequel
un pipeline devient dangereux est toujours le même — une opinion entre, traverse
quelques couches, et ressort en donnée. Le contournement était involontaire ; il n'en
était pas moins un contournement.

TROIS CORRESPONDANCES, ET AUCUNE N'EST NEUTRE.

1. **Le niveau de la watchlist est une HYPOTHÈSE, pas un acquis.** Le type s'appelle
   `Candidat`, son champ `niveau_attendu`, et sa documentation dit « à valider avant
   tout usage » ; `a_resoudre` nomme ce qui empêche de s'en servir tel quel. Un compte
   portant une réserve non levée retombe donc en `E_FAIBLE`, comme un compte absent de
   la liste. Mesuré le 24/09 : 34 des 66 comptes sont sans réserve, 32 en portent une —
   dont les quatre comptes suivis ici, tous en « expertise et authenticité à établir ».
   Prendre le niveau attendu pour un niveau validé promouvrait la moitié de la liste
   sur la foi d'une note de travail.

2. **`verifie` vaut TOUJOURS `False`.** AGENTS.md : « aucun des 66 comptes de la
   watchlist n'est authentifié — ne pas le prétendre ». Le plafond de 0,60 s'applique
   donc à tous, sans exception, et rien ici ne peut le lever.

3. **L'impact suit le caractère ACTIONNABLE du message.** Un signal d'entrée, une
   fermeture, un déplacement de stop sont des propos sur lesquels quelqu'un peut agir :
   `fort`. Une analyse ou une nouvelle : `moyen`. Un rappel pédagogique ou un message
   non classé : `faible`. Or l'exigence de corroboration CROÎT avec l'impact — ce
   classement ne peut donc que durcir l'exigence sur ce qui est actionnable, jamais
   l'adoucir. C'est le sens d'un contrôle : il refuse, il n'autorise pas.

Ce module ne rend AUCUN verdict lui-même : il traduit, appelle, et transmet. Toute la
règle vit dans `packages/intelligence`, à un seul endroit.
"""

from __future__ import annotations

from packages.intelligence.classify import Information, Nature
from packages.intelligence.pipeline import qualifier
from packages.intelligence.sources import Niveau, Source
from packages.intelligence.watchlist import WATCHLIST
from packages.social.modele import Classification, Publication

# Un message social AFFIRME rarement un état du monde. `NEWS` est la seule étiquette qui
# prétende rapporter un fait ; le reste est un jugement, et le rester jusqu'au bout.
_NATURE = {
    Classification.NEWS: Nature.FACTUELLE,
    Classification.TRADE_SIGNAL: Nature.PREDICTION,
    Classification.MARKET_ANALYSIS: Nature.PREDICTION,
}

_ACTIONNABLES = frozenset({
    Classification.TRADE_SIGNAL, Classification.CLOSE_POSITION,
    Classification.MOVE_STOP, Classification.TAKE_PROFIT_UPDATE,
    Classification.CANCEL_SIGNAL,
})
_INFORMATIVES = frozenset({
    Classification.MARKET_ANALYSIS, Classification.NEWS, Classification.TRADE_UPDATE,
})

# Seuls les comptes SANS réserve ouverte portent leur niveau attendu. Les autres sont
# des hypothèses en attente, et une hypothèse ne crédite personne.
_NIVEAUX: dict[str, Niveau] = {
    c.handle.lower(): c.niveau_attendu for c in WATCHLIST if not c.a_resoudre}


def _source(compte: str) -> Source:
    """Niveau VALIDÉ de la watchlist, sinon E. `verifie` reste False — toujours."""
    return Source(handle=compte, niveau=_NIVEAUX.get(compte.lower(), Niveau.E_FAIBLE),
                  verifie=False)


def _impact(c: Classification) -> str:
    """Actionnable → `fort`. L'exigence de preuve monte avec l'impact, pas l'inverse."""
    if c in _ACTIONNABLES:
        return "fort"
    return "moyen" if c in _INFORMATIVES else "faible"


def information(p: Publication) -> Information:
    actifs = tuple(x for x in (p.ticker, p.symbole) if x)
    return Information(
        texte=p.texte, source=_source(p.compte),
        nature=_NATURE.get(p.classification, Nature.OPINION),
        url=p.url or "", horodatage=p.ts.isoformat(),
        sujet=p.ticker or "", actifs=actifs, impact_potentiel=_impact(p.classification))


def verdict(p: Publication) -> dict:
    """Le verdict du dépôt, réduit à ce que l'écran doit montrer. Ne lève jamais."""
    v = qualifier(information(p))
    return {
        "statut": str(v.classement.statut),
        "exploitable": bool(v.exploitable),
        "confiance": round(float(v.confiance), 3),
        "niveau_source": str(_source(p.compte).niveau),
        "motifs": list(v.motifs)[:4],
    }
