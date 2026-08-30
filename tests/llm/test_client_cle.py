"""Sans en-tête d'autorisation, le client ne savait parler qu'à un modèle LOCAL.

Brancher OpenAI, Anthropic ou Mistral échouait en 401 sans que rien ne l'explique. C'est le seul
obstacle qui empêchait un utilisateur auto-hébergé d'utiliser SON fournisseur.
"""

import importlib
import io
import json
import os
import urllib.error

import packages.llm.client as client


def _recharge(**env):
    for k in ("LLM_API_KEY", "LLM_BASE_URL"):
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    return importlib.reload(client)


def test_sans_cle_aucun_en_tete_dautorisation():
    """Un modèle local (LM Studio, Ollama) n'en demande pas — en envoyer un serait du bruit."""
    c = _recharge()
    cfg = c.Config().resolue()
    assert "Authorization" not in c._headers(cfg, json=True)
    assert c._headers(cfg, json=True)["Content-Type"] == "application/json"


def test_avec_cle_len_tete_est_pose():
    c = _recharge(LLM_API_KEY="sk-abc123")
    assert (
        c._headers(c.Config().resolue(), json=True)["Authorization"]
        == "Bearer sk-abc123"
    )


def test_len_tete_est_pose_aussi_sur_les_requetes_de_decouverte():
    """La détection du modèle interroge /models : sans clé, elle échouait avant même le premier appel."""
    c = _recharge(LLM_API_KEY="sk-abc123")
    cfg = c.Config().resolue()
    assert c._headers(cfg)["Authorization"] == "Bearer sk-abc123"
    assert "Content-Type" not in c._headers(cfg)


def test_une_cle_vide_equivaut_a_pas_de_cle():
    c = _recharge(LLM_API_KEY="")
    assert "Authorization" not in c._headers(c.Config().resolue(), json=True)


# --- Config PAR APPEL : l'appelant prime sur l'environnement ---------------------------------


def test_la_config_de_lappelant_prime_sur_lenvironnement():
    """C'est ce qui permet de changer de fournisseur depuis l'interface, sans toucher au .env."""
    c = _recharge(LLM_API_KEY="sk-env", LLM_BASE_URL="http://local/v1")
    cfg = c.Config(
        base="https://api.exemple.test/v1", key="sk-appelant", model="m"
    ).resolue()
    assert cfg.base == "https://api.exemple.test/v1"
    assert cfg.key == "sk-appelant"
    assert c._headers(cfg)["Authorization"] == "Bearer sk-appelant"


def test_les_champs_vides_retombent_sur_lenvironnement():
    """Une config partielle ne doit pas effacer ce qui est déjà configuré sur la machine."""
    c = _recharge(LLM_API_KEY="sk-env", LLM_BASE_URL="http://local/v1")
    cfg = c.Config(model="autre-modele").resolue()
    assert cfg.base == "http://local/v1" and cfg.key == "sk-env"
    assert cfg.model == "autre-modele"


def test_la_barre_finale_de_lurl_est_normalisee():
    """Sans cela, « .../v1/ » produirait « .../v1//chat/completions » et un 404 obscur."""
    c = _recharge()
    assert c.Config(base="https://x.test/v1/").resolue().base == "https://x.test/v1"


def test_la_config_nest_jamais_conservee_entre_deux_appels():
    """Une clé mémorisée serait une clé qui fuit d'un utilisateur à l'autre."""
    c = _recharge(LLM_API_KEY="sk-env")
    c.Config(key="sk-jetable").resolue()
    assert c.Config().resolue().key == "sk-env"


def test_lurl_de_base_reste_surchargeable():
    """Tout fournisseur compatible OpenAI convient : seule l'URL de base change."""
    c = _recharge(LLM_BASE_URL="https://api.exemple.test/v1", LLM_API_KEY="k")
    assert c._BASE == "https://api.exemple.test/v1"
    _recharge()


class _Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.body


def test_gemini_404_compatibilite_replie_sur_api_native(monkeypatch):
    c = _recharge()
    calls = []

    def fake(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            body = io.BytesIO(b'{"error":{"message":"route absente"}}')
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, body)
        return _Response(
            {"candidates": [{"content": {"parts": [{"text": "réponse"}]}}]}
        )

    monkeypatch.setattr(c.urllib.request, "urlopen", fake)
    cfg = c.Config(
        base="https://generativelanguage.googleapis.com/v1beta/openai",
        key="AIza-secret",
        model="configured-flash",
    )
    out = c.complete("question", system="système", cfg=cfg)
    assert out == {"available": True, "text": "réponse", "transport": "gemini-native"}
    assert calls[0].full_url.endswith("/openai/chat/completions")
    assert calls[1].full_url.endswith("/v1beta/models/configured-flash:generateContent")
    assert calls[1].headers["X-goog-api-key"] == "AIza-secret"


def test_gemini_retire_choisit_un_modele_du_catalogue(monkeypatch):
    c = _recharge()
    calls = []

    def fake(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))
        if len(calls) == 2:
            body = io.BytesIO(b'{"error":{"message":"model no longer available"}}')
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, body)
        if len(calls) == 3:
            return _Response({"data": [{"id": "retired-flash"}, {"id": "current-flash"}]})
        return _Response({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    monkeypatch.setattr(c.urllib.request, "urlopen", fake)
    cfg = c.Config(
        base="https://generativelanguage.googleapis.com/v1beta/openai",
        key="secret",
        model="retired-flash",
    )

    out = c.complete("question", cfg=cfg)

    assert out["available"] is True
    assert out["transport"] == "gemini-native-auto"
    assert out["model"] == "current-flash"
    assert calls[-1].full_url.endswith("/models/current-flash:generateContent")


def test_erreur_http_restitue_le_message_du_fournisseur(monkeypatch):
    c = _recharge()

    def fake(req, timeout):
        body = io.BytesIO(b'{"error":{"message":"modele retire"}}')
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(c.urllib.request, "urlopen", fake)
    cfg = c.Config(base="https://api.exemple.test/v1", key="secret", model="modele")
    out = c.complete("question", cfg=cfg)
    assert out["available"] is False and out["reason"] == "modele retire"
