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
from dataclasses import dataclass

_BASE = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
# Clé du FOURNISSEUR de l'utilisateur. Absente = modèle local (LM Studio / Ollama n'en demandent
# pas). Sans cet en-tête, brancher un fournisseur distant échouait en 401 sans que rien ne le
# dise : le client ne savait parler qu'à un modèle local.
#
# La clé n'est lue QUE depuis l'environnement du poste qui exécute l'API. Elle n'est jamais
# demandée dans le navigateur ni transmise ailleurs — sur une instance auto-hébergée, elle ne
# quitte pas la machine de son propriétaire.
_KEY = os.environ.get("LLM_API_KEY", "")
_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))


@dataclass(frozen=True)
class Config:
    """Où appeler, avec quelle clé, quel modèle. Résolue à CHAQUE appel, jamais mémorisée.

    Pourquoi une config par appel plutôt qu'une variable d'environnement seule : éditer un
    fichier `.env` puis relancer l'API pour changer de fournisseur est un obstacle réel. La
    config peut donc venir de l'appelant (l'interface web transmet celle de l'utilisateur).

    Elle n'est ni écrite sur disque, ni journalisée, ni renvoyée dans une réponse : elle vit le
    temps de la requête. Une clé qu'on n'écrit jamais ne peut pas être commitée par erreur.
    """
    base: str = ""
    key: str = ""
    model: str = ""

    def resolue(self) -> Config:
        """Complète les champs vides par l'environnement. L'appelant a la priorité."""
        return Config(base=(self.base or _BASE).rstrip("/"),
                      key=self.key or _KEY,
                      model=self.model or os.environ.get("LLM_MODEL", ""))


def _headers(cfg: Config, json: bool = False) -> dict:
    h = {"Content-Type": "application/json"} if json else {}
    if cfg.key:
        h["Authorization"] = f"Bearer {cfg.key}"
    return h


def _get(path: str, cfg: Config | None = None):
    c = (cfg or Config()).resolue()
    req = urllib.request.Request(f"{c.base}{path}", headers=_headers(c))
    with urllib.request.urlopen(req, timeout=6) as r:  # noqa: S310 — URL fournie par l'opérateur
        return json.loads(r.read().decode())


def available(cfg: Config | None = None) -> bool:
    """True si le fournisseur répond (modèle local chargé, ou clé distante valide)."""
    try:
        return bool(_get("/models", cfg).get("data"))
    except Exception:  # noqa: BLE001
        return False


def diagnostic(cfg: Config | None = None) -> dict:
    """Teste la connexion et DIT pourquoi elle échoue. Ne renvoie jamais la clé.

    Un « indisponible » sans motif est le pire retour possible : l'utilisateur ne sait pas s'il
    s'est trompé d'URL, de clé, ou si son modèle local n'est pas lancé. On distingue donc les cas.
    """
    c = (cfg or Config()).resolue()
    try:
        data = _get("/models", c)
        modeles = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        return {"ok": bool(modeles), "modeles": modeles[:20], "base": c.base,
                "cle_fournie": bool(c.key),
                "motif": "" if modeles else "le fournisseur répond mais n'annonce aucun modèle"}
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        motif = ("clé refusée (401/403) — vérifiez la clé et qu'elle correspond bien au "
                 "fournisseur de l'URL" if "401" in msg or "403" in msg else
                 "adresse introuvable (404) — vérifiez l'URL de base" if "404" in msg else
                 "aucun serveur ne répond — modèle local non lancé, ou URL inaccessible"
                 if "refus" in msg.lower() or "urlopen" in msg.lower() else msg[:160])
        return {"ok": False, "modeles": [], "base": c.base, "cle_fournie": bool(c.key),
                "motif": motif}


def _default_model(cfg: Config | None = None) -> str:
    c = (cfg or Config()).resolue()
    if c.model:
        return c.model
    try:
        return _get("/models", c)["data"][0]["id"]
    except Exception:  # noqa: BLE001
        return "local-model"


def complete(prompt: str, system: str = "", temperature: float = 0.3,
             max_tokens: int = 1100, cfg: Config | None = None) -> dict:
    """Chat completion. Renvoie {available, text} ; available=False si le fournisseur ne répond pas."""
    c = (cfg or Config()).resolue()
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    body = json.dumps({"model": _default_model(c), "messages": msgs,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    try:
        req = urllib.request.Request(f"{c.base}/chat/completions", data=body,
                                     headers=_headers(c, json=True))
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:  # noqa: S310
            data = json.loads(r.read().decode())
        msg = data["choices"][0].get("message", {})
        # modèles « raisonneurs » (gemma, etc.) : si content vide, récupérer reasoning_content
        txt = (msg.get("content") or "").strip() or (msg.get("reasoning_content") or "").strip()
        return {"available": True, "text": txt}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": "", "reason": str(e)[:120]}
