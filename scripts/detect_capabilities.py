#!/usr/bin/env python3
"""Snapshot the local capabilities an agent can rely on (schemas/capabilities.schema.json).

Looks up runtimes and tools on PATH, asks found executables for their version
(5 s timeout each), and lists test/build configuration in the project directory.
Read-only and offline: no network access, no file written, no install.

It cannot see the tools an AI platform grants the model (web search, memory,
sub-agents); those are listed under "not_detectable" for the agent to fill in.

Usage
  python3 scripts/detect_capabilities.py [PROJECT_DIR] [--json] [--only python3,node]

Exit code: 0 on success, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RUNTIMES = {
    "python3": ["--version"], "node": ["--version"], "npm": ["--version"], "bash": ["--version"],
    "go": ["version"], "java": ["-version"], "rustc": ["--version"], "deno": ["--version"],
}
TOOLS = {
    "git": ["--version"], "pytest": ["--version"], "ruff": ["--version"], "shellcheck": ["--version"],
    "eslint": ["--version"], "tsc": ["--version"], "make": ["--version"], "docker": ["--version"],
    "pandoc": ["--version"], "libreoffice": ["--version"], "jq": ["--version"],
}
PROJECT_MARKERS = {
    "git_repository": [".git"],
    "python_project": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
    "node_project": ["package.json"],
    "python_tests": ["pytest.ini", "tox.ini", "tests", "conftest.py"],
    "makefile": ["Makefile"],
    "ci": [".github/workflows", ".gitlab-ci.yml"],
    "agent_instructions": ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md", "SKILL.md"],
}
NOT_DETECTABLE = ["web_search", "web_fetch", "persistent_memory", "sub_agents",
                  "document_tools", "approval_requirements"]


def version_of(exe: str, args: list[str]) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        proc = subprocess.run([path, *args], capture_output=True, text=True, timeout=5,
                              stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "present (version unknown)"
    out = (proc.stdout or proc.stderr or "").strip().splitlines()
    return out[0][:120] if out else "present (version unknown)"


def snapshot(project_dir: Path, only: set[str] | None = None) -> dict:
    def pick(table: dict) -> dict:
        return {k: version_of(k, v) for k, v in table.items() if only is None or k in only}

    project = {}
    for key, markers in PROJECT_MARKERS.items():
        found = [m for m in markers if (project_dir / m).exists()]
        project[key] = found
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "python": platform.python_version()},
        "runtimes": pick(RUNTIMES),
        "tools": pick(TOOLS),
        "project": {"path": str(project_dir.resolve()), **project},
        "not_detectable": NOT_DETECTABLE,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project_dir", nargs="?", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--only", help="comma-separated executables to probe (default: all known)")
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir)
    if not project_dir.is_dir():
        print(f"error: {project_dir} is not a directory", file=sys.stderr)
        return 2
    only = set(args.only.split(",")) if args.only else None
    snap = snapshot(project_dir, only)

    if args.json:
        print(json.dumps(snap, indent=2))
        return 0
    print(f"Platform: {snap['platform']['system']} {snap['platform']['machine']}")
    for section in ("runtimes", "tools"):
        present = {k: v for k, v in snap[section].items() if v}
        absent = sorted(k for k, v in snap[section].items() if not v)
        print(f"{section.capitalize()}:")
        for k, v in present.items():
            print(f"  + {k}: {v}")
        if absent:
            print(f"  - absent: {', '.join(absent)}")
    print("Project:")
    for k, v in snap["project"].items():
        if k != "path":
            print(f"  {'+' if v else '-'} {k}{': ' + ', '.join(v) if v else ''}")
    print(f"Not detectable from here (check your tool list): {', '.join(NOT_DETECTABLE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
