"""Le MANDAT — définition déclarative de stratégie, séparée du moteur qui l'exécute.

Vocabulaire. « Mandat » est le terme institutionnel exact : ce qu'un gérant est
autorisé et instruit à faire, indépendamment du code qui le fait. On évite
`strategy` qui désigne déjà, dans `packages/strategies/`, les plugins EXÉCUTABLES.

Le problème qu'il ferme. Le 26-27/08, trois divergences production/backtest ont été
corrigées en un jour (#347 alignement, #352 sélection, #353 point de mesure). Cause
racine commune, et ce n'est aucune des trois : il n'existait nulle part d'artefact
disant « voici la stratégie ». Elle était éparpillée entre des valeurs par défaut de
fonctions, des variables d'environnement (`QUANT_LIVE_LITE` coupait `fundamentals`,
donc changeait la SÉLECTION D'UNIVERS sans qu'aucune configuration ne le dise) et des
effets de bord. Deux chemins pouvaient donc diverger en silence.

Un mandat est une DONNÉE : sérialisable, versionnée, hashée. Son identité est le
hash de sa forme canonique. Ce hash entre dans chaque ordre, chaque ligne de journal
et chaque résultat de backtest — de sorte qu'on puisse toujours répondre à « quelle
définition exacte a produit cet ordre ».
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any

from packages.mandate.canonical import hacher, hacher_court

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# CIBLES DE RÉSULTAT — refusées par construction.
#
# « Donne-moi un Sharpe de 2,3 » est une spécification par le RÉSULTAT, et c'est
# une machine à surapprendre : on ne spécifie pas une estimation, on la mesure.
# Le dépôt possède déjà la preuve chiffrée que ce n'est pas honorable —
# `research/sharpe_diff.seuil_detectable` établit que 126 pas ne résolvent que
# ~+0,14 de Sharpe (ADR-0039). Un système incapable de distinguer 1,35 de 1,49
# ne peut pas livrer « 2,3 » comme contrat.
#
# Pire que l'inefficacité : si une boucle génère des mandats et garde ceux qui
# atteignent la cible, elle fait du p-hacking à l'échelle. Le dépôt sait déjà y
# répondre — `research/ledger` compte les essais, `portfolio/psr` déflate le Sharpe
# de ce nombre (DSR), `research/fdr` contrôle les fausses découvertes d'un criblage
# simultané, et `research/gate` tranche. Le mandat leur fournit ce qui manquait :
# une IDENTITÉ stable par essai, donc un comptage qui ne peut pas être sous-estimé.
#
# Ces grandeurs restent parfaitement légitimes en SORTIE, avec leur barre d'erreur.
# Elles sont interdites en ENTRÉE.
# ---------------------------------------------------------------------------
METRIQUES_DE_RESULTAT = frozenset({
    "sharpe", "sortino", "calmar", "information_ratio", "alpha", "rendement",
    "return", "cagr", "profit", "pnl", "win_rate", "taux_de_reussite",
    "deflated_sharpe", "dsr",
})

# Ce que l'on PEUT spécifier : des contraintes que l'on contrôle réellement.
CONTRAINTES_CONNUES = frozenset({
    "drawdown_max", "turnover_max_annuel", "levier_max", "poids_max_ligne",
    "poids_min_ligne", "nb_lignes_min", "nb_lignes_max", "univers_autorise",
    "univers_interdit", "classes_actifs", "budget_couts_annuel",
    "correlation_max_au_book", "liquidite_min_adv",
})


@dataclass(frozen=True)
class Mandat:
    """Définition de stratégie. Immuable — une modification produit un NOUVEAU mandat.

    `meta` est COSMÉTIQUE et volontairement HORS identité : renommer un mandat ou
    corriger sa description ne doit pas rompre le lien d'audit avec les ordres qu'il
    a déjà produits. Tout le reste est sémantique et entre dans le hash.
    """

    moteur: str
    contraintes: dict[str, Any] = field(default_factory=dict)
    parametres: dict[str, Any] = field(default_factory=dict)
    donnees: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    # -- identité ----------------------------------------------------------
    def corps(self) -> dict:
        """Partie SÉMANTIQUE — tout ce qui peut changer une décision."""
        return {
            "schema_version": self.schema_version,
            "moteur": self.moteur,
            "contraintes": self.contraintes,
            "parametres": self.parametres,
            "donnees": self.donnees,
            "execution": self.execution,
        }

    def identite(self) -> str:
        """SHA-256 de la forme canonique du corps. L'identité du mandat."""
        return hacher(self.corps())

    def identite_courte(self) -> str:
        return hacher_court(self.corps())

    # -- sérialisation -----------------------------------------------------
    def vers_dict(self) -> dict:
        d = self.corps()
        d["meta"] = dict(self.meta)
        return d

    def vers_json(self, indent: int = 2) -> str:
        return json.dumps(self.vers_dict(), indent=indent, ensure_ascii=False,
                          sort_keys=True)

    def avec(self, **champs: Any) -> Mandat:
        """Copie modifiée — nouvelle identité si le changement est sémantique."""
        return replace(self, **champs)

    def renomme(self, nom: str) -> Mandat:
        """Change le nom SANS changer l'identité (démonstration du découpage)."""
        return replace(self, meta={**self.meta, "nom": nom})


