#!/usr/bin/env python3
"""Miroir Obsidian → Notion (gratuit, sans Docker/n8n). One-way : pousse des notes du vault vers
des pages Notion sous une page parente. stdlib pure (urllib) + NOTION_TOKEN.

  export NOTION_TOKEN=ntn_xxx ; export NOTION_PARENT=<page_id Notion>
  python scripts/notion_sync.py                       # notes par défaut (00_INDEX, 02..04)
  python scripts/notion_sync.py --files 03_TODO.md 04_JOURNAL.md

Prérequis : créer une intégration Notion (notion.so → My integrations), partager la page parente
avec l'intégration (⋯ → Connections), récupérer l'ID de la page parente (32 hex dans son URL).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
API = "https://api.notion.com/v1"
DEFAULT_FILES = ["00_INDEX.md", "02_DECISIONS.md", "03_TODO.md", "04_JOURNAL.md"]


def _rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[:1900]}}]   # Notion : 2000 car. max / rich_text


def md_to_blocks(md: str, limit: int = 95) -> list[dict]:
    """Convertit du Markdown en blocs Notion (titres, puces, code, paragraphes). Pur, testable."""
    blocks: list[dict] = []
    in_code, code_buf = False, []
    for raw in md.splitlines():
        ln = raw.rstrip()
        if ln.strip().startswith("```"):
            if in_code:
                blocks.append({"type": "code", "code": {"language": "plain text",
                              "rich_text": _rt("\n".join(code_buf))}})
                code_buf = []
            in_code = not in_code
            continue
        if in_code:
            code_buf.append(ln); continue
        if not ln.strip():
            continue
        if ln.startswith("### "):
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": _rt(ln[4:])}})
        elif ln.startswith("## "):
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": _rt(ln[3:])}})
        elif ln.startswith("# "):
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": _rt(ln[2:])}})
        elif ln.lstrip().startswith(("- ", "* ")):
            blocks.append({"type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": _rt(ln.lstrip()[2:])}})
        else:
            blocks.append({"type": "paragraph", "paragraph": {"rich_text": _rt(ln)}})
        if len(blocks) >= limit:
            break
    if in_code and code_buf:
        blocks.append({"type": "code", "code": {"language": "plain text", "rich_text": _rt("\n".join(code_buf))}})
    return blocks


def _api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — API Notion officielle
        return json.loads(r.read().decode())


def _archive_existing(parent: str, title: str, token: str) -> None:
    """Archive les pages enfant homonymes (évite les doublons à chaque run). Best-effort."""
    try:
        children = _api("GET", f"/blocks/{parent}/children?page_size=100", token).get("results", [])
        for b in children:
            if b.get("type") == "child_page" and b.get("child_page", {}).get("title") == title:
                _api("PATCH", f"/pages/{b['id']}", token, {"archived": True})
    except Exception:  # noqa: BLE001
        pass


def sync(files: list[str], token: str, parent: str) -> int:
    ok = 0
    for fname in files:
        p = VAULT / fname
        if not p.exists():
            print(f"· {fname} : absent — ignoré"); continue
        title = p.stem
        blocks = md_to_blocks(p.read_text(encoding="utf-8"))
        _archive_existing(parent, title, token)
        try:
            _api("POST", "/pages", token, {
                "parent": {"page_id": parent},
                "properties": {"title": {"title": [{"text": {"content": title}}]}},
                "children": blocks})
            print(f"✓ {fname} → Notion ({len(blocks)} blocs)")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"⛔ {fname} : {e}\n   → vérifie NOTION_TOKEN + page parente partagée avec l'intégration.")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    ap.add_argument("--parent", default=os.environ.get("NOTION_PARENT"))
    a = ap.parse_args()
    token = os.environ.get("NOTION_TOKEN")
    if not token or not a.parent:
        print("⛔ NOTION_TOKEN et NOTION_PARENT requis (.env)."); return 1
    return sync(a.files, token, a.parent)


if __name__ == "__main__":
    sys.exit(main())
