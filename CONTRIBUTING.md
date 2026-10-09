# Contributing to OMNISKILL

Thanks for helping. Contributions in French or English are welcome.

## Most useful contributions right now

1. **Benchmark runs.** Run the corpus on a platform (see `benchmarks/README.md`) and submit the plan, raw result lines, `REPORT.md` and `CONDITIONS.md`. Negative results are as welcome as positive ones.
2. **New benchmark tasks**, especially adversarial, ambiguous and partially blocked ones, with fixtures and automatable criteria.
3. **Guard bypasses.** A risky command that `guard_command.py` allows, or a safe common command it blocks. Add it to `tests/test_guard_command.py`.
4. **Platform adapters**, only with a documented, reproducible test on that platform.

## Ground rules

- Keep the core short. `scripts/validate_skill.py` fails the build if `SKILL.md` exceeds its token budget; detail belongs in `modes/` or `references/`.
- Scripts: standard library only, offline, no destructive side effects, clear errors, meaningful exit codes, tests included.
- No fabricated results, no compatibility claims without evidence, no secrets (real or realistic) in the repository. Build secret-shaped test strings at runtime (see `tests/helpers.py`).
- Do not weaken a check to make a test pass.

## Pull request checklist

- [ ] `scripts/check_repo.sh` passes locally (paste the RESULT line in the PR)
- [ ] New behaviour has tests; new scripts have docstrings with usage and exit codes
- [ ] Docs updated (README, `CHANGELOG.md` under *Unreleased*)
- [ ] For benchmark tasks: `python3 scripts/run_benchmarks.py validate` passes
- [ ] For benchmark results: raw data, conditions and grader identity included; grader is not the model under test
- [ ] The PR description ends with an OMNISKILL status report for the change itself

## Review criteria

Maintainers check correctness, evidence, scope (one concern per PR), safety impact and token cost of anything added to the core or modes.

## Conduct

Participation is governed by `CODE_OF_CONDUCT.md`.
