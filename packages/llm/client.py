"""Client LLM **local** compatible OpenAI (LM Studio / Ollama / vLLM) — gratuit & privé.

LM Studio expose une API OpenAI sur http://localhost:1234/v1. On l'utilise pour générer des
commentaires en langage naturel (revue de portefeuille, explication de signal, résumé de news).
Rien ne sort de la machine. stdlib pure (urllib), **dégrade proprement** si aucun serveur local.

Config : LLM_BASE_URL (défaut LM Studio), LLM_MODEL (sinon auto-détecté), LLM_TIMEOUT,
LLM_API_KEY (facultative — absente pour un modèle local, requise par tout fournisseur distant).
Tout fournisseur exposant une API compatible OpenAI convient ; seule l'URL de base change.
"""

from __future__ import annotations

import json
import os
import urllib.request

_BASE = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
# Clé du FOURNISSEUR de l'utilisateur. Absente = modèle local (LM Studio / Ollama n'en demandent
# pas). Sans cet en-tête, brancher un fournisseur distant échouait en 401 sans que rien ne le
# dise : le client ne savait parler qu'à un modèle local.
#
# La clé n'est lue QUE depuis l'environnement du poste qui exécute l'API. Elle n'est jamais
# demandée dans le navigateur ni transmise ailleurs — sur une instance auto-hébergée, elle ne
# quitte pas la machine de son propriétaire.
_KEY = os.environ.get("LLM_API_KEY", "")


def _headers(json: bool = False) -> dict:
    h = {"Content-Type": "application/json"} if json else {}
    if _KEY:
        h["Authorization"] = f"Bearer {_KEY}"
    return h
_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))


def _get(path: str):
    req = urllib.request.Request(f"{_BASE}{path}", headers=_headers())
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
             max_tokens: int = 1100) -> dict:
    """Chat completion. Renvoie {available, text} ; available=False si serveur injoignable."""
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    body = json.dumps({"model": _default_model(), "messages": msgs,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    try:
        req = urllib.request.Request(f"{_BASE}/chat/completions", data=body,
                                     headers=_headers(json=True))
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310
            data = json.loads(r.read().decode())
        msg = data["choices"][0].get("message", {})
        # modèles « raisonneurs » (gemma, etc.) : si content vide, récupérer reasoning_content
        txt = (msg.get("content") or "").strip() or (msg.get("reasoning_content") or "").strip()
        return {"available": True, "text": txt}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": "", "reason": str(e)[:120]}
