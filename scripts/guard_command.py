#!/usr/bin/env python3
"""Classify a shell command before an agent runs it: allow, confirm or deny.

  deny     never run (catastrophic, disables a protection, or pipes remote code to a shell)
  confirm  destructive, irreversible or externally visible: needs explicit user approval
  allow    no known risky pattern found (NOT a guarantee the command is safe)

This is a pattern-based safety net, not a sandbox. Obfuscated commands can evade it.
It never executes the command it inspects.

Usage
  python3 scripts/guard_command.py "git push --force origin main"
  echo "rm -rf build" | python3 scripts/guard_command.py -
  python3 scripts/guard_command.py --json "curl -k https://x"

Exit codes: 0 allow, 3 confirm, 4 deny, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

EXIT = {"allow": 0, "confirm": 3, "deny": 4}

# (verdict, reason, pattern). Patterns run on the whole command and on each
# segment split at ; && || and newlines.
RULES: list[tuple[str, str, re.Pattern[str]]] = [
    # --- deny: catastrophic or protection-disabling
    ("deny", "recursive delete of a root, home or wildcard path",
     re.compile(r"\brm\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*\s+(?:-[a-zA-Z-]+\s+)*(?:--\s+)?(?:/|/\*|~/?|\$HOME/?|\*|\.\.?/?)(?:\s|$)")),
    ("deny", "rm with --no-preserve-root", re.compile(r"--no-preserve-root")),
    ("deny", "filesystem format", re.compile(r"\bmkfs(\.\w+)?\b")),
    ("deny", "raw write to a block device", re.compile(r"\bdd\b[^\n]*\bof=/dev/(sd|nvme|hd|xvd|vd|disk)")),
    ("deny", "redirect onto a block device", re.compile(r">\s*/dev/(sd|nvme|hd|xvd|vd|disk)")),
    ("deny", "fork bomb", re.compile(r":\(\)\s*\{\s*:\s*\|\s*:&\s*\}\s*;\s*:")),
    ("deny", "world-writable permissions on a system path",
     re.compile(r"\bchmod\s+(-R\s+)?0?777\s+/(\s|$|etc|usr|bin|var)")),
    ("deny", "remote content piped to an interpreter",
     re.compile(r"\b(curl|wget|fetch)\b[^|\n]*\|\s*(sudo\s+)?(ba|z|da|k)?sh\b|\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(python3?|node|perl|ruby)\b")),
    ("deny", "executing a downloaded script via process substitution",
     re.compile(r"\b(ba)?sh\s+<\(\s*(curl|wget)")),
    ("deny", "TLS verification disabled",
     re.compile(r"(\bcurl\b[^\n]*\s(-k|--insecure)\b|\bwget\b[^\n]*--no-check-certificate|"
                r"http\.sslVerify\s*(=|\s)\s*false|NODE_TLS_REJECT_UNAUTHORIZED=0|PYTHONHTTPSVERIFY=0|"
                r"GIT_SSL_NO_VERIFY=(1|true)|--trusted-host\b|strict-ssl\s+false)", re.IGNORECASE)),
    ("deny", "security control disabled",
     re.compile(r"\b(setenforce\s+0|ufw\s+disable|systemctl\s+(stop|disable)\s+(firewalld|apparmor|auditd)|"
                r"iptables\s+-F|Set-MpPreference\s+-DisableRealtimeMonitoring)", re.IGNORECASE)),
    ("deny", "git hooks or verification bypassed",
     re.compile(r"\bgit\s+(commit|push|merge|rebase)\b[^\n]*\s--no-verify\b")),

    # --- confirm: destructive / irreversible / external
    ("confirm", "file deletion", re.compile(r"(^|\s|;|&|\|)(sudo\s+)?(rm|rmdir|unlink|shred)\s")),
    ("confirm", "find with -delete or -exec rm", re.compile(r"\bfind\b[^\n]*(-delete\b|-exec\s+rm\b)")),
    ("confirm", "git history or working tree discarded",
     re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f|checkout\s+(--\s+)?\.(\s|$)|restore\s+(--\s+)?\.|"
                r"branch\s+-D|stash\s+(drop|clear)|filter-branch|filter-repo|rebase|reflog\s+expire|gc\s+--prune)")),
    ("confirm", "git push (externally visible)", re.compile(r"\bgit\s+push\b")),
    ("confirm", "publishing a package or release",
     re.compile(r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bgh\s+(release\s+create|pr\s+(create|merge))\b|\bdocker\s+push\b")),
    ("confirm", "infrastructure change",
     re.compile(r"\bterraform\s+(apply|destroy)\b|\bkubectl\s+(delete|apply|drain|scale)\b|\bhelm\s+(uninstall|delete|upgrade)\b|"
                r"\bdocker\s+(system|volume|image|container)\s+prune\b|\baws\s+\S+\s+(delete|terminate|rm)")),
    ("confirm", "destructive SQL",
     re.compile(r"\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\w+\s*(;|$))", re.IGNORECASE)),
    ("confirm", "privilege escalation", re.compile(r"(^|\s|;|&)(sudo|su|doas)\s")),
    ("confirm", "recursive ownership or permission change", re.compile(r"\b(chmod|chown|chgrp)\s+-R\b")),
    ("confirm", "system power state", re.compile(r"\b(shutdown|reboot|halt|poweroff)\b")),
    ("confirm", "process killing", re.compile(r"\b(kill\s+-9|killall|pkill)\b")),
    ("confirm", "file overwrite by truncation", re.compile(r"(^|[;&|]\s*)>\s*\S|\btruncate\s+-s\s*0\b")),
    ("confirm", "package installation from a URL or VCS",
     re.compile(r"\bpip3?\s+install\b[^\n]*(https?://|git\+)|\bnpm\s+(i|install)\b[^\n]*(https?://|github:)")),
    ("confirm", "outbound mutating HTTP request",
     re.compile(r"\bcurl\b[^\n]*(-X\s*(POST|PUT|PATCH|DELETE)\b|--data\b|-d\s|--upload-file|-T\s)", re.IGNORECASE)),
    ("confirm", "crontab replaced or removed", re.compile(r"\bcrontab\s+(-r\b|(?!-)\S+\s*$)")),
]

SPLIT_RE = re.compile(r"\s*(?:;|&&|\|\||\n)\s*")


def classify(command: str) -> dict:
    command = command.strip()
    if not command:
        return {"verdict": "allow", "reasons": [], "command": command}
    candidates = [command] + [s for s in SPLIT_RE.split(command) if s and s != command]
    hits: dict[str, list[str]] = {"deny": [], "confirm": []}
    for verdict, reason, pattern in RULES:
        if any(pattern.search(c) for c in candidates) and reason not in hits[verdict]:
            hits[verdict].append(reason)
    if hits["deny"]:
        verdict = "deny"
    elif hits["confirm"]:
        verdict = "confirm"
    else:
        verdict = "allow"
    return {"verdict": verdict, "reasons": hits["deny"] + hits["confirm"], "command": command}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", help="the shell command to classify, or - to read it from stdin")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    command = sys.stdin.read(100_000) if args.command == "-" else args.command
    result = classify(command)
    if args.json:
        print(json.dumps(result))
    else:
        print(result["verdict"].upper())
        for r in result["reasons"]:
            print(f"  - {r}")
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
