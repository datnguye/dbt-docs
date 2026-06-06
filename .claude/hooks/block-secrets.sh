#!/usr/bin/env bash
# PreToolUse hook — blocks Read/Edit/Write/Grep/Bash access to secret files.
#
# Reads the hook payload from stdin and exits with code 2 (deny) if any token
# in the candidate input matches a known secret-file pattern. Patterns covered:
# .env, .env.*, *.pem, *.key, credentials.json, secrets.json, *.p12, *.pfx,
# id_rsa, id_ed25519. .env.example is explicitly allowed as a template file.

set -euo pipefail

# Buffer stdin so we can hand it to python3 without a heredoc fighting for it.
HOOK_PAYLOAD="$(cat)"
export HOOK_PAYLOAD

python3 <<'PY'
import json, os, re, sys

try:
    data = json.loads(os.environ.get("HOOK_PAYLOAD", ""))
except Exception:
    sys.exit(0)

tool = data.get("tool_name", "")
ti = data.get("tool_input", {}) or {}
if tool in ("Read", "Edit", "Write"):
    candidate = ti.get("file_path", "")
elif tool == "Grep":
    candidate = ti.get("path", "")
elif tool == "Bash":
    candidate = ti.get("command", "")
else:
    sys.exit(0)

if not candidate:
    sys.exit(0)

# Split on shell-ish separators so "cat .env" and "Read /a/.env" both tokenize.
tokens = [t.strip("'\"") for t in re.split(r"[\s|;&<>()`]+", candidate) if t]

allow = [re.compile(r"(^|/)\.env\.example$")]
deny = [
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.[^/]+$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r"(^|/)secrets\.json$"),
    re.compile(r"(^|/)id_rsa$"),
    re.compile(r"(^|/)id_ed25519$"),
    re.compile(r"\.pem$"),
    re.compile(r"\.key$"),
    re.compile(r"\.p12$"),
    re.compile(r"\.pfx$"),
]

for tok in tokens:
    if any(p.search(tok) for p in allow):
        continue
    if any(p.search(tok) for p in deny):
        sys.stderr.write(
            f"Blocked: {tool} tool touches a secret file ({tok}). "
            "Access disabled by .claude/hooks/block-secrets.sh. "
            "If this is a false positive, rename the file or edit the hook.\n"
        )
        sys.exit(2)

sys.exit(0)
PY
