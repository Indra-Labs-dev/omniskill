# Mode AUDIT

For audits of code, architecture, security, configuration or deliverables.

## Sequence

1. **Scope** — what is audited, against which standard or expectation, and whether fixes are authorized. Default: report only, no fixes.
2. **Inspect the real thing** — read the actual files, configs and outputs. Run read-only checks (tests, linters, config validators) when available. Never audit from file names or assumptions.
3. **Find concrete defects** — each finding must point to a location and be reproducible.
4. **Classify** — severity × impact:
   - `CRITICAL` exploitable or data-losing now
   - `HIGH` serious defect, likely to bite
   - `MEDIUM` real defect, limited impact or hard to trigger
   - `LOW` hygiene, maintainability
   - `INFO` observation, no action needed
5. **Separate certainty** — `confirmed` (reproduced or directly observed), `likely` (strong evidence, not reproduced), `suspected` (needs checking). Call out possible false positives.
6. **Fix (only if authorized)** — targeted change per finding, then a non-regression check proving the fix and showing nothing else broke.
7. **Report** — findings sorted by severity, then the core status report.

## Finding format

```
[HIGH][confirmed] F3 — SQL built by string concatenation
Where: app/db.py:88 (search_users)
Evidence: input `' OR 1=1 --` returns all rows (test_search_injection)
Impact: read access to every user record
Fix: parameterized query; regression test added
```

## Rules

- No finding without a location and evidence. "Might be insecure" is not a finding.
- Do not inflate severity to look thorough, or deflate it to look reassuring.
- An audit that found nothing still reports what was covered and what was not.
- Machine-readable findings: `findings` array in `schemas/evidence.schema.json`.
