"""Test helpers: paths and a subprocess runner for the scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def run_script(name: str, *args: str, stdin: str | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], input=stdin, capture_output=True,
                          text=True, cwd=cwd or ROOT, timeout=60, check=False)


def fake_secret(kind: str) -> str:
    """Build secret-shaped strings at runtime so no secret-like literal exists in the repo."""
    if kind == "aws":
        return "AK" + "IA" + "Q3EGRKZJ7N5TWX2M"
    if kind == "github":
        return "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
    if kind == "private_key":
        return "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIEow\n"
    raise ValueError(kind)
