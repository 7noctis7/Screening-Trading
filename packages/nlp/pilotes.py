"""Deux fournisseurs, une interface — LM Studio et Ollama.

POURQUOI DEUX. LM Studio expose une API compatible OpenAI (`/v1/chat/completions`), Ollama
une API native (`/api/chat`). Les deux savent contraindre la sortie à un schéma JSON, mais
par des champs DIFFÉRENTS : `response_format.json_schema` d'un côté, `format` de l'autre.
Écrire le code contre un seul enfermerait le projet dans ce fournisseur, alors que le choix
dépend de ce qui est installé sur la machine — LM Studio ici, Ollama sur une autre.

CE QUE LES PILOTES NE FONT PAS. Ils n'interprètent rien, ne réessaient pas, ne décident pas
du repli. Ils envoient, lisent, et rendent un dictionnaire ou `None`. Le moteur décide.
Cette séparation est ce qui rend le moteur testable sans réseau.

Bibliothèque standard uniquement : ce paquet doit fonctionner dans l'environnement allégé
de la CI, où ni `requests` ni `openai` ne sont installés.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from packages.nlp.schemas import SCHEMA

LMSTUDIO_BASE = "http://localhost:1234/v1"
OLLAMA_BASE = "http://127.0.0.1:11434"
NOM_SCHEMA = "signal_marche"


def _poster(url: str, charge: dict, timeout: float) -> dict | None:
    """POST JSON → dict, ou `None`. Aucune exception ne sort d'ici."""
    donnees = json.dumps(charge).encode("utf-8")
    req = urllib.request.Request(url, data=donnees,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — hôte local
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _obtenir(url: str, timeout: float) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _json_dans(texte: str) -> dict | None:
    """Lit le JSON d'une réponse. Tolère un préambule, refuse de deviner.

    La sortie structurée devrait rendre ce nettoyage inutile ; il existe parce qu'un modèle
    quantifié agressif ajoute parfois « ```json » autour. On retire les clôtures de bloc et
    on tente UN décodage — pas d'extraction par expression régulière, qui accepterait un
    JSON tronqué en croyant l'avoir compris.
    """
    t = (texte or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        t = t.rsplit("```", 1)[0].strip()
    try:
        charge = json.loads(t)
    except Exception:  # noqa: BLE001
        return None
    return charge if isinstance(charge, dict) else None


@dataclass
class PiloteLMStudio:
    """API compatible OpenAI — LM Studio, vLLM, llama.cpp server, Jan…"""

    modele: str
    base: str = LMSTUDIO_BASE
    nom: str = "lmstudio"

    def disponible(self, timeout: float = 3.0) -> bool:
        d = _obtenir(f"{self.base.rstrip('/')}/models", timeout)
        return bool(d and d.get("data"))

    def modeles(self, timeout: float = 3.0) -> list[str]:
        d = _obtenir(f"{self.base.rstrip('/')}/models", timeout) or {}
        return [str(m.get("id", "")) for m in (d.get("data") or [])]

    def classer(self, systeme: str, utilisateur: str, timeout: float) -> dict | None:
        charge = {
            "model": self.modele,
            "messages": [{"role": "system", "content": systeme},
                         {"role": "user", "content": utilisateur}],
            "temperature": 0.0,       # une classification n'a pas à varier d'un appel à l'autre
            "max_tokens": 400,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": NOM_SCHEMA, "strict": True, "schema": SCHEMA},
            },
        }
        d = _poster(f"{self.base.rstrip('/')}/chat/completions", charge, timeout)
        if not d:
            return None
        try:
            return _json_dans(d["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            return None


@dataclass
class PiloteOllama:
    """API native Ollama. `format` accepte directement un schéma JSON depuis la 0.5."""

    modele: str
    base: str = OLLAMA_BASE
    nom: str = "ollama"

    def disponible(self, timeout: float = 3.0) -> bool:
        d = _obtenir(f"{self.base.rstrip('/')}/api/tags", timeout)
        return bool(d and d.get("models"))

    def modeles(self, timeout: float = 3.0) -> list[str]:
        d = _obtenir(f"{self.base.rstrip('/')}/api/tags", timeout) or {}
        return [str(m.get("name", "")) for m in (d.get("models") or [])]

    def classer(self, systeme: str, utilisateur: str, timeout: float) -> dict | None:
        charge = {
            "model": self.modele,
            "messages": [{"role": "system", "content": systeme},
                         {"role": "user", "content": utilisateur}],
            "stream": False,
            "format": SCHEMA,
            "options": {"temperature": 0.0},
        }
        d = _poster(f"{self.base.rstrip('/')}/api/chat", charge, timeout)
        if not d:
            return None
        try:
            return _json_dans(d["message"]["content"])
        except Exception:  # noqa: BLE001
            return None


def choisir(modele: str, pilote: str = "auto", base: str = "",
            timeout: float = 3.0):
    """Le pilote à utiliser, ou `None` si aucun fournisseur ne répond.

    En mode `auto`, LM Studio est essayé d'abord : c'est ce qui est installé sur le poste
    de développement. L'ordre est un défaut, pas une préférence technique — `QUANT_NLP_PILOTE`
    tranche quand les deux tournent.
    """
    if pilote == "lmstudio":
        return PiloteLMStudio(modele, base or LMSTUDIO_BASE)
    if pilote == "ollama":
        return PiloteOllama(modele, base or OLLAMA_BASE)
    for p in (PiloteLMStudio(modele, base or LMSTUDIO_BASE),
              PiloteOllama(modele, base or OLLAMA_BASE)):
        if p.disponible(timeout):
            return p
    return None
