#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit): enforces project rules on the edited file.

Exit 2 => stderr is fed back to Claude so it self-corrects immediately.
Checks: file length (<400 lines), function length (<50 lines, heuristic),
and dangerous quant patterns (look-ahead, live-trading, hardcoded keys).
"""
import json
import re
import sys
from pathlib import Path

MAX_FILE_LINES = 400
MAX_FUNC_LINES = 50

RISK_PATTERNS = [
    (r"\.shift\(\s*-\d", "possible look-ahead: negative shift() uses future data"),
    (r"\bpaper\s*=\s*False|\blive\s*=\s*True|APCA-API.*live", "LIVE TRADING flag detected — paper only without explicit GO LIVE"),
    (r"(api[_-]?key|secret)\s*=\s*['\"][A-Za-z0-9]{16,}", "hardcoded credential — move to .env"),
    (r"fillna\(method=['\"]bfill|\.bfill\(", "bfill leaks future values into the past"),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path", "")
    if not fp or not fp.endswith((".py", ".ts", ".tsx")):
        return 0
    path = Path(fp)
    if not path.exists():
        return 0
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    problems = []

    if len(lines) > MAX_FILE_LINES:
        problems.append(f"{path.name}: {len(lines)} lines > {MAX_FILE_LINES}. Split by responsibility NOW (architecture rule #2).")

    if fp.endswith(".py"):
        starts = [i for i, l in enumerate(lines) if re.match(r"\s*(async\s+)?def\s+\w+", l)]
        for i, s in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(lines)
            if end - s > MAX_FUNC_LINES:
                name = re.search(r"def\s+(\w+)", lines[s]).group(1)
                problems.append(f"{path.name}:{s + 1} function `{name}` ~{end - s} lines > {MAX_FUNC_LINES}. Extract helpers.")

    for pat, msg in RISK_PATTERNS:
        for i, l in enumerate(lines):
            if re.search(pat, l):
                problems.append(f"{path.name}:{i + 1} {msg}")
                break

    if problems:
        print("PROJECT RULE VIOLATIONS:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
