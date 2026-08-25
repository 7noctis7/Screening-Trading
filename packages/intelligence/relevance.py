"""Pertinence de marché — écarter le bruit sans écarter le signal faible.

Le critère n'est PAS la popularité. Un post viral sans mécanisme de transmission vers un prix
n'a pas sa place dans un pipeline de trading ; une note technique lue par trois cents personnes
sur les réserves de la Fed en a une.

La question posée à chaque information est donc : par quel canal ceci peut-il déplacer un prix ?
Si aucun canal ne se nomme, la pertinence est nulle, quelle que soit l'audience.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Categorie(StrEnum):
    MACRO = "macro"
    GEOPOLITIQUE = "geopolitique"
    ACTIONS = "actions"
    CRYPTO = "crypto"
    SENTIMENT = "sentiment"
    HORS_SUJET = "hors_sujet"


# Taxonomie. Sert au CLASSEMENT et à l'aiguillage vers les actifs — jamais à décider seule.
SUJETS: dict[Categorie, tuple[str, ...]] = {
    Categorie.MACRO: ("inflation", "cpi", "pce", "emploi", "chomage", "pib", "taux",
                      "banque centrale", "fed", "bce", "politique monetaire", "liquidite",
                      "credit", "dette", "courbe des taux", "qt", "qe"),
    Categorie.GEOPOLITIQUE: ("conflit", "sanctions", "elections", "commerce", "tarifs",
                             "tensions", "energie", "approvisionnement", "petrole", "opep"),
    Categorie.ACTIONS: ("resultats", "guidance", "m&a", "acquisition", "direction",
                        "reglementation", "capex", "semi-conducteurs", "valorisation",
                        "flux institutionnels", "buyback", "dividende"),
    Categorie.CRYPTO: ("etf", "bitcoin", "ethereum", "stablecoin", "defi", "rwa",
                       "on-chain", "whale", "halving", "staking", "custody"),
    Categorie.SENTIMENT: ("risk-on", "risk-off", "euphorie", "peur", "capitulation",
                          "rotation", "narratif", "positionnement"),
}

# Motifs de BRUIT. Leur présence ne suffit pas à écarter — elle retire du crédit.
BRUIT = ("giveaway", "airdrop gratuit", "abonne-toi", "lien en bio", "signal premium",
         "groupe telegram", "1000x", "garanti", "ne rate pas", "pump")

IMPACT = {"fort": 1.0, "moyen": 0.6, "faible": 0.3}


@dataclass(frozen=True)
class Pertinence:
    score: float
    categories: tuple[Categorie, ...]
    motifs: list[str]

    @property
    def retenue(self) -> bool:
        """Seuil délibérément bas : ce filtre écarte le bruit, il ne juge pas la thèse."""
        return self.score >= 0.30 and Categorie.HORS_SUJET not in self.categories


def categoriser(texte: str) -> tuple[Categorie, ...]:
    t = (texte or "").lower()
    trouvees = tuple(c for c, mots in SUJETS.items() if any(m in t for m in mots))
    return trouvees or (Categorie.HORS_SUJET,)


def evaluer(texte: str, impact: str = "faible",
            actifs: tuple[str, ...] = ()) -> Pertinence:
    """Pertinence ∈ [0,1] avec ses motifs. Un canal de transmission nommé (catégorie + actif)
    vaut davantage que n'importe quelle audience."""
    cats = categoriser(texte)
    motifs: list[str] = []
    if Categorie.HORS_SUJET in cats:
        return Pertinence(0.0, cats, ["aucun sujet de marché identifié"])
    score = min(0.60, 0.30 * len(cats))
    motifs.append(f"catégories : {', '.join(c.value for c in cats)} (+{score:.2f})")
    if actifs:
        score += 0.20
        motifs.append(f"actifs nommés : {', '.join(actifs)} (+0.20)")
    else:
        motifs.append("aucun actif nommé — canal de transmission non identifié (+0.00)")
    c = 0.20 * IMPACT.get(impact, 0.3)
    score += c
    motifs.append(f"impact déclaré « {impact} » (+{c:.2f})")
    t = (texte or "").lower()
    vus = [m for m in BRUIT if m in t]
    if vus:
        score -= 0.40
        motifs.append(f"marqueurs de bruit : {', '.join(vus)} (-0.40)")
    return Pertinence(round(max(0.0, min(1.0, score)), 3), cats, motifs)
