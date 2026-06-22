"""LLM LOCAL gratuit via Ollama (FinOps : décharge les tâches simples de l'API payante).

`cheap_llm()` parle à l'API native d'Ollama (`/api/chat`, défaut `gemma3n:e4b`). `smart_text()`
ROUTE : tâche simple → modèle local gratuit en priorité ; repli sur le serveur OpenAI-compatible
(LM Studio via `packages.llm.client.complete`) ; rien si tout est éteint. stdlib pure (urllib),
jamais bloquant. Réserve Claude/API payante au raisonnement complexe.

Config : OLLAMA_HOST (défaut 127.0.0.1:11434), QUANT_LOCAL_LLM (défaut gemma3n:e4b).
"""
from __future__ import annotations

import json
import os
import urllib.request


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def available() -> bool:
    """True si un serveur Ollama répond (au moins un modèle téléchargé)."""
    try:
        req = urllib.request.Request(f"{_host()}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:  # noqa: S310 — hôte local contrôlé
            return bool(json.loads(r.read().decode()).get("models"))
    except Exception:  # noqa: BLE001
        return False


def cheap_llm(prompt: str, system: str = "", model: str | None = None,
              temperature: float = 0.3, timeout: float = 60.0) -> str | None:
    """Complétion via un petit modèle local (Ollama). None si serveur absent/erreur (jamais bloquant)."""
    model = model or os.environ.get("QUANT_LOCAL_LLM", "gemma3n:e4b")
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    body = json.dumps({"model": model, "stream": False, "messages": msgs,
                       "options": {"temperature": temperature}}).encode()
    try:
        req = urllib.request.Request(f"{_host()}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — hôte local
            data = json.loads(r.read().decode())
        return (data.get("message", {}).get("content") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def smart_text(prompt: str, system: str = "", complex: bool = False) -> str | None:
    """Routeur FinOps : tâche SIMPLE → Ollama local (gratuit) d'abord ; sinon repli LM Studio.
    Renvoie le texte ou None. Pour le raisonnement lourd, passer complex=True (saute le local)."""
    if not complex:
        t = cheap_llm(prompt, system)
        if t:
            return t
    try:
        from packages.llm.client import complete
        res = complete(prompt, system=system)
        return (res.get("text") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None
