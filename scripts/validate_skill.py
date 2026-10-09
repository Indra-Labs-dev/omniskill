#!/usr/bin/env python3
"""Validate the structure and metadata of an OMNISKILL (Agent Skills format) skill.

Checks
  * SKILL.md exists and has valid frontmatter (name, description, optional fields)
  * name follows Agent Skills rules; description length within limits
  * the core stays under a token budget (prevents silent core bloat)
  * the four mode files exist and are referenced from the core
  * every relative file path cited in backticks in the docs exists

Usage
  python3 scripts/validate_skill.py [SKILL_DIR] [--max-core-tokens N] [--json]

Exit codes: 0 valid, 1 validation errors, 2 usage or I/O error.
Read-only: never modifies files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FrontmatterError, estimate_tokens, parse_frontmatter  # noqa: E402

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KNOWN_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
REQUIRED_MODES = ("quick", "pro", "autonomous", "audit")
DEFAULT_MAX_CORE_TOKENS = 1800  # OMNISKILL's own budget; the spec recommends < 5000
MAX_BODY_LINES = 500
# Paths cited like `modes/pro.md` or `scripts/x.py`; placeholders with <> are skipped.
PATH_RE = re.compile(r"`((?:modes|references|schemas|scripts|adapters|benchmarks|examples)/[A-Za-z0-9_./-]+)`")
DOC_GLOBS = ("SKILL.md", "modes/*.md", "references/*.md", "adapters/*.md")


def validate(skill_dir: Path, max_core_tokens: int = DEFAULT_MAX_CORE_TOKENS,
             allow_dir_mismatch: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    info: dict = {}

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {"valid": False, "errors": [f"{skill_md} not found"], "warnings": [], "info": {}}

    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"valid": False, "errors": ["SKILL.md is not valid UTF-8"], "warnings": [], "info": {}}

    try:
        meta, body = parse_frontmatter(text)
    except FrontmatterError as exc:
        return {"valid": False, "errors": [f"frontmatter: {exc}"], "warnings": [], "info": {}}

    # --- name
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        errors.append("frontmatter: 'name' is required")
    else:
        if len(name) > 64:
            errors.append("name: longer than 64 characters")
        if not NAME_RE.match(name):
            errors.append("name: use lowercase letters, digits and single hyphens only")
        if skill_dir.resolve().name != name:
            msg = (f"name '{name}' must match the skill directory name '{skill_dir.resolve().name}' "
                   "(Agent Skills spec)")
            (warnings if allow_dir_mismatch else errors).append(msg)

    # --- description
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append("frontmatter: 'description' is required")
    elif len(desc) > 1024:
        errors.append(f"description: {len(desc)} characters, maximum is 1024")
    elif len(desc) < 40:
        warnings.append("description: very short; loaders use it to decide when to apply the skill")

    compat = meta.get("compatibility")
    if isinstance(compat, str) and len(compat) > 500:
        errors.append("compatibility: maximum is 500 characters")
    if "metadata" in meta:
        if not isinstance(meta["metadata"], dict):
            errors.append("metadata: must be a mapping")
        elif any(not isinstance(v, str) for v in meta["metadata"].values()):
            errors.append("metadata: values must be strings (quote numbers and booleans)")
    for key in meta:
        if key not in KNOWN_KEYS:
            warnings.append(f"frontmatter: unknown key '{key}' (may be ignored by loaders)")

    # --- core budget
    core_tokens = estimate_tokens(body)
    info["core_tokens_estimate"] = core_tokens
    info["core_lines"] = len(body.splitlines())
    if info["core_lines"] > MAX_BODY_LINES:
        errors.append(f"core: {info['core_lines']} lines; the spec recommends under {MAX_BODY_LINES}")
    if core_tokens > max_core_tokens:
        errors.append(f"core: ~{core_tokens} tokens exceeds budget of {max_core_tokens}; "
                      "move detail to modes/ or references/")

    # --- modes
    for mode in REQUIRED_MODES:
        rel = f"modes/{mode}.md"
        if not (skill_dir / rel).is_file():
            errors.append(f"missing mode file {rel}")
        elif mode != "quick" and rel not in body:
            errors.append(f"core does not reference {rel}")

    # --- cited paths
    checked = 0
    for pattern in DOC_GLOBS:
        for doc in sorted(skill_dir.glob(pattern)):
            content = doc.read_text(encoding="utf-8", errors="replace")
            for match in PATH_RE.finditer(content):
                rel = match.group(1).rstrip(".,")
                checked += 1
                if any(ch in rel for ch in "*<>"):
                    continue
                if not (skill_dir / rel).exists():
                    errors.append(f"{doc.relative_to(skill_dir)}: cited path '{rel}' does not exist")
    info["paths_checked"] = checked

    return {"valid": not errors, "errors": errors, "warnings": warnings, "info": info}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("skill_dir", nargs="?", default=".", help="directory containing SKILL.md")
    parser.add_argument("--max-core-tokens", type=int, default=DEFAULT_MAX_CORE_TOKENS)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--allow-dir-mismatch", action="store_true",
                        help="downgrade the name/directory mismatch to a warning (e.g. a clone named omniskill-main)")
    args = parser.parse_args(argv)

    skill_dir = Path(args.skill_dir)
    if not skill_dir.is_dir():
        print(f"error: {skill_dir} is not a directory", file=sys.stderr)
        return 2

    result = validate(skill_dir, args.max_core_tokens, args.allow_dir_mismatch)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for w in result["warnings"]:
            print(f"WARN  {w}")
        for e in result["errors"]:
            print(f"ERROR {e}")
        state = "VALID" if result["valid"] else "INVALID"
        print(f"{state}: {skill_dir / 'SKILL.md'} {result['info']}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
