"""LLM local (LM Studio / Ollama) — commentaires IA privés, gratuits, hors-ligne-safe."""
from packages.llm.client import available, complete
from packages.llm.local import cheap_llm, smart_text

__all__ = ["available", "complete", "cheap_llm", "smart_text"]
