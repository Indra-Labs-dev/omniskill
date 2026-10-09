# Mode PRO

For complex tasks with several steps, dependencies and a deliverable to test.

## Sequence

1. **Context** — inspect the relevant files, conventions, tests and constraints. Note what already exists and must be kept.
2. **Acceptance criteria** — write them before large changes. Number them (`C1`, `C2`, …), mark the essential ones, and say how each will be checked.
3. **Plan** — 3 to 8 ordered steps. Note dependencies ("C3 needs the schema from step 2").
4. **Execute** — one step at a time. After each step that changes behaviour, run the narrowest check that covers it.
5. **Validate** — run the full relevant check (test suite, build, linter, document render) once the steps are done.
6. **Report** — the structured report from the core, one line of evidence per criterion.

## Rules

- Prefer the project's existing tools and conventions over new ones.
- A failing check is information: fix, re-run, or report it as `FAIL`. Never hide or skip it silently.
- If a criterion turns out impossible, say so early and propose the closest achievable alternative.
- Optional: record the report as JSON following `schemas/evidence.schema.json` and check it with `scripts/validate_evidence.py`.

## Example criteria

```
C1 (essential) POST /users rejects an invalid email with 422 — check: unit test
C2 (essential) existing tests still pass — check: full test suite
C3 README documents the new rule — check: section present
```
