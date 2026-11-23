#!/usr/bin/env python3
"""PreToolUse hook: stop Claude Code from reading or writing .env files (API keys).

Blocks any tool call whose path or shell command mentions .env, .env.local, .env.prod, ...
.env.example (placeholders only, committed to git) stays allowed.
"""

import json
import re
import sys

ALLOWED = {".env.example"}
ENV_TOKEN = re.compile(r"(?<![\w])\.env[\w.-]*")   # .env, .env.local; not .venv, not dotenv


def env_mentions(text: str) -> list[str]:
    return [t for t in ENV_TOKEN.findall(text or "") if t.rstrip(".") not in ALLOWED]


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "Bash":
        texts = [tool_input.get("command", "")]
    else:  # Read, Edit, Write, NotebookEdit, Grep
        texts = [str(tool_input.get(k, "")) for k in ("file_path", "notebook_path", "path", "glob", "pattern")]

    hits = sorted({h for t in texts for h in env_mentions(t)})
    if hits:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Blocked: {', '.join(hits)} holds API keys and is off-limits to Claude Code. "
                "Use .env.example (placeholders) instead; the user edits .env by hand."),
        }}))


if __name__ == "__main__":
    main()
