# Efficiency: tokens, time, tool calls

## Loading

1. Load `SKILL.md` first.
2. Load one mode file, only if the task is not QUICK.
3. Load a `references/` file only when a step needs it.
4. Platforms without skill loading can use a pre-built bundle (`scripts/bundle.py`), which concatenates core + one mode.

## Working

- Read a file once; keep what you need from it. Re-read only after it changed.
- Reuse inspection results (capabilities, project layout) instead of probing again.
- Answer from context when it is enough; search externally only for what is missing or may have changed.
- Batch independent tool calls when the platform allows it.
- Targeted test first, full suite at the end (and before any release).
- Stop a fix loop after two attempts without progress.
- Reports: a summary plus evidence pointers beats pasting full logs.

## Sub-agents

| Situation | Agents |
|---|---|
| Default | 1 (no sub-agent) |
| Two truly independent workstreams with real time gain | 2 |
| High-stakes work that needs an independent verifier | up to 3, verifier included |

- No recursive delegation (a sub-agent never spawns another).
- Every delegation states: goal, scope (files/resources it may touch), acceptance criteria, expected output format.
- No two agents write the same files or shared resources in parallel.
- The verifier receives the criteria and the deliverable, not the producer's reasoning.

## Measuring

Do not claim savings without numbers. `benchmarks/` records tokens, tool calls and time per run when the platform exposes them; missing values stay `null`, never estimated silently.
