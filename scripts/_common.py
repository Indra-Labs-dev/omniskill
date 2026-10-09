"""Shared helpers for OMNISKILL scripts. Standard library only, no I/O side effects."""

from __future__ import annotations

import re
from typing import Any

# Common secret formats. Deliberately conservative: false negatives are possible
# (documented residual risk), false positives should be rare.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("password_assignment", re.compile(r"(?i)\b(?:password|passwd|secret|api_key|apikey|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]")),
]

# Values that are clearly illustrative and must not trigger the scanner.
_ALLOWLIST = re.compile(r"(?i)(example|placeholder|changeme|redacted|xxxx|<[^>]+>|\*\*\*)")


def find_secrets(text: str) -> list[str]:
    """Return the kinds of secrets found in text (never the values)."""
    kinds: list[str] = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            if _ALLOWLIST.search(match.group(0)):
                continue
            kinds.append(kind)
            break
    return kinds


class FrontmatterError(ValueError):
    pass


def _scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    if (raw[0] == raw[-1]) and raw[0] in "\"'" and len(raw) >= 2:
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the YAML frontmatter subset used by Agent Skills.

    Supports top-level ``key: value`` pairs and one level of nested mapping
    (indented ``key: value`` lines under ``key:``). Anything else is rejected
    with a clear error rather than guessed at.
    Returns (metadata, body).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("file must start with a '---' frontmatter line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise FrontmatterError("frontmatter is not closed by a '---' line") from exc

    data: dict[str, Any] = {}
    current_parent: str | None = None
    for lineno, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line.startswith((" ", "\t"))
        if ":" not in line:
            raise FrontmatterError(f"line {lineno}: expected 'key: value'")
        key, _, value = line.strip().partition(":")
        key = key.strip()
        if not key:
            raise FrontmatterError(f"line {lineno}: empty key")
        if indented:
            if current_parent is None or not isinstance(data.get(current_parent), dict):
                raise FrontmatterError(f"line {lineno}: indented key without a parent mapping")
            data[current_parent][key] = _scalar(value)
            continue
        if key in data:
            raise FrontmatterError(f"line {lineno}: duplicate key '{key}'")
        if value.strip() == "":
            data[key] = {}
            current_parent = key
        else:
            data[key] = _scalar(value)
            current_parent = None
    body = "\n".join(lines[end + 1:])
    return data, body


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token). Used for budgets, not billing."""
    return (len(text) + 3) // 4
