def test_cheap_llm_offline_returns_none(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")   # port mort → refus immédiat
    from packages.llm.local import cheap_llm
    assert cheap_llm("ping") is None


def test_smart_text_offline_returns_none(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    from packages.llm import smart_text
    # local KO + LM Studio KO → repli propre sur None (jamais d'exception)
    assert smart_text("x", complex=False) is None
