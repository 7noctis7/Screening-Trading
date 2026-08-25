"""Portail de risque PRÉ-TRADE — la dernière barrière avant le courtier.

CE QUE CE MODULE CORRIGE. Le dépôt contenait deux couches de risque qui ne se rencontraient
jamais. `packages.risk.engine.RiskEngine` (règles reward/risk, nombre de positions, exposition
par actif) n'était instancié que dans `scripts/demo_*.py` — donc dans les démos et les backtests.
Le chemin de PRODUCTION (`scripts/run_live.py`) n'en passait par aucune : après la décision de
`rebalance_plan.decider`, le montant partait au courtier, seulement mis à l'échelle par le
facteur `reduce` du kill-switch. Autrement dit, les limites de risque du projet étaient
documentées, testées, et absentes de la seule chaîne qui envoie de vrais ordres.

CE QU'IL N'EST PAS. Ce portail ne remplace pas `RiskEngine` (qui raisonne par signal/stop, en
streaming barre par barre) ni les kill-switches. Il s'insère APRÈS la stratégie et AVANT le
courtier, et il ne connaît rien de la stratégie : il ne voit qu'un ordre, un état de compte et
des limites. C'est précisément ce qui le rend non contournable — aucune couche amont, IA
comprise, ne lui passe d'argument qui l'assouplirait.

PRINCIPE DIRECTEUR : le portail ne peut que RÉDUIRE ou REFUSER, jamais augmenter. Un portail
capable d'agrandir un ordre ne serait plus un garde-fou.

COROLLAIRE, ET IL COMPTE : une VENTE ou une LIQUIDATION n'est jamais bloquée. Un portail qui
refuse un désengagement augmente le risque au lieu de le réduire — c'est le même piège que le
plancher de ligne qui ne gardait que les ouvertures (cf. `rebalance_plan`) : une règle correcte
appliquée dans un seul sens produit l'inverse de son intention.

Les limites viennent de l'ENVIRONNEMENT, jamais d'un appelant. Un appelant qui pourrait passer
ses propres limites pourrait les desserrer ; c'est exactement ce qu'on veut rendre impossible.
Les valeurs par défaut sont volontairement conservatrices et supposent un compte SANS levier.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Défauts : compte sans levier, portefeuille de conviction moyenne. Chaque valeur est un plafond
# DUR, pas une cible — la stratégie reste libre en dessous.
MAX_POIDS_LIGNE = 0.20       # QUANT_RISK_MAX_WEIGHT      — une ligne ne dépasse pas 20 % du compte
MAX_POSITIONS = 40           # QUANT_RISK_MAX_POSITIONS   — au-delà, on n'OUVRE plus (on peut solder)
MAX_ORDRE_PCT = 0.15         # QUANT_RISK_MAX_ORDER_PCT   — un ordre ne dépasse pas 15 % du compte
MAX_EXPOSITION = 1.00        # QUANT_RISK_MAX_GROSS       — 1,00 = aucun levier, jamais


def _env(nom: str, defaut: float) -> float:
    """Lecture tolérante d'une limite. Une valeur illisible ou négative retombe sur le défaut :
    une faute de frappe dans `.env` ne doit pas désactiver silencieusement un garde-fou."""
    try:
        v = float(os.environ.get(nom, "") or defaut)
    except (TypeError, ValueError):
        return defaut
    return v if v > 0 else defaut


@dataclass(frozen=True)
class Limites:
    """Plafonds durs. `depuis_env()` est la SEULE fabrique utilisée en production."""
    max_poids_ligne: float = MAX_POIDS_LIGNE
    max_positions: int = MAX_POSITIONS
    max_ordre_pct: float = MAX_ORDRE_PCT
    max_exposition: float = MAX_EXPOSITION

    @staticmethod
    def depuis_env() -> Limites:
        return Limites(
            max_poids_ligne=_env("QUANT_RISK_MAX_WEIGHT", MAX_POIDS_LIGNE),
            max_positions=int(_env("QUANT_RISK_MAX_POSITIONS", MAX_POSITIONS)),
            max_ordre_pct=_env("QUANT_RISK_MAX_ORDER_PCT", MAX_ORDRE_PCT),
            max_exposition=_env("QUANT_RISK_MAX_GROSS", MAX_EXPOSITION),
        )

    def resume(self) -> str:
        return (f"ligne ≤ {self.max_poids_ligne:.0%} · positions ≤ {self.max_positions} · "
                f"ordre ≤ {self.max_ordre_pct:.0%} · brut ≤ {self.max_exposition:.0%}")


@dataclass(frozen=True)
class EtatCompte:
    """Ce que le portail doit connaître du compte. Fourni par l'appelant, mais JAMAIS utilisé
    pour assouplir une limite — seulement pour la mesurer."""
    equity: float
    exposition_brute: float      # somme des valeurs absolues des positions, en monnaie
    n_positions: int
    detenu_ligne: float = 0.0    # valeur déjà détenue sur CE symbole


@dataclass(frozen=True)
class Verdict:
    """Décision auditable. `montant` ≤ montant demandé, toujours."""
    autorise: bool
    montant: float
    regle: str
    motif: str

    @property
    def reduit(self) -> bool:
        return self.autorise and self.regle != "ok"


def _veto(regle: str, motif: str) -> Verdict:
    return Verdict(False, 0.0, regle, motif)


def evaluer(action: str, montant: float, etat: EtatCompte,
            limites: Limites | None = None, *, liquidation: bool = False) -> Verdict:
    """Autorise, réduit ou refuse UN ordre. `action` ∈ {acheter, alleger, solder}.

    L'ordre des règles porte le sens : on établit d'abord que l'état du compte est CONNU, puis
    que le sens de l'ordre réduit ou augmente le risque, et seulement ensuite on applique les
    plafonds — qui ne concernent que ce qui augmente le risque.
    """
    lim = limites or Limites.depuis_env()
    montant = max(0.0, float(montant))

    # 1. RÉDUIRE LE RISQUE PASSE TOUJOURS — et cette règle vient AVANT toutes les autres,
    #    y compris avant le contrôle d'equity. Un désengagement part en QUANTITÉ : il n'a pas
    #    besoin qu'on sache dimensionner. Refuser une sortie parce que le courtier n'a pas
    #    renvoyé l'equity, c'est enfermer la position le jour précis où l'on veut sortir.
    if liquidation or action in ("alleger", "solder", "vendre"):
        return Verdict(True, montant, "ok", "désengagement — jamais bloqué par le portail")

    # 2. INCONNU ≠ ZÉRO. Une equity nulle ou illisible n'est pas un compte vide : c'est un compte
    #    qu'on n'a pas su lire. Dimensionner un ACHAT là-dessus, c'est parier sur une inconnue.
    if etat.equity <= 0:
        return _veto("equity_inconnue",
                     "equity nulle ou illisible — aucun achat ne peut être dimensionné")

    if montant <= 0:
        return _veto("montant_nul", "montant nul")

    # 3. PLAFONDS. Chacun peut RÉDUIRE le montant ; le plus contraignant l'emporte.
    plafonds: list[tuple[str, float, str]] = [
        ("taille_ordre", lim.max_ordre_pct * etat.equity,
         f"ordre plafonné à {lim.max_ordre_pct:.0%} du compte"),
        ("poids_ligne", max(0.0, lim.max_poids_ligne * etat.equity - etat.detenu_ligne),
         f"ligne plafonnée à {lim.max_poids_ligne:.0%} du compte"),
        ("exposition_brute", max(0.0, lim.max_exposition * etat.equity - etat.exposition_brute),
         f"exposition brute plafonnée à {lim.max_exposition:.0%} — aucun levier"),
    ]
    regle, autorise_max, motif = min(plafonds, key=lambda p: p[1])

    # 4. NOMBRE DE POSITIONS : ne s'applique qu'à une OUVERTURE. Renforcer une ligne existante
    #    ne crée pas de position supplémentaire — refuser ici ne réduirait aucun risque.
    if etat.detenu_ligne <= 0 and etat.n_positions >= lim.max_positions:
        return _veto("max_positions",
                     f"{etat.n_positions} positions ouvertes ≥ plafond {lim.max_positions} — "
                     "aucune nouvelle ligne (les allègements restent possibles)")

    if autorise_max <= 0:
        return _veto(regle, motif + " — déjà atteint")
    if montant <= autorise_max:
        return Verdict(True, montant, "ok", "dans toutes les limites")
    return Verdict(True, round(autorise_max, 2), regle,
                   f"{motif} : {montant:.0f} $ réduit à {autorise_max:.0f} $")


def ligne_journal(symbole: str, action: str, demande: float, v: Verdict) -> str:
    """Trace auditable d'UNE décision. Répond après coup à « pourquoi cet ordre a-t-il été
    accepté / réduit / refusé ? » — sans cette ligne, la question reste sans réponse."""
    etat = "REFUSÉ" if not v.autorise else ("RÉDUIT" if v.reduit else "OK")
    return (f"[risk-gate] {symbole:14s} {action:8s} demandé {demande:9.0f}$ → "
            f"{v.montant:9.0f}$  {etat:7s} [{v.regle}] {v.motif}")
