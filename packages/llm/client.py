"""Client LLM **local** compatible OpenAI (LM Studio / Ollama / vLLM) — gratuit & privé.

LM Studio expose une API OpenAI sur http://localhost:1234/v1. On l'utilise pour générer des
commentaires en langage naturel (revue de portefeuille, explication de signal, résumé de news).
Rien ne sort de la machine. stdlib pure (urllib), **dégrade proprement** si aucun serveur local.

Config : LLM_BASE_URL (défaut LM Studio), LLM_MODEL (sinon auto-détecté), LLM_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import urllib.request

_BASE = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))


def _get(path: str):
    req = urllib.request.Request(f"{_BASE}{path}")
    with urllib.request.urlopen(req, timeout=4) as r:  # noqa: S310 (URL locale contrôlée)
        return json.loads(r.read().decode())


def available() -> bool:
    """True si un serveur LLM local répond (LM Studio lancé avec un modèle chargé)."""
    try:
        data = _get("/models")
        return bool(data.get("data"))
    except Exception:  # noqa: BLE001
        return False


def _default_model() -> str:
    if os.environ.get("LLM_MODEL"):
        return os.environ["LLM_MODEL"]
    try:
        return _get("/models")["data"][0]["id"]
    except Exception:  # noqa: BLE001
        return "local-model"


def complete(prompt: str, system: str = "", temperature: float = 0.3,
             max_tokens: int = 400) -> dict:
    """Chat completion. Renvoie {available, text} ; available=False si serveur injoignable."""
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    body = json.dumps({"model": _default_model(), "messages": msgs,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    try:
        req = urllib.request.Request(f"{_BASE}/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310
            data = json.loads(r.read().decode())
        return {"available": True, "text": data["choices"][0]["message"]["content"].strip()}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": "", "reason": str(e)[:120]}
