# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-10-09 (not published)

### Added
- Core `SKILL.md` in Agent Skills format (~1,200 tokens) with instruction hierarchy, mode selection, evidence-based verification and honest reporting.
- Modes QUICK, PRO, AUTONOMOUS (checkpoint format `schemas/session.schema.json`) and AUDIT (severity × certainty findings).
- References: evidence protocol, capability detection, efficiency, security.
- JSON schemas: evidence report, session checkpoint, capabilities snapshot, benchmark task.
- Scripts (stdlib only): `validate_skill.py`, `validate_evidence.py`, `guard_command.py`, `detect_capabilities.py`, `bundle.py`, `run_benchmarks.py`, `check_repo.sh`.
- Benchmark corpus of 30 tasks with fixtures, A/B protocol, randomized planning, aggregation with exact McNemar test and publication-threshold checks.
- Adapters: generic, platform notes, `AGENTS.md` template.
- Unit tests, GitHub Actions CI, governance files.

### Not done
- No benchmark run yet; no platform has been tested end to end.
