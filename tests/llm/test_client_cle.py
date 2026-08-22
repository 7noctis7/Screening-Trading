"""Sans en-tête d'autorisation, le client ne savait parler qu'à un modèle LOCAL.

Brancher OpenAI, Anthropic ou Mistral échouait en 401 sans que rien ne l'explique. C'est le seul
obstacle qui empêchait un utilisateur auto-hébergé d'utiliser SON fournisseur.
"""
import importlib
import os

import packages.llm.client as client


def _recharge(**env):
    for k in ("LLM_API_KEY", "LLM_BASE_URL"):
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    return importlib.reload(client)


def test_sans_cle_aucun_en_tete_dautorisation():
    """Un modèle local (LM Studio, Ollama) n'en demande pas — en envoyer un serait du bruit."""
    c = _recharge()
    assert "Authorization" not in c._headers(json=True)
    assert c._headers(json=True)["Content-Type"] == "application/json"


def test_avec_cle_len_tete_est_pose():
    c = _recharge(LLM_API_KEY="sk-abc123")
    assert c._headers(json=True)["Authorization"] == "Bearer sk-abc123"


def test_len_tete_est_pose_aussi_sur_les_requetes_de_decouverte():
    """La détection du modèle interroge /models : sans clé, elle échouait avant même le premier appel."""
    c = _recharge(LLM_API_KEY="sk-abc123")
    assert c._headers()["Authorization"] == "Bearer sk-abc123"
    assert "Content-Type" not in c._headers()


def test_une_cle_vide_equivaut_a_pas_de_cle():
    c = _recharge(LLM_API_KEY="")
    assert "Authorization" not in c._headers(json=True)


def test_lurl_de_base_reste_surchargeable():
    """Tout fournisseur compatible OpenAI convient : seule l'URL de base change."""
    c = _recharge(LLM_BASE_URL="https://api.exemple.test/v1", LLM_API_KEY="k")
    assert c._BASE == "https://api.exemple.test/v1"
    _recharge()
