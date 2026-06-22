#!/usr/bin/env python3
"""Recherche SÉMANTIQUE locale du vault Obsidian — RAG gratuit, 100 % local, sans service payant.

Par défaut : TF-IDF (numpy + stdlib, hors-ligne, déterministe). Si tu installes Ollama, passe en
embeddings denses : `QUANT_EMBED=ollama python scripts/vault_search.py search "..."` (modèle
`nomic-embed-text`, repli automatique sur TF-IDF si Ollama injoignable).

  python scripts/vault_search.py search "réconciliation GAAP non-GAAP" -k 5
  python scripts/vault_search.py search "pourquoi DuckDB" --vault vault

Claude peut l'appeler en une commande pour retrouver la bonne note sans tout relire.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_WORD = re.compile(r"[a-zA-ZàâäéèêëîïôöùûüçœÀÂÄÉÈÊËÎÏÔÖÙÛÜÇŒ0-9_]{2,}")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def _chunks(vault: Path) -> list[dict]:
    """Découpe chaque note en sections (par titre `##`), pour un rappel fin."""
    out: list[dict] = []
    for f in sorted(vault.rglob("*.md")):
        rel = f.relative_to(vault).as_posix()
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001
            continue
        heading, buf = "(intro)", []

        def _flush():
            txt = "\n".join(buf).strip()
            if txt:
                out.append({"file": rel, "heading": heading, "text": txt})

        for ln in lines:
            if ln.startswith("## "):
                _flush(); heading = ln.lstrip("# ").strip(); buf = []
            else:
                buf.append(ln)
        _flush()
    return out


def _code_chunks(roots: list[Path]) -> list[dict]:
    """Découpe les .py par bloc top-level (def/class) → contexte ciblé pour Claude (#2, moins de tokens)."""
    out: list[dict] = []
    for root in roots:
        if not root.exists():
            continue
        for f in sorted(root.rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            rel = f.relative_to(ROOT).as_posix() if str(f).startswith(str(ROOT)) else f.name
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except Exception:  # noqa: BLE001
                continue
            heading, buf = f"{f.stem} (module)", []

            def _flush():
                txt = "\n".join(buf).strip()
                if txt:
                    out.append({"file": rel, "heading": heading, "text": txt})
            for ln in lines:
                if (ln.startswith("def ") or ln.startswith("class ")
                        or ln.startswith("    def ")):                 # bloc top-level / méthode
                    _flush(); heading = ln.strip().rstrip(":"); buf = [ln]
                else:
                    buf.append(ln)
            _flush()
    return out


def _tfidf_vectors(chunks: list[dict]) -> tuple[list[dict], dict]:
    docs = [_tokens(c["text"] + " " + c["heading"]) for c in chunks]
    n = len(docs) or 1
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    vecs: list[dict] = []
    for d in docs:
        tf: dict[str, float] = {}
        for t in d:
            tf[t] = tf.get(t, 0.0) + 1.0
        v = {t: w * idf.get(t, 0.0) for t, w in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: w / norm for t, w in v.items()})
    return vecs, idf


def _q_vector(query: str, idf: dict) -> dict:
    tf: dict[str, float] = {}
    for t in _tokens(query):
        tf[t] = tf.get(t, 0.0) + 1.0
    v = {t: w * idf.get(t, 0.0) for t, w in tf.items()}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: w / norm for t, w in v.items()}


def _cos(a: dict, b: dict) -> float:
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return sum(w * big.get(t, 0.0) for t, w in small.items())


def _ollama_embed(texts: list[str]) -> list[list[float]] | None:
    """Embeddings denses via Ollama si dispo (sinon None → repli TF-IDF). 100 % local."""
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.environ.get("QUANT_EMBED_MODEL", "nomic-embed-text")
    try:
        import json
        import urllib.request
        out = []
        for t in texts:
            req = urllib.request.Request(
                f"{host}/api/embeddings",
                data=json.dumps({"model": model, "prompt": t[:8000]}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — hôte local
                out.append(json.loads(r.read())["embedding"])
        return out
    except Exception:  # noqa: BLE001
        return None


def search(query: str, vault: Path, k: int = 5, code_roots: list[Path] | None = None) -> list[dict]:
    chunks = _chunks(vault) + (_code_chunks(code_roots) if code_roots else [])
    if not chunks:
        return []
    use_ollama = os.environ.get("QUANT_EMBED", "tfidf").lower() == "ollama"
    scores: list[float] = []
    if use_ollama:
        import numpy as np
        embs = _ollama_embed([c["text"] for c in chunks] + [query])
        if embs is not None:
            M = np.array(embs[:-1], dtype=float); q = np.array(embs[-1], dtype=float)
            M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9); q /= (np.linalg.norm(q) + 1e-9)
            scores = (M @ q).tolist()
    if not scores:  # repli TF-IDF (défaut, hors-ligne)
        vecs, idf = _tfidf_vectors(chunks)
        qv = _q_vector(query, idf)
        scores = [_cos(qv, v) for v in vecs]
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)[:k]
    return [{**c, "score": round(s, 4)} for c, s in ranked if s > 0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Recherche sémantique locale du vault.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="cherche dans le vault")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--vault", default=str(ROOT / "vault"))
    s.add_argument("--code", action="store_true", help="indexe aussi packages/ et scripts/ (.py)")
    a = ap.parse_args()
    code_roots = [ROOT / "packages", ROOT / "scripts"] if a.code else None
    hits = search(a.query, Path(a.vault), a.k, code_roots=code_roots)
    if not hits:
        print("(aucun résultat)"); return 0
    for h in hits:
        print(f"[{h['score']:.3f}] {h['file']} › {h['heading']}")
        snippet = " ".join(h["text"].split())[:240]
        print(f"    {snippet}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
