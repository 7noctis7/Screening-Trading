"""Comparatif de modèles locaux — ce qu'il mesure, et surtout ce qu'il NE mesure PAS.

CE QU'IL MESURE : des qualités OPÉRATIONNELLES. Latence, jetons par seconde, taux de repli,
taux de sortie conforme au schéma, STABILITÉ (le même titre deux fois donne-t-il la même
réponse ?) et ACCORD entre modèles.

CE QU'IL NE MESURE PAS, ET C'EST ESSENTIEL : la valeur PRÉDICTIVE. Aucun classement obtenu
ici ne dit qu'un modèle fait gagner de l'argent. Un modèle peut être rapide, stable, d'accord
avec ses pairs, et parfaitement inutile — l'accord entre modèles mesure leur ressemblance,
pas leur justesse, et deux modèles entraînés sur le même web se ressemblent par construction.
Seul `make alpha-nlp`, sur des rendements réalisés, tranche la question qui compte.

L'usage juste de ce banc est donc d'ÉLIMINER : écarter un modèle trop lent pour la séance,
trop instable pour être reproductible, ou qui ne tient pas le schéma. Ce qui reste va au
banc d'alpha.

LES MODÈLES SONT ÉPROUVÉS EN SÉRIE, jamais en parallèle : sur 16 Go unifiés, alterner entre
deux modèles chargés fait payer un rechargement à chaque bascule, et les latences mesurées
ne décriraient plus le modèle mais l'ordre des appels.
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass, field

from packages.nlp.config import ConfigNLP
from packages.nlp.moteur import MoteurNLP
from packages.nlp.pilotes import pilote_pour

# Cas d'école : un fait clairement favorable, un clairement défavorable, un non-événement.
# Ce ne sont PAS une vérité terrain — ce sont des contrôles de bon sens. Un modèle qui les
# rate est disqualifié ; un modèle qui les passe n'a rien prouvé.
CAS: tuple[tuple[str, str, str], ...] = (
    ("AAPL", "Résultats trimestriels très au-dessus du consensus, marge brute en hausse.",
     "BULLISH"),
    ("NVDA", "La société relève sa prévision de chiffre d'affaires pour le trimestre.",
     "BULLISH"),
    ("BA", "Rappel massif après un défaut de production critique sur la chaîne principale.",
     "BEARISH"),
    ("XYZ", "Le régulateur ouvre une enquête pour fraude comptable présumée.", "BEARISH"),
    ("KO", "La société confirme la tenue de son assemblée générale annuelle en mai.",
     "NEUTRAL"),
    ("PG", "Le siège social déménage de deux étages dans le même immeuble.", "NEUTRAL"),
)
REPETITIONS = 3          # pour la stabilité : même entrée, même sortie ?


@dataclass
class Resultat:
    """Ce qu'un modèle a produit sur le jeu commun."""

    modele: str
    pilote: str
    n: int = 0
    accords_bon_sens: int = 0
    replis: int = 0
    conformes: int = 0
    latences_ms: list[float] = field(default_factory=list)
    jetons: list[int] = field(default_factory=list)
    stable: bool | None = None
    sentiments: list[str] = field(default_factory=list)
    incidents: list[str] = field(default_factory=list)

    @property
    def latence_mediane(self) -> float | None:
        return round(statistics.median(self.latences_ms), 1) if self.latences_ms else None

    @property
    def latence_p90(self) -> float | None:
        if not self.latences_ms:
            return None
        s = sorted(self.latences_ms)
        return round(s[min(len(s) - 1, int(len(s) * 0.9))], 1)

    @property
    def jetons_par_s(self) -> float | None:
        """Jetons RÉELS rendus par le fournisseur, jamais estimés depuis la longueur du
        texte — une estimation fausse de 20 à 40 % selon le tokeniseur ne comparerait rien."""
        if not self.jetons or not self.latences_ms:
            return None
        total_s = sum(self.latences_ms) / 1000.0
        return round(sum(self.jetons) / total_s, 1) if total_s > 0 else None

    @property
    def taux_bon_sens(self) -> float:
        return round(self.accords_bon_sens / self.n, 3) if self.n else 0.0

    def en_dict(self) -> dict:
        return {"modele": self.modele, "pilote": self.pilote, "n": self.n,
                "bon_sens": self.taux_bon_sens, "replis": self.replis,
                "conformes": self.conformes, "stable": self.stable,
                "latence_mediane_ms": self.latence_mediane,
                "latence_p90_ms": self.latence_p90, "jetons_par_s": self.jetons_par_s,
                "incidents": list(self.incidents)}


