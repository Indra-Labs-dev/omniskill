# Security policy

## Scope

- The skill instructions (`SKILL.md`, `modes/`, `references/`): wording that leads an agent to act unsafely, bypass approvals or follow injected instructions.
- The scripts in `scripts/`: crashes on hostile input, unintended writes, secret leaks, execution of inspected content.
- `guard_command.py` bypasses: dangerous commands classified as `allow`.

Out of scope: the behaviour of a specific AI platform or model, unless OMNISKILL's text makes it worse.

## Reporting

Please **do not open a public issue** for a vulnerability. Use the repository's private vulnerability reporting (GitHub: *Security → Report a vulnerability*) once the repository is published. Until then, contact the maintainer privately.

Include: affected file and version, steps to reproduce, impact, and a suggested fix if you have one. Never include real secrets or personal data.

We aim to acknowledge within 7 days and to publish a fix or mitigation, with credit if you wish, after coordination.

## Design guarantees

- Scripts use the Python standard library only, make no network calls and never execute the content they inspect.
- Only `bundle.py` (its output directory, refusing to overwrite files it did not create) and `run_benchmarks.py plan|report --out` (the file you name) write files.
- CI uses no secrets.

## Residual risks

- Pattern-based command classification can be evaded by obfuscation.
- Secret detection covers common formats only.
- Instructions reduce, but cannot eliminate, unsafe model behaviour.
