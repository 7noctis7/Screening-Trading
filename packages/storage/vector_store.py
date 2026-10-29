"""Stockage vectoriel amélioré pour journal + vault.

TF-IDF avec IDF global ou Ollama. Cosine propre. Compatible ontologie.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path

from packages.storage.journal_sqlite import SqliteTradeJournal

_DEFAULT_VEC_DB = "data/vectors.db"


def _tokens(text: str) -> list[str]:
    import re
    return [w.lower() for w in re.findall(r"[a-zA-ZàâäéèêëîïôöùûüçœÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒ0-9_]{2,}", text)]


def _compute_idf(texts: list[str]) -> dict:
    n = len(texts) or 1
    df: dict[str, int] = {}
    for t in texts:
        for tok in set(_tokens(t)):
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log((n + 1) / (c + 1)) + 1.0 for tok, c in df.items()}


def _tfidf_vec(text: str, idf: dict) -> dict:
    tf: dict[str, float] = {}
    for t in _tokens(text):
        tf[t] = tf.get(t, 0.0) + 1.0
    v = {t: w * idf.get(t, 0.0) for t, w in tf.items()}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: w / norm for t, w in v.items()}


def _cosine_dict(a: dict, b: dict) -> float:
    return sum(w * b.get(t, 0.0) for t, w in a.items())


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


def _cosine_list(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class VectorStore:
    def __init__(self, db_path: str | Path = _DEFAULT_VEC_DB):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                source TEXT,
                text TEXT,
                vector BLOB,
                method TEXT
            )"""
        )
        self.conn.commit()

    def index_journal(self, journal_path: str = "data/journal.db") -> int:
        j = SqliteTradeJournal(journal_path)
        trades = j.all()
        j.close()
        texts = []
        items = []
        for t in trades:
            text = " ".join(filter(None, [t.entry_reason, t.exit_reason, t.strategy, t.regime, t.instrument]))
            if text.strip():
                texts.append(text)
                items.append((t.id, text))
        idf = _compute_idf(texts)
        use_ollama = os.environ.get("QUANT_EMBED", "tfidf").lower() == "ollama"
        n = 0
        for tid, text in items:
            if use_ollama:
                vec = _ollama_embed(text)
                method = "ollama"
                blob = json.dumps(vec).encode() if vec else None
            else:
                vec = _tfidf_vec(text, idf)
                method = "tfidf"
                blob = json.dumps(vec).encode()
            if blob:
                self.conn.execute(
                    "INSERT OR REPLACE INTO embeddings (id, source, text, vector, method) VALUES (?,?,?,?,?)",
                    (tid, "journal", text, blob, method),
                )
                n += 1
        self.conn.commit()
        return n

    def search(self, query: str, k: int = 5) -> list[dict]:
        rows = self.conn.execute("SELECT id, text, vector, method FROM embeddings").fetchall()
        if not rows:
            return []
        use_ollama = os.environ.get("QUANT_EMBED", "tfidf").lower() == "ollama"
        q_vec_list = _ollama_embed(query) if use_ollama else None
        scored = []
        for rid, text, blob, method in rows:
            try:
                v = json.loads(blob)
                if method == "ollama" and isinstance(v, list) and q_vec_list:
                    score = _cosine_list(q_vec_list, v)
                else:
                    idf = {}
                    qv = _tfidf_vec(query, idf)
                    score = _cosine_dict(qv, v if isinstance(v, dict) else {})
                scored.append((score, rid, text))
            except Exception:
                continue
        scored.sort(reverse=True)
        return [{"id": i, "text": t, "score": round(s, 4)} for s, i, t in scored[:k] if s > 0]

    def close(self):
        self.conn.close()
