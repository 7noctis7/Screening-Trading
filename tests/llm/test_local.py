def test_cheap_llm_offline_returns_none(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")   # port mort → refus immédiat
    from packages.llm.local import cheap_llm
    assert cheap_llm("ping") is None


def test_smart_text_returns_none_when_all_providers_down(monkeypatch):
    """Déterministe : on simule les 2 fournisseurs ÉTEINTS (peu importe ce qui tourne en local)."""
    import packages.llm.client as client
    import packages.llm.local as local
    monkeypatch.setattr(local, "cheap_llm", lambda *a, **k: None)          # Ollama KO
    monkeypatch.setattr(client, "complete", lambda *a, **k: {"available": False, "text": ""})  # LM Studio KO
    assert local.smart_text("x", complex=False) is None


def test_smart_text_prefers_local_for_simple_tasks(monkeypatch):
    """Tâche simple → modèle LOCAL (gratuit) utilisé en priorité (FinOps), sans toucher l'API payante."""
    import packages.llm.local as local
    monkeypatch.setattr(local, "cheap_llm", lambda *a, **k: "réponse locale")
    assert local.smart_text("résume ceci", complex=False) == "réponse locale"
