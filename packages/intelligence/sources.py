"""Qualité d'une SOURCE — qui parle, et quel crédit lui accorder.

Règle fondatrice : le nombre d'abonnés n'est pas une preuve de vérité. Un compte à un million
d'abonnés publie des choses fausses ; un compte à cinquante mille peut être la meilleure source
d'un sujet. Le nombre d'abonnés entre donc dans le score comme une contribution BORNÉE et
minoritaire, jamais comme un critère suffisant.

Deuxième règle : ce module note la SOURCE, pas l'information. Une source excellente peut publier
une opinion ; une opinion reste une opinion (cf. `classify`). Confondre les deux est le mécanisme
par lequel un avis d'investisseur devient une « donnée » dans un pipeline.

Le score est DÉCOMPOSABLE : `ScoreSource.detail` liste chaque contribution avec son libellé. On
doit pouvoir répondre à « pourquoi 0,90 et pas 0,45 ? » sans lire le code.

Ce paquet n'importe rien de `packages.execution` et n'a aucun accès au courtier. C'est
structurel : la couche d'intelligence alimente l'analyse, elle n'émet jamais d'ordre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Niveau(StrEnum):
    """Hiérarchie des sources. A domine toujours E, quel que soit le nombre d'abonnés."""
    A_PRIMAIRE = "A"      # source primaire/officielle : émetteur, banque centrale, régulateur, filing
    B_EXPERT = "B"        # expert crédible et identifié dans SON domaine
    C_SUIVI = "C"         # compte très suivi, expertise à établir
    D_SECONDAIRE = "D"    # compte secondaire/émergent — détection, pas confirmation
    E_FAIBLE = "E"        # anonyme/non vérifié — signal faible uniquement


# Poids de base par niveau. L'écart A→E est délibérément large : aucune accumulation de bonus
# ne doit permettre à un compte anonyme d'atteindre le crédit d'un communiqué officiel.
_BASE = {Niveau.A_PRIMAIRE: 0.70, Niveau.B_EXPERT: 0.45, Niveau.C_SUIVI: 0.25,
         Niveau.D_SECONDAIRE: 0.15, Niveau.E_FAIBLE: 0.05}

# Contribution MAXIMALE du nombre d'abonnés, toutes tailles confondues. Volontairement faible :
# c'est le garde-fou contre « viral donc vrai ».
POIDS_ABONNES_MAX = 0.08
SEUIL_ABONNES = 100_000

PLAFOND_NON_VERIFIE = 0.60   # un compte non authentifié ne peut pas atteindre le haut du barème


@dataclass(frozen=True)
class Source:
    """Identité déclarée d'une source. `verifie` signifie AUTHENTIFIÉE par un humain ou un
    procédé traçable — pas « a une coche »."""
    handle: str
    niveau: Niveau = Niveau.E_FAIBLE
    verifie: bool = False
    abonnes: int | None = None            # None = INCONNU, jamais 0 par défaut
    domaines: tuple[str, ...] = ()
    exactitude_passee: float | None = None  # ∈ [0,1] mesurée, None si aucun historique
    note: str = ""


@dataclass(frozen=True)
class ScoreSource:
    valeur: float
    detail: list[tuple[str, float]] = field(default_factory=list)

    def explication(self) -> str:
        lignes = [f"  {lib:38s} {c:+.3f}" for lib, c in self.detail]
        return "\n".join(lignes + [f"  {'TOTAL':38s} {self.valeur: .3f}"])


def _contribution_abonnes(n: int | None) -> tuple[str, float]:
    """Bornée et logarithmique : passer de 100 k à 10 M ne double pas le crédit."""
    if not n or n < SEUIL_ABONNES:
        return ("abonnés < 100 k ou inconnus", 0.0)
    import math
    ratio = math.log10(n / SEUIL_ABONNES) / 2.0        # 100 k → 0 · 10 M → 1
    return (f"audience ({n:,}".replace(",", " ") + ")",
            round(POIDS_ABONNES_MAX * min(1.0, ratio), 3))


def score_source(s: Source, domaine: str = "") -> ScoreSource:
    """Crédit accordé à la source POUR CE DOMAINE. Un expert crypto n'est pas un expert macro."""
    detail: list[tuple[str, float]] = [(f"niveau {s.niveau.value}", _BASE[s.niveau])]
    total = _BASE[s.niveau]

    if s.verifie:
        detail.append(("identité authentifiée", 0.15))
        total += 0.15
    else:
        detail.append(("identité NON authentifiée", 0.0))

    lib, c = _contribution_abonnes(s.abonnes)
    detail.append((lib, c))
    total += c

    if domaine and s.domaines:
        dans = domaine.lower() in {d.lower() for d in s.domaines}
        detail.append((f"domaine « {domaine} » {'couvert' if dans else 'HORS expertise'}",
                       0.10 if dans else -0.15))
        total += 0.10 if dans else -0.15

    if s.exactitude_passee is not None:
        c = round(0.20 * (s.exactitude_passee - 0.5) * 2, 3)   # 0,5 neutre · 1,0 → +0,20
        detail.append((f"exactitude passée {s.exactitude_passee:.0%}", c))
        total += c
    else:
        detail.append(("aucun historique d'exactitude", 0.0))

    if not s.verifie and total > PLAFOND_NON_VERIFIE:
        detail.append((f"plafond compte non authentifié ({PLAFOND_NON_VERIFIE:.2f})",
                       round(PLAFOND_NON_VERIFIE - total, 3)))
        total = PLAFOND_NON_VERIFIE

    return ScoreSource(round(max(0.0, min(1.0, total)), 3), detail)


def utilisable_seule(s: Source) -> bool:
    """Cette source suffit-elle, à elle seule, pour une information à impact ?

    Réponse : seulement une source PRIMAIRE authentifiée. Tout le reste demande corroboration.
    C'est la règle qui empêche un post isolé de devenir un fait."""
    return s.niveau is Niveau.A_PRIMAIRE and s.verifie
