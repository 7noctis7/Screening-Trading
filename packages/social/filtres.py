"""Filtrer et chercher dans les publications. Fonctions PURES, testables hors ligne.

Le filtrage vit ici, pas dans la route ni dans le composant, pour une raison précise :
le site est publié en STATIQUE (GitHub Pages, sans API). La même sémantique doit donc
valoir des deux côtés — filtrée par le serveur quand l'API répond, filtrée par le
navigateur sur la charge embarquée sinon. Deux implémentations divergeraient en silence,
et l'utilisateur verrait des résultats différents selon l'endroit d'où il regarde.

TROIS DÉCISIONS DE SÉMANTIQUE, toutes contre-intuitives une fois codées naïvement.

1. UNE SÉLECTION VIDE VEUT DIRE « TOUS », JAMAIS « AUCUN ». C'est le défaut qui décide
   de ce qu'on voit en arrivant sur la page. Traiter `comptes=[]` comme « ne retenir
   aucun compte » donnerait une page vide au premier chargement, indiscernable d'un flux
   en panne.

2. LA RECHERCHE EST INSENSIBLE À LA CASSE **ET AUX ACCENTS**. Le contenu est bilingue :
   « resistance » tapé au clavier doit trouver « résistance » écrit dans le message.
   « resistance » tapé au clavier doit trouver « résistance » écrit dans le message.
   Sans cela, l'absence de résultat ne dit pas « rien à ce sujet » mais « pas écrit
   comme vous » — et rien à l'écran ne fait la différence.
3. PLUSIEURS MOTS = ET, PAS UNE PHRASE. « BTC LONG » cherche les messages contenant les
   deux, où qu'ils soient, plutôt que la suite exacte « BTC LONG ». Un jeton seul se
   comporte identiquement, donc le cas simple ne paie rien pour le cas composé.

Ce que la recherche BALAIE : texte, ticker, symbole, classification, direction, et les
niveaux extraits (« 65000 » retrouve le message dont le TP1 vaut 65000). Un champ absent
n'est pas cherché — il n'est pas non plus remplacé par une chaîne vide qui matcherait
n'importe quoi.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from packages.social.modele import Classification, Direction, Publication


def normaliser(texte: str) -> str:
    """Minuscules, accents retirés. La forme sous laquelle tout est comparé."""
    decompose = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _champs_cherchables(p: Publication) -> list[str]:
    """Tout ce sur quoi la recherche porte. Un champ absent n'y entre pas."""
    champs: list[str] = [p.texte, str(p.classification)]
    for optionnel in (p.ticker, p.symbole):
        if optionnel:
            champs.append(optionnel)
    if p.direction is not None:
        champs.append(str(p.direction))
    for cle, valeur in p.extraits.items():
        champs.append(cle)
        champs.append(_nombre(valeur))
    return champs


def _nombre(v: float) -> str:
    """« 65000 » doit retrouver un niveau stocké 65000.0 — donc les deux formes."""
    entier = f"{v:.0f}"
    return f"{v} {entier}" if float(entier) == v else str(v)


def contient(p: Publication, requete: str) -> bool:
    """Vrai si CHAQUE mot de la requête apparaît dans au moins un champ cherchable."""
    mots = normaliser(requete).split()
    if not mots:
        return True
    foin = " \u0000 ".join(normaliser(c) for c in _champs_cherchables(p))
    return all(mot in foin for mot in mots)


@dataclass(frozen=True)
class Filtre:
    """Critères combinables. Chaque champ vide = ce critère ne filtre RIEN.

    Les critères se combinent en ET : un compte ET un mot-clé ET une classification.
    À l'intérieur d'un même critère, c'est un OU : deux comptes veulent dire l'un ou
    l'autre. C'est la lecture naturelle d'une interface à cases à cocher, et la seule
    qui rende « astekz + micro2macr0 » utile.
    """

    comptes: Sequence[str] = ()
    requete: str = ""
    classifications: Sequence[Classification] = ()
    directions: Sequence[Direction] = ()
    symboles: Sequence[str] = ()
    tickers: Sequence[str] = ()
    _vide: bool = field(default=False, repr=False, compare=False)

    def actif(self) -> bool:
        """Y a-t-il seulement quelque chose à filtrer ? Sert à le DIRE à l'écran."""
        return bool(self.comptes or self.requete.strip() or self.classifications
                    or self.directions or self.symboles or self.tickers)


def _dans(valeur: str | None, choix: Sequence[str]) -> bool:
    """Un critère vide laisse tout passer. Une valeur absente ne passe QUE si vide."""
    if not choix:
        return True
    if valeur is None:
        return False
    cible = normaliser(valeur)
    return any(cible == normaliser(str(c)) for c in choix)


def retenir(p: Publication, f: Filtre) -> bool:
    """Une publication passe-t-elle TOUS les critères ?"""
    return (_dans(p.compte, f.comptes)
            and _dans(str(p.classification), [str(c) for c in f.classifications])
            and _dans(None if p.direction is None else str(p.direction),
                      [str(d) for d in f.directions])
            and _dans(p.symbole, f.symboles)
            and _dans(p.ticker, f.tickers)
            and contient(p, f.requete))


def appliquer(publications: Iterable[Publication], f: Filtre) -> list[Publication]:
    """Filtre, puis trie du plus récent au plus ancien."""
    gardees = [p for p in publications if retenir(p, f)]
    gardees.sort(key=lambda p: p.ts, reverse=True)
    return gardees