def depuis_dict(d: dict) -> Mandat:
    """Reconstruit un mandat. Refuse les clés inconnues plutôt que de les ignorer.

    Une clé ignorée en silence est un mandat qui ne fait pas ce qu'il dit : elle
    n'entre alors ni dans le comportement ni dans le hash, et l'écart ne se voit nulle
    part. C'est exactement le mode de panne que ce module existe pour fermer.
    """
    connus = {"moteur", "contraintes", "parametres", "donnees",
              "execution", "schema_version", "meta"}
    inconnus = set(d) - connus
    if inconnus:
        raise ValueError(f"clés de mandat inconnues : {sorted(inconnus)}")
    if "moteur" not in d:
        raise ValueError("mandat sans `moteur` : rien ne peut l'exécuter")
    return Mandat(
        moteur=str(d["moteur"]),
        contraintes=dict(d.get("contraintes") or {}),
        parametres=dict(d.get("parametres") or {}),
        donnees=dict(d.get("donnees") or {}),
        execution=dict(d.get("execution") or {}),
        schema_version=int(d.get("schema_version", SCHEMA_VERSION)),
        meta=dict(d.get("meta") or {}),
    )


def _verifier_cibles_de_resultat(m: Mandat) -> list[str]:
    """Refuse toute contrainte qui est en réalité une cible de résultat."""
    fautes = []
    for cle in m.contraintes:
        racine = str(cle).lower().replace("cible_", "").replace("_cible", "")
        racine = racine.replace("target_", "").replace("_target", "")
        racine = racine.replace("min_", "").replace("max_", "")
        if racine in METRIQUES_DE_RESULTAT:
            fautes.append(
                f"`contraintes.{cle}` est une CIBLE DE RÉSULTAT. On ne spécifie pas "
                f"un « {racine} », on le mesure — avec son intervalle de confiance "
                "et le nombre de mandats essayés (research/ledger + portfolio/psr). "
                "Spécifie plutôt ce que tu contrôles : drawdown_max, "
                "turnover_max_annuel, levier_max, liquidite_min_adv…")
    return fautes


def valider(m: Mandat) -> list[str]:
    """Renvoie la liste des anomalies. Liste vide = mandat recevable.

    Renvoie plutôt que lève : un appelant veut souvent TOUTES les fautes d'un coup,
    pas la première. `exiger_valide` lève pour les chemins qui ne peuvent pas continuer.
    """
    fautes = _verifier_cibles_de_resultat(m)
    if m.schema_version != SCHEMA_VERSION:
        fautes.append(f"schema_version {m.schema_version} ≠ {SCHEMA_VERSION} attendu")
    if not m.moteur:
        fautes.append("`moteur` vide")
    inconnues = set(m.contraintes) - CONTRAINTES_CONNUES
    inconnues = {c for c in inconnues
                 if not _verifier_cibles_de_resultat(
                     m.avec(contraintes={c: m.contraintes[c]}))}
    if inconnues:
        fautes.append(f"contraintes non reconnues : {sorted(inconnues)}")
    try:
        m.identite()
    except (ValueError, TypeError) as e:
        fautes.append(f"corps non canonisable : {e}")
    return fautes


def exiger_valide(m: Mandat) -> Mandat:
    """Lève si le mandat est irrecevable. À appeler avant TOUTE exécution."""
    fautes = valider(m)
    if fautes:
        detail = "\n  - ".join(fautes)
        raise ValueError(f"mandat irrecevable ({len(fautes)}) :\n  - {detail}")
    return m
