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
import urllib.error
import urllib.parse
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
        return Config(
            base=(self.base or _BASE).rstrip("/"),
            key=self.key or _KEY,
            model=self.model or os.environ.get("LLM_MODEL", ""),
        )


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


def _connu(modele: str, catalogue: list[str]) -> bool:
    """Le modèle demandé figure-t-il au catalogue du fournisseur ?

    Comparaison tolérante au préfixe `models/`. Un catalogue vide ne prouve rien → on ne bloque
    pas."""
    if not modele or not catalogue:
        return True
    cible = modele.split("/")[-1].strip().lower()
    return any(m.split("/")[-1].strip().lower() == cible for m in catalogue)


def available(cfg: Config | None = None) -> bool:
    """True si le fournisseur répond ET sert le modèle demandé.

    Tester seulement `/models` produisait un « ● connecté » suivi d'un 404 à la génération : le
    fournisseur répondait bien, mais pas pour CE modèle. Un voyant vert doit tester ce que fera
    le bouton, pas autre chose (cas réel du 25/08 : base d'un fournisseur, modèle d'un autre)."""
    c = (cfg or Config()).resolue()
    try:
        catalogue = [
            m.get("id") for m in (_get("/models", c).get("data") or []) if m.get("id")
        ]
    except Exception:  # noqa: BLE001
        return False
    return bool(catalogue) and _connu(c.model, catalogue)


def diagnostic(cfg: Config | None = None) -> dict:
    """Teste la connexion et DIT pourquoi elle échoue. Ne renvoie jamais la clé.

    Un « indisponible » sans motif est le pire retour possible : l'utilisateur ne sait pas s'il
    s'est trompé d'URL, de clé, ou si son modèle local n'est pas lancé. On distingue donc les cas.
    """
    c = (cfg or Config()).resolue()
    try:
        data = _get("/models", c)
        modeles = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
        if modeles and not _connu(c.model, modeles):
            # LE cas qui produisait « connecté » puis « 404 » : l'URL d'un fournisseur avec le
            # nom de modèle d'un autre (base LM Studio + modèle « gemini-… », par exemple).
            return {
                "ok": False,
                "modeles": modeles[:20],
                "base": c.base,
                "cle_fournie": bool(c.key),
                "modele": c.model,
                "motif": f"le fournisseur répond sur {c.base} mais ne connaît pas le modèle "
                f"« {c.model} » — base et modèle doivent venir du MÊME fournisseur. "
                f"Modèles servis ici : {', '.join(modeles[:5])}",
            }
        return {
            "ok": bool(modeles),
            "modeles": modeles[:20],
            "base": c.base,
            "cle_fournie": bool(c.key),
            "modele": c.model,
            "motif": ""
            if modeles
            else "le fournisseur répond mais n'annonce aucun modèle",
        }
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        motif = (
            "clé refusée (401/403) — vérifiez la clé et qu'elle correspond bien au "
            "fournisseur de l'URL"
            if "401" in msg or "403" in msg
            else f"adresse introuvable (404) sur {c.base}/models — vérifiez l'URL de base"
            if "404" in msg
            else "aucun serveur ne répond — modèle local non lancé, ou URL inaccessible"
            if "refus" in msg.lower() or "urlopen" in msg.lower()
            else msg[:160]
        )
        return {
            "ok": False,
            "modeles": [],
            "base": c.base,
            "cle_fournie": bool(c.key),
            "motif": motif,
        }


def _default_model(cfg: Config | None = None) -> str:
    c = (cfg or Config()).resolue()
    if c.model:
        return c.model
    try:
        return _get("/models", c)["data"][0]["id"]
    except Exception:  # noqa: BLE001
        return "local-model"


