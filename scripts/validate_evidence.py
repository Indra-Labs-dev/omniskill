#!/usr/bin/env python3
"""Validate OMNISKILL evidence reports (schemas/evidence.schema.json + status rules).

Beyond the structure, it enforces the honesty rules of the evidence protocol:
  * VERIFIED requires every essential criterion PASS and no FAIL
  * PASS needs concrete evidence (no "done"/"ok", no self-citation)
  * BLOCKED requires at least one blocker; PARTIAL requires some PASS
  * AUDIT reports need well-formed findings
  * no secrets anywhere in the report

Usage
  python3 scripts/validate_evidence.py REPORT.json [REPORT.json ...] [--json]
  python3 scripts/validate_evidence.py -            # read one report from stdin

Exit codes: 0 all valid, 1 at least one invalid report, 2 usage or I/O error.
Read-only. File contents are treated as data, never executed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import find_secrets  # noqa: E402

MODES = {"QUICK", "PRO", "AUTONOMOUS", "AUDIT"}
STATUSES = {"VERIFIED", "PARTIAL", "BLOCKED", "UNVERIFIED"}
CRITERION_STATUSES = {"PASS", "FAIL", "NOT_VERIFIED"}
ACTION_STATES = {"planned", "attempted", "executed", "observed"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
CERTAINTIES = {"confirmed", "likely", "suspected"}
TOP_KEYS = {"task", "mode", "status", "criteria", "actions", "limitations", "blockers", "findings"}
CRITERION_KEYS = {"id", "description", "essential", "status", "evidence"}
MAX_EVIDENCE_CHARS = 2000
MAX_FILE_BYTES = 1_000_000

PLACEHOLDER_EVIDENCE = re.compile(
    r"^\s*(done|ok|okay|works?|working|verified|passed|pass|success(ful)?|yes|true|fine|n/?a|-|tbd|todo)\s*[.!]*\s*$",
    re.IGNORECASE,
)
SELF_CITATION = re.compile(
    r"(?i)^\s*(i\s+(have\s+)?(confirmed|verified|checked|believe|think|am\s+confident)|"
    r"as\s+(stated|mentioned|said)\s+(above|before|earlier)|trust\s+me|should\s+work|"
    r"it\s+(should|must)\s+(work|be\s+fine))"
)


def _type_error(path: str, expected: str) -> str:
    return f"{path}: expected {expected}"


def validate_report(report: object) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one parsed report."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(report, dict):
        return [_type_error("report", "a JSON object")], warnings

    for key in sorted(set(report) - TOP_KEYS):
        errors.append(f"unknown field '{key}'")
    for key in ("task", "mode", "status", "criteria"):
        if key not in report:
            errors.append(f"missing required field '{key}'")
    if errors and any(e.startswith("missing") for e in errors):
        return errors, warnings

    if not isinstance(report["task"], str) or len(report["task"].strip()) < 3:
        errors.append(_type_error("task", "a non-empty string"))
    if report["mode"] not in MODES:
        errors.append(f"mode: '{report['mode']}' not in {sorted(MODES)}")
    status = report["status"]
    if status not in STATUSES:
        errors.append(f"status: '{status}' not in {sorted(STATUSES)}")

    criteria = report["criteria"]
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria: expected a non-empty list")
        criteria = []

    seen_ids: set[str] = set()
    valid_criteria: list[dict] = []
    for i, c in enumerate(criteria):
        where = f"criteria[{i}]"
        if not isinstance(c, dict):
            errors.append(_type_error(where, "an object"))
            continue
        missing = CRITERION_KEYS - set(c)
        if missing:
            errors.append(f"{where}: missing {sorted(missing)}")
            continue
        for key in sorted(set(c) - CRITERION_KEYS):
            errors.append(f"{where}: unknown field '{key}'")
        cid = c["id"]
        if not isinstance(cid, str) or not cid:
            errors.append(_type_error(f"{where}.id", "a non-empty string"))
        elif cid in seen_ids:
            errors.append(f"{where}: duplicate id '{cid}'")
        else:
            seen_ids.add(cid)
        if not isinstance(c["essential"], bool):
            errors.append(_type_error(f"{where}.essential", "true or false"))
        if c["status"] not in CRITERION_STATUSES:
            errors.append(f"{where}.status: '{c['status']}' not in {sorted(CRITERION_STATUSES)}")
            continue
        ev = c["evidence"]
        if not isinstance(ev, str):
            errors.append(_type_error(f"{where}.evidence", "a string"))
            continue
        if c["status"] == "PASS":
            if not ev.strip() or PLACEHOLDER_EVIDENCE.match(ev):
                errors.append(f"{where} ({cid}): PASS without concrete evidence ('{ev.strip()}')")
            elif SELF_CITATION.match(ev):
                errors.append(f"{where} ({cid}): PASS backed only by the model's own statement")
        elif c["status"] == "NOT_VERIFIED" and not ev.strip():
            warnings.append(f"{where} ({cid}): NOT_VERIFIED should say why")
        if len(ev) > MAX_EVIDENCE_CHARS:
            warnings.append(f"{where} ({cid}): evidence is {len(ev)} chars; summarise and point to a file")
        valid_criteria.append(c)

    # --- optional arrays
    for key in ("limitations", "blockers"):
        if key in report and (not isinstance(report[key], list)
                              or not all(isinstance(x, str) for x in report[key])):
            errors.append(_type_error(key, "a list of strings"))
    for i, a in enumerate(report.get("actions", []) if isinstance(report.get("actions", []), list) else []):
        if not isinstance(a, dict) or "description" not in a or a.get("state") not in ACTION_STATES:
            errors.append(f"actions[{i}]: needs 'description' and 'state' in {sorted(ACTION_STATES)}")
    if "actions" in report and not isinstance(report["actions"], list):
        errors.append(_type_error("actions", "a list"))

    findings = report.get("findings", [])
    if not isinstance(findings, list):
        errors.append(_type_error("findings", "a list"))
        findings = []
    for i, f in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(f, dict):
            errors.append(_type_error(where, "an object"))
            continue
        for key in ("id", "severity", "certainty", "location", "evidence"):
            if not f.get(key):
                errors.append(f"{where}: missing '{key}'")
        if f.get("severity") and f["severity"] not in SEVERITIES:
            errors.append(f"{where}.severity: '{f['severity']}' not in {sorted(SEVERITIES)}")
        if f.get("certainty") and f["certainty"] not in CERTAINTIES:
            errors.append(f"{where}.certainty: '{f['certainty']}' not in {sorted(CERTAINTIES)}")
    if findings and report.get("mode") != "AUDIT":
        warnings.append("findings present but mode is not AUDIT")

    # --- status consistency (the honesty rules)
    essential = [c for c in valid_criteria if c.get("essential") is True]
    if not essential and valid_criteria:
        warnings.append("no criterion marked essential; VERIFIED would be meaningless")
    blockers = report.get("blockers") or []
    statuses = [c["status"] for c in valid_criteria]

    if status == "VERIFIED":
        if not essential:
            errors.append("status VERIFIED requires at least one essential criterion")
        bad = [c["id"] for c in essential if c["status"] != "PASS"]
        if bad:
            errors.append(f"status VERIFIED but essential criteria not PASS: {bad}")
        if "FAIL" in statuses:
            errors.append("status VERIFIED but some criterion is FAIL")
        if blockers:
            errors.append("status VERIFIED but blockers are listed")
    elif status == "BLOCKED":
        if not blockers:
            errors.append("status BLOCKED requires at least one entry in 'blockers'")
    elif status == "PARTIAL":
        if "PASS" not in statuses:
            errors.append("status PARTIAL requires at least one PASS criterion (otherwise UNVERIFIED or BLOCKED)")
        if essential and all(c["status"] == "PASS" for c in essential) and "FAIL" not in statuses:
            warnings.append("status PARTIAL but every essential criterion is PASS; VERIFIED may be accurate")
    elif status == "UNVERIFIED":
        if essential and all(c["status"] == "PASS" for c in essential) and "FAIL" not in statuses:
            warnings.append("status UNVERIFIED but every essential criterion is PASS")

    # --- secrets anywhere
    kinds = find_secrets(json.dumps(report, ensure_ascii=False))
    if kinds:
        errors.append(f"report contains what looks like secrets: {sorted(set(kinds))}")

    return errors, warnings


def load(path: str) -> tuple[object | None, str | None]:
    try:
        if path == "-":
            raw = sys.stdin.read(MAX_FILE_BYTES + 1)
        else:
            p = Path(path)
            if not p.is_file():
                return None, "IO: not a regular file"
            if p.stat().st_size > MAX_FILE_BYTES:
                return None, f"larger than {MAX_FILE_BYTES} bytes"
            raw = p.read_text(encoding="utf-8")
        if len(raw) > MAX_FILE_BYTES:
            return None, f"larger than {MAX_FILE_BYTES} bytes"
        return json.loads(raw), None
    except UnicodeDecodeError:
        return None, "not UTF-8 text"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
    except OSError as exc:
        return None, f"IO: cannot read: {exc.strerror}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("reports", nargs="+", help="report files, or - for stdin")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    results = []
    io_error = False
    for path in args.reports:
        data, load_error = load(path)
        if load_error:
            if load_error.startswith("IO:"):
                io_error = True
            results.append({"file": path, "valid": False, "errors": [load_error], "warnings": []})
            continue
        errors, warnings = validate_report(data)
        results.append({"file": path, "valid": not errors, "errors": errors, "warnings": warnings,
                        "status": data.get("status") if isinstance(data, dict) else None})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'VALID  ' if r['valid'] else 'INVALID'} {r['file']}")
            for e in r["errors"]:
                print(f"  ERROR {e}")
            for w in r["warnings"]:
                print(f"  WARN  {w}")

    if io_error:
        return 2
    return 1 if any(not r["valid"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
