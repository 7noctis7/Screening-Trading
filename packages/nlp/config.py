"""Réglages du NLP local. TOUT ce qui se change sans lire le code est ici.

LE BUDGET MÉMOIRE EST UNE CONTRAINTE, PAS UN RÉGLAGE. Le Mac Mini a 16 Go unifiés, dont au
plus 7,5 Go pour le LLM et son cache. En quantification Q4, un modèle pèse grossièrement
0,6 Go par milliard de paramètres — 7B ≈ 4,5 Go, 9B ≈ 5,5 Go — et chaque requête
concurrente y ajoute son contexte. C'est un ORDRE DE GRANDEUR, pas une mesure : la seule
vraie mesure est celle que `scripts/benchmark_nlp.py` lit sur le processus d'inférence.
La concurrence par défaut est de 2, parce qu'au-delà on entre dans la zone où macOS
échange sur disque — et une latence qui explose ressemble exactement à une panne de
modèle.
Plus le modèle est gros, plus cette marge se referme : sur un 9B,
`QUANT_NLP_CONCURRENCE=1` est prudent si le banc montre une p90 qui décroche.

AUCUN MODÈLE N'EST ÉCRIT EN DUR. Un identifiant figé dans le code devient faux dès que
l'utilisateur change de modèle, et il ment en SILENCE : le fournisseur sert ce qu'il a
chargé, le signal repart estampillé du nom qu'on croyait. `pilotes.resoudre_modele()`
demande donc au fournisseur ce qu'il expose. `LOCAL_TRADING_MODEL` reste le mot de la
fin quand plusieurs modèles sont exposés.

UN SEUL MODÈLE ACTIF À LA FOIS. Deux modèles chargés simultanément peuvent tenir en
mémoire, mais alterner entre eux fait payer un rechargement à chaque bascule. Le
comparatif se fait donc en série (`scripts/benchmark_nlp.py`), jamais en parallèle.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

# Défauts pensés pour LM Studio sur Mac Mini M4 16 Go.
# VIDE À DESSEIN : « je ne sais pas quel modèle est chargé » est la vérité tant qu'on
# n'a pas interrogé le fournisseur. Un nom plausible ici serait une supposition que tout le
# reste de la chaîne propagerait comme un fait. Cf. `pilotes.resoudre_modele()`.
MODELE_DEFAUT = ""
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

    def avec_modele(self, modele: str) -> ConfigNLP:
        """La même config, avec le modèle RÉSOLU. `replace` plutôt qu'une mutation :
        la config est gelée pour qu'une trace de signal ne change pas après coup."""
        return replace(self, modele=modele)

    def resume(self) -> str:
        nom = self.modele or "(à découvrir auprès du fournisseur)"
        return (f"{nom} · pilote {self.pilote} · timeout {self.timeout_s:.0f} s · "
                f"concurrence {self.concurrence} · cache {self.cache_max}")
