"""Stockage vectoriel pour enregistrements DB (journal trades).

Indexe les champs texte (entry_reason, exit_reason, strategy, regime) en vecteurs
TF-IDF ou Ollama. SQLite local, compatible avec le journal existant.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path

import numpy as np

from packages.storage.journal_sqlite import SqliteTradeJournal

_DEFAULT_VEC_DB = "data/vectors.db"


def _tokens(text: str) -> list[str]:
    import re
    return [w.lower() for w in re.findall(r"[a-zA-ZàâäéèêëîïôöùûüçœÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒ0-9_]{2,}", text)]


def _tfidf_vec(text: str, idf: dict) -> dict:
    tf: dict[str, float] = {}
    for t in _tokens(text):
        tf[t] = tf.get(t, 0.0) + 1.0
    v = {t: w * idf.get(t, 0.0) for t, w in tf.items()}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: w / norm for t, w in v.items()}


def _ollama_embed(text: str) -> list[float] | None:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.environ.get("QUANT_EMBED_MODEL", "nomic-embed-text")
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{host}/api/embeddings",
            data=json.dumps({"model": model, "prompt": text[:4000]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["embedding"]
    except Exception:
        return None


class VectorStore:
    def __init__(self, db_path: str | Path = _DEFAULT_VEC_DB):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                source TEXT,  -- 'journal' | 'vault'
                text TEXT,
                vector BLOB,  -- json list or numpy
                method TEXT   -- 'tfidf' | 'ollama'
            )"""
        )
        self.conn.commit()

    def index_journal(self, journal_path: str = "data/journal.db") -> int:
        """Indexe les textes des trades."""
        j = SqliteTradeJournal(journal_path)
        trades = j.all()
        j.close()
        n = 0
        use_ollama = os.environ.get("QUANT_EMBED", "tfidf").lower() == "ollama"
        for t in trades:
            text = " ".join(filter(None, [t.entry_reason, t.exit_reason, t.strategy, t.regime, t.instrument]))
            if not text.strip():
                continue
            if use_ollama:
                vec = _ollama_embed(text)
                method = "ollama"
                blob = json.dumps(vec).encode() if vec else None
            else:
                # simple tfidf on the fly (or precompute idf outside)
                vec = _tfidf_vec(text, {})  # idf empty → pure tf for demo
                method = "tfidf"
                blob = json.dumps(vec).encode()
            if blob:
                self.conn.execute(
                    "INSERT OR REPLACE INTO embeddings (id, source, text, vector, method) VALUES (?,?,?,?,?)",
                    (t.id, "journal", text, blob, method),
                )
                n += 1
        self.conn.commit()
        return n

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Recherche cosine simple."""
        # For brevity: load all and score (ok for small journal)
        rows = self.conn.execute("SELECT id, text, vector, method FROM embeddings").fetchall()
        if not rows:
            return []
        # query vec (tfidf fallback)
        qv = _tfidf_vec(query, {})
        scored = []
        for rid, text, blob, method in rows:
            try:
                v = json.loads(blob)
                if isinstance(v, list):  # ollama
                    # skip or convert; for demo use text overlap
                    score = len(set(_tokens(query)) & set(_tokens(text))) / max(1, len(_tokens(query)))
                else:
                    score = sum(qv.get(t, 0) * w for t, w in v.items())
                scored.append((score, rid, text))
            except Exception:
                continue
        scored.sort(reverse=True)
        return [{"id": i, "text": t, "score": round(s, 4)} for s, i, t in scored[:k] if s > 0]

    def close(self):
        self.conn.close()
