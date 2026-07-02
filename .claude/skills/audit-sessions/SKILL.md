---
name: audit-sessions
description: Audit recent Claude Code sessions for this project with sub-agents, cluster friction, and propose skills/hooks/CLAUDE.md fixes. Writes report to vault/13_CC_OPS.md.
disable-model-invocation: true
---

Audit pipeline — run these steps exactly:

1. Locate transcripts: `ls -t ~/.claude/projects/` and identify the directory
   matching this project's path (slug = cwd with `/` replaced by `-`). Take the
   **10 most recent** `*.jsonl` files (or the number given as `$ARGUMENTS`).
2. Spawn **session-auditor** sub-agents in parallel — one per batch of ~3
   session files — passing explicit file paths. Collect their YAML summaries.
   Also pass `.claude/ops/friction.jsonl` to one of them if it exists.
3. Spawn **friction-clusterer** with ALL YAML summaries concatenated. Receive
   the clustered report with ranked fixes.
4. Review the proposed fixes yourself against the current `CLAUDE.md` and
   existing `.claude/skills/` — drop anything already covered, dedupe.
5. Write the final report to `vault/13_CC_OPS.md` (create if absent, prepend
   dated section if it exists). Include: friction cluster table, ranked fixes,
   and the ready-to-paste artifacts (SKILL.md drafts, hook fragments,
   CLAUDE.md diff).
6. Present to the user: the top 3 fixes with one-line justification each, and
   ask which to apply. Apply only the approved ones.

Never fabricate friction: if transcripts are missing or unreadable, say so and
report only what was actually parsed.
