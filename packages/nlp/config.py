"""Réglages du NLP local. TOUT ce qui se change sans lire le code est ici.

LE BUDGET MÉMOIRE EST UNE CONTRAINTE, PAS UN RÉGLAGE. Le Mac Mini a 16 Go unifiés, dont au
plus 7,5 Go pour le LLM et son cache. Un modèle 7B quantifié en Q4 occupe environ 4,5 Go ;
chaque requête concurrente y ajoute son contexte. La concurrence par défaut est donc de 2 —
pas par prudence vague, mais parce qu'au-delà on entre dans la zone où macOS commence à
échanger sur disque, et une latence qui explose ressemble à une panne de modèle.

UN SEUL MODÈLE ACTIF. Charger Qwen 7B et Gemma 2B en même temps tient en mémoire, mais
alterner entre eux fait payer un rechargement à chaque bascule. Le comparatif entre modèles
se fait donc en série (`scripts/benchmark_nlp.py`), jamais en parallèle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Défauts pensés pour LM Studio sur Mac Mini M4 16 Go.
MODELE_DEFAUT = "qwen2.5-7b-instruct"
TIMEOUT_S = 12.0          # au-delà, un titre ne vaut plus qu'on attende
CONCURRENCE = 2           # cf. budget mémoire ci-dessus
CACHE_MAX = 256           # entrées ; une entrée pèse quelques centaines d'octets
PILOTE = "auto"           # auto | lmstudio | ollama


def _flottant(nom: str, defaut: float) -> float:
    try:
        v = float(os.environ.get(nom, "") or defaut)
    except (TypeError, ValueError):
        return defaut
    return v if v > 0 else defaut


def _entier(nom: str, defaut: int) -> int:
    return int(_flottant(nom, float(defaut)))


@dataclass(frozen=True)
class ConfigNLP:
    """Résolue à chaque appel, jamais mémorisée — même principe que `llm.client.Config`."""

    modele: str = ""
    base: str = ""
    pilote: str = ""
    timeout_s: float = TIMEOUT_S
    concurrence: int = CONCURRENCE
    cache_max: int = CACHE_MAX

    @staticmethod
    def depuis_env() -> ConfigNLP:
        return ConfigNLP(
            # `LOCAL_TRADING_MODEL` est le nom demandé par le cahier des charges ;
            # `QUANT_NLP_MODEL` et `LLM_MODEL` restent acceptés pour ne pas casser
            # une configuration existante.
            modele=(os.environ.get("LOCAL_TRADING_MODEL")
                    or os.environ.get("QUANT_NLP_MODEL")
                    or os.environ.get("LLM_MODEL")
                    or MODELE_DEFAUT),
            base=os.environ.get("QUANT_NLP_BASE", ""),
            pilote=(os.environ.get("QUANT_NLP_PILOTE") or PILOTE).lower(),
            timeout_s=_flottant("QUANT_NLP_TIMEOUT_S", TIMEOUT_S),
            concurrence=max(1, _entier("QUANT_NLP_CONCURRENCE", CONCURRENCE)),
            cache_max=max(0, _entier("QUANT_NLP_CACHE", CACHE_MAX)),
        )

    def resume(self) -> str:
        return (f"{self.modele} · pilote {self.pilote} · timeout {self.timeout_s:.0f} s · "
                f"concurrence {self.concurrence} · cache {self.cache_max}")