def _alternative_model(c: Config, current: str) -> str:
    """Choisit dans le catalogue un modèle texte différent, sans nom périssable codé en dur."""
    try:
        models = [m.get("id", "") for m in (_get("/models", c).get("data") or [])]
    except Exception:  # noqa: BLE001
        return ""
    blocked = ("embedding", "image", "audio", "tts", "vision")
    candidates = [
        model
        for model in models
        if model
        and not _connu(current, [model])
        and not any(word in model.lower() for word in blocked)
    ]
    candidates.sort(
        key=lambda model: ("flash" not in model.lower(), "latest" not in model.lower())
    )
    return candidates[0] if candidates else ""


def _openai_body(
    prompt: str, system: str, temperature: float, max_tokens: int, model: str
) -> bytes:
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    return json.dumps(
        {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode()


def _post_openai(c: Config, body: bytes) -> str:
    req = urllib.request.Request(
        f"{c.base}/chat/completions", data=body, headers=_headers(c, json=True)
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:  # noqa: S310
        data = json.loads(response.read().decode())
    msg = data["choices"][0].get("message", {})
    return (msg.get("content") or "").strip() or (
        msg.get("reasoning_content") or ""
    ).strip()


def _is_gemini(c: Config) -> bool:
    return "generativelanguage.googleapis.com" in c.base.lower()


def _post_gemini_native(
    c: Config,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    model: str = "",
) -> str:
    """Repli sur l'API Gemini native si sa couche compatible renvoie 404."""
    root = c.base.split("/openai", 1)[0].rstrip("/")
    selected = urllib.parse.quote(
        (model or _default_model(c)).split("/")[-1], safe="-._"
    )
    url = f"{root}/models/{selected}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    headers = {"Content-Type": "application/json", "x-goog-api-key": c.key}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:  # noqa: S310
        data = json.loads(response.read().decode())
    parts = data["candidates"][0]["content"].get("parts", [])
    return "\n".join(str(part.get("text", "")).strip() for part in parts).strip()


def _error_detail(exc: Exception) -> str:
    if not isinstance(exc, urllib.error.HTTPError):
        return str(exc)[:180]
    try:
        body = exc.read().decode(errors="replace")
        data = json.loads(body)
        return str(data.get("error", {}).get("message") or body)[:180]
    except Exception:  # noqa: BLE001 — diagnostic d'erreur uniquement
        return str(exc)[:180]


def complete(
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 1100,
    cfg: Config | None = None,
) -> dict:
    """Chat completion. Renvoie {available, text} ; available=False si le fournisseur ne répond pas."""
    c = (cfg or Config()).resolue()
    model = _default_model(c)
    body = _openai_body(prompt, system, temperature, max_tokens, model)
    try:
        return {
            "available": True,
            "text": _post_openai(c, body),
            "transport": "openai-compatible",
        }
    except urllib.error.HTTPError as first:
        if _is_gemini(c) and first.code == 404:
            try:
                text = _post_gemini_native(
                    c, prompt, system, temperature, max_tokens, model
                )
                return {"available": True, "text": text, "transport": "gemini-native"}
            except urllib.error.HTTPError as native:
                alternative = (
                    _alternative_model(c, model) if native.code in (400, 404) else ""
                )
                if alternative:
                    try:
                        text = _post_gemini_native(
                            c, prompt, system, temperature, max_tokens, alternative
                        )
                        return {
                            "available": True,
                            "text": text,
                            "transport": "gemini-native-auto",
                            "model": alternative,
                        }
                    except Exception as retry:  # noqa: BLE001
                        native = retry
                reason = f"compatibilité: {_error_detail(first)} ; natif: {_error_detail(native)}"
                return {"available": False, "text": "", "reason": reason}
            except Exception as native:  # noqa: BLE001
                reason = f"compatibilité: {_error_detail(first)} ; natif: {_error_detail(native)}"
                return {"available": False, "text": "", "reason": reason}
        return {"available": False, "text": "", "reason": _error_detail(first)}
    except Exception as e:  # noqa: BLE001
        return {
            "available": False,
            "text": "",
            "reason": f"{_error_detail(e)} — appel POST {c.base}/chat/completions, "
            f"modèle « {model or '(auto)'} »",
        }
