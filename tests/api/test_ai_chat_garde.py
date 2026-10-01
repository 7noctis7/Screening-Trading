"""`/api/ai/chat` est fermée aux appels non locaux, comme les autres routes POST.

Contexte (audit du 01/10, B6) : la route n'appelait pas `_webhook_authorized`.
Exposée par `make api-lan` ou par le Dockerfile (`--host 0.0.0.0`), elle aurait
consommé la clé LLM de l'environnement pour n'importe quel appelant.

Importer `apps.api.main` ne construit pas le snapshot (seul l'événement `startup`
le fait) : on appelle donc la route directement.
"""

from types import SimpleNamespace

import pytest

main = pytest.importorskip("apps.api.main")


def _requete(hote: str, entetes: dict | None = None):
    return SimpleNamespace(client=SimpleNamespace(host=hote), headers=entetes or {})


@pytest.fixture
def appels(monkeypatch):
    """Doublure du copilote : enregistre les appels, ne contacte aucun LLM."""
    vus: list[str] = []

    def repondre(question, *_a, **_k):
        vus.append(question)
        return {"available": True, "answer": "ok"}

    monkeypatch.setattr("packages.llm.assistant.answer_question", repondre)
    monkeypatch.setattr(main, "_snap", lambda: {})
    monkeypatch.setattr(main, "_WEBHOOK_TOKEN", "")
    return vus


def _corps():
    return main.AIChatRequest(question="quel est le régime ?")


def test_un_appel_distant_est_refuse_sans_atteindre_le_llm(appels):
    r = main.ai_chat(_corps(), _requete("203.0.113.7"))
    assert r == {"available": False, "reason": "endpoint local uniquement"}
    assert appels == []


def test_un_appel_local_passe(appels):
    r = main.ai_chat(_corps(), _requete("127.0.0.1"))
    assert r["available"] is True and appels == ["quel est le régime ?"]


def test_avec_jeton_seul_le_bon_jeton_passe(monkeypatch, appels):
    monkeypatch.setattr(main, "_WEBHOOK_TOKEN", "secret-de-test")
    faux = _requete("127.0.0.1", {"X-Webhook-Token": "faux"})
    bon = _requete("203.0.113.7", {"X-Webhook-Token": "secret-de-test"})
    refuse, accepte = main.ai_chat(_corps(), faux), main.ai_chat(_corps(), bon)
    assert refuse["available"] is False and accepte["available"] is True
    assert len(appels) == 1
