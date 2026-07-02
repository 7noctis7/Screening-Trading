#!/usr/bin/env python3
"""PostToolUseFailure / Stop hook: appends structured friction events to
.claude/ops/friction.jsonl — consumed by the /audit-sessions skill and the
Ops dashboard. Never blocks (always exits 0)."""
import json
import sys
import time
from pathlib import Path

OUT = Path(".claude/ops/friction.jsonl")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "stop" if "--event" in sys.argv else "tool_failure",
        "session_id": payload.get("session_id", ""),
        "tool": payload.get("tool_name", ""),
        "input": str((payload.get("tool_input") or {}))[:500],
        "error": str(payload.get("error") or payload.get("tool_response") or "")[:800],
    }
    with OUT.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
