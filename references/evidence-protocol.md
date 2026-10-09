# Evidence protocol

The contract every OMNISKILL task ends with. Machine-readable form: `schemas/evidence.schema.json`. Checker: `scripts/validate_evidence.py`.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `task` | yes | One-sentence goal |
| `mode` | yes | `QUICK`, `PRO`, `AUTONOMOUS` or `AUDIT` |
| `status` | yes | Global status, see below |
| `criteria[]` | yes (≥1) | `id`, `description`, `essential`, `status`, `evidence` |
| `actions[]` | no | Significant actions with their `state` |
| `limitations[]` | no | Known limits, residual risks |
| `blockers[]` | required if `BLOCKED` | What stops progress and what would unblock it |
| `findings[]` | AUDIT only | `id`, `severity`, `certainty`, `location`, `evidence` |

## Action states

| State | Meaning |
|---|---|
| `planned` | Intended, not attempted |
| `attempted` | Started; outcome unknown or failed |
| `executed` | Completed by a real tool call |
| `observed` | Its result was looked at (output read, file opened) |

Only `observed` actions can back a `PASS`.

## Criterion status

- `PASS` — checked and satisfied. `evidence` must say **how** (command + result, file + section, source + date).
- `FAIL` — checked and not satisfied.
- `NOT_VERIFIED` — not checked (no tool, no access, out of time). `evidence` says why.

## Global status rules (enforced by the validator)

| Status | Condition |
|---|---|
| `VERIFIED` | Every essential criterion is `PASS`, and no criterion is `FAIL` |
| `PARTIAL` | At least one criterion `PASS`, and at least one essential criterion is `FAIL` or `NOT_VERIFIED` |
| `BLOCKED` | `blockers[]` is non-empty |
| `UNVERIFIED` | Work produced but essential criteria lack evidence |

Additional checks:

- `PASS` with empty or placeholder evidence ("done", "ok", "works", "verified") is rejected.
- `PASS` whose evidence only cites the model's own statement ("I confirmed", "as stated above") is rejected.
- Text that looks like a secret (private keys, common token formats) is rejected anywhere in the report.
- Very long evidence strings are flagged: summarise and point to a file instead.

## Minimal example

```json
{
  "task": "Fix date parsing for ISO week dates",
  "mode": "QUICK",
  "status": "VERIFIED",
  "criteria": [
    {"id": "C1", "description": "parse('2026-W41-5') returns 2026-10-09", "essential": true,
     "status": "PASS", "evidence": "python -m pytest tests/test_dates.py::test_iso_week -> 1 passed"}
  ]
}
```
