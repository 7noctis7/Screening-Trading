---
name: session-open
description: Opening ritual - read the vault memory (index, architecture diagrams, journal, TODO) and produce the 3-line state synthesis plus session plan. Run at the start of every session.
---

1. Read in order: `vault/00_INDEX.md` → `vault/01_ARCHITECTURE.md` (BOTH Mermaid
   diagrams — components AND end-to-end flow) → last 3 dated entries of
   `vault/04_JOURNAL.md` → `vault/03_TODO.md`.
2. Output exactly:
   - **État (3 lines)**: where the project is, what changed last session, next priority.
   - **Plan**: the P0 tasks for this session, each located on the architecture
     diagram ("this touches `packages/regime` → feeds `ranking`").
   - **Risks**: anything from the journal that could bite today (broken test,
     pending migration, API quota).
3. Wait for user confirmation of the plan before writing code. Work in small
   tested increments; commit atomically.
