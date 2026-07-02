---
name: session-close
description: Closing ritual - update JOURNAL, TODO, DECISIONS, refresh Mermaid diagrams if architecture changed, sync Notion. Run before ending any session.
---

1. Summarize what was done this session (files touched, tests added, decisions).
2. Update the vault:
   - `vault/04_JOURNAL.md`: append dated entry (done / blocked / next).
   - `vault/03_TODO.md`: close finished items, add discovered ones with P0/P1/P2.
   - `vault/02_DECISIONS.md`: one ADR per non-trivial choice made today
     (context → decision → consequences).
3. **Diagram check**: if a module, dependency, or pipeline step was added or
   changed, update BOTH Mermaid diagrams in `vault/01_ARCHITECTURE.md` now.
   Optionally spawn `vault-architect` to verify zero drift.
4. Run `pytest -q && ruff check .` — the session does not close on red.
5. Run `python scripts/sync_notion.py` if it exists (todos + architecture mirror).
6. End with: "Reprenable par une autre instance: OUI/NON" and why.
