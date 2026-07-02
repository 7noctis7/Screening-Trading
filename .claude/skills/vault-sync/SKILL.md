---
name: vault-sync
description: Verify vault-code coherence and push pilotage state to Notion (todos, architecture mirror, latest results).
disable-model-invocation: true
---

1. Spawn **vault-architect** → get drift report. Apply its diagram patches to
   `vault/01_ARCHITECTURE.md` if any (code wins over diagram).
2. Run `python scripts/sync_notion.py` (todos → Notion DB, architecture Mermaid
   → Notion page, latest tear sheet link). If the script is missing, offer to
   create it using the Notion MCP/API with the token from `.env`.
3. Report: drift score, items synced, anything requiring a human decision.