def eprouver(modele: str, pilote_nom: str = "auto", base: str = "",
             cas: tuple = CAS, repetitions: int = REPETITIONS) -> Resultat | None:
    """Éprouve UN modèle sur le jeu commun. `None` si aucun fournisseur ne répond."""
    # Le plafond de jetons vient de l'ENVIRONNEMENT : un banc qui mesurerait sous un
    # plafond différent de celui de la production classerait des modèles qu'on ne fait
    # pas tourner.
    env = ConfigNLP.depuis_env()
    cfg = ConfigNLP(modele=modele, base=base, pilote=pilote_nom,
                    max_jetons=env.max_jetons,
                    cache_max=0)     # cache DÉSACTIVÉ : il fausserait latence et stabilité
    p = pilote_pour(cfg)
    if p is None:
        return None
    moteur = MoteurNLP(cfg=cfg, pilote=p)
    r = Resultat(modele=modele, pilote=p.nom)
    for ticker, texte, attendu in cas:
        s = asyncio.run(moteur.classer(ticker, texte))
        r.n += 1
        r.sentiments.append(s.sentiment)
        if s.repli:
            r.replis += 1
            continue
        r.conformes += 1
        if s.latence_ms:
            r.latences_ms.append(s.latence_ms)
        jet = (getattr(p, "dernier_usage", {}) or {}).get("completion_tokens")
        if isinstance(jet, int) and jet > 0:
            r.jetons.append(jet)
        if s.sentiment == attendu:
            r.accords_bon_sens += 1
    r.stable = _stabilite(moteur, cas[0], repetitions)
    if r.replis:
        r.incidents.append(f"{r.replis}/{r.n} repli(s) — chaîne instable ou modèle absent")
    if r.stable is False:
        r.incidents.append("réponses NON reproductibles à température nulle")
    return r


def _stabilite(moteur: MoteurNLP, cas: tuple, repetitions: int) -> bool | None:
    """Le même titre, plusieurs fois : la réponse change-t-elle ?

    À température nulle un modèle devrait être déterministe. Les modèles quantifiés ne le
    sont pas toujours selon le moteur d'inférence, et l'ignorer rendrait irreproductible
    tout ce qui s'appuie dessus — y compris une mesure d'alpha.
    """
    ticker, texte, _ = cas
    vus = set()
    for _ in range(max(2, repetitions)):
        s = asyncio.run(moteur.classer(ticker, texte))
        if s.repli:
            return None
        vus.add((s.sentiment, round(s.confiance, 2)))
    return len(vus) == 1


def accord(resultats: list[Resultat]) -> list[dict]:
    """Part des cas où deux modèles disent la même chose.

    ATTENTION à la lecture : l'accord mesure la RESSEMBLANCE, pas la justesse. Deux modèles
    entraînés sur le même web se ressemblent par construction, et deux modèles d'accord sur
    une erreur restent d'accord.
    """
    out: list[dict] = []
    for i, a in enumerate(resultats):
        for b in resultats[i + 1:]:
            n = min(len(a.sentiments), len(b.sentiments))
            if not n:
                continue
            memes = sum(1 for k in range(n) if a.sentiments[k] == b.sentiments[k])
            out.append({"a": a.modele, "b": b.modele, "n": n,
                        "accord": round(memes / n, 3)})
    return out
