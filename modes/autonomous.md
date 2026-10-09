# Mode AUTONOMOUS

For long work with little supervision, which may be interrupted and resumed.

Autonomy never widens permissions. Everything the core requires confirmation for still requires it: when you reach such an action, prepare everything, record the pending decision, and stop that branch.

## Start

1. Write the goal and numbered acceptance criteria.
2. Break the work into steps small enough to verify one by one.
3. If you can write files, create a checkpoint file (default `.omniskill/session.json`, format in `schemas/session.schema.json`). If you cannot, keep the same structure in your messages.
4. If a checkpoint already exists, read it first and resume from it; do not restart finished steps unless their evidence is stale.

## Loop

For each step:

1. Mark it `in_progress` in the checkpoint.
2. Do it.
3. Verify it (the narrowest relevant check).
4. Mark it `done` **only with evidence**, otherwise `failed` or `blocked` with the reason.
5. Save the checkpoint.

Stop the loop when: all steps are done; a step is blocked and nothing else can progress; two consecutive attempts on the same step make no progress; or the budget (time, tokens, tool calls) agreed or reasonable is reached.

## End

- Final report from the core, plus: steps done, steps left, pending decisions, and the exact way to resume (`resume_hint`).
- Never declare the whole job `VERIFIED` when some steps were skipped.

## Checkpoint example

```json
{
  "goal": "Migrate config loader to TOML",
  "updated_at": "2026-10-09T14:00:00Z",
  "steps": [
    {"id": "S1", "title": "Add TOML parser", "status": "done", "evidence": "pytest tests/test_config.py: 12 passed"},
    {"id": "S2", "title": "Migrate env overrides", "status": "in_progress"},
    {"id": "S3", "title": "Delete legacy INI files", "status": "blocked", "reason": "destructive: needs user approval"}
  ],
  "pending_decisions": ["Approve deletion of config/*.ini (3 files)"],
  "resume_hint": "Finish S2, run full test suite, then ask about S3."
}
```
