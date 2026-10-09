#!/usr/bin/env python3
"""OMNISKILL benchmark tooling: validate the corpus, plan randomized A/B trials, aggregate results.

This script does not call any model. Trials are run by a person or a harness on the
target platform (with and without OMNISKILL loaded); results are graded independently
and recorded as JSON Lines, one trial per line (format: benchmarks/README.md).

Subcommands
  validate [--tasks DIR]                         check every task file and corpus balance
  plan --env ENV [--env ENV2] --repeats N --seed S --out plan.jsonl
                                                 randomized trial order (A = baseline, B = omniskill)
  report RESULTS.jsonl [...] [--tasks DIR] [--out report.md] [--min-environments 3]
                                                 aggregate metrics and check the publication thresholds

Exit codes: 0 ok, 1 invalid corpus / invalid results / thresholds not met (report --strict), 2 usage error.
Writes only the file given with --out. No network, standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS = ROOT / "benchmarks" / "tasks"
CATEGORIES = {"dev": "DEV", "data": "DATA", "docs": "DOC", "security": "SEC", "research": "RES"}
DIFFICULTIES = {"simple", "complex"}
KINDS = {"standard", "ambiguous", "partially_blocked", "verification_heavy", "adversarial"}
EVAL_METHODS = {"automated", "rubric", "hybrid"}
RESOURCES = {"files", "shell", "python", "node", "web", "none"}
STATUSES = {"VERIFIED", "PARTIAL", "BLOCKED", "UNVERIFIED"}
ARMS = ("baseline", "omniskill")
REQUIRED_TASK_KEYS = ("id", "category", "difficulty", "kind", "prompt", "acceptance_criteria",
                      "evaluation", "expected_evidence", "failure_conditions", "resources")
METRICS = ("tokens", "tool_calls", "duration_s", "corrections", "human_interventions")


# ----------------------------------------------------------------------------- corpus
def validate_task(task: object, fixtures_root: Path) -> list[str]:
    if not isinstance(task, dict):
        return ["task must be a JSON object"]
    errs = [f"missing '{k}'" for k in REQUIRED_TASK_KEYS if k not in task]
    if errs:
        return errs
    tid, cat = task["id"], task["category"]
    if cat not in CATEGORIES:
        errs.append(f"category '{cat}' not in {sorted(CATEGORIES)}")
    elif not (isinstance(tid, str) and tid.startswith(CATEGORIES[cat] + "-") and tid[-3:].isdigit()):
        errs.append(f"id '{tid}' must look like {CATEGORIES[cat]}-NNN for category '{cat}'")
    if task["difficulty"] not in DIFFICULTIES:
        errs.append(f"difficulty '{task['difficulty']}' not in {sorted(DIFFICULTIES)}")
    if task["kind"] not in KINDS:
        errs.append(f"kind '{task['kind']}' not in {sorted(KINDS)}")
    if not isinstance(task["prompt"], str) or len(task["prompt"]) < 10:
        errs.append("prompt must be a string of at least 10 characters")
    crit = task["acceptance_criteria"]
    if not isinstance(crit, list) or not crit:
        errs.append("acceptance_criteria must be a non-empty list")
    else:
        ids = [c.get("id") for c in crit if isinstance(c, dict)]
        if len(ids) != len(crit) or len(set(ids)) != len(ids):
            errs.append("acceptance_criteria need unique 'id' values")
        if not any(isinstance(c, dict) and c.get("essential") is True for c in crit):
            errs.append("at least one acceptance criterion must be essential")
        if any(not isinstance(c, dict) or not c.get("text") for c in crit):
            errs.append("every acceptance criterion needs 'text'")
    if not isinstance(task["evaluation"], dict) or task["evaluation"].get("method") not in EVAL_METHODS:
        errs.append(f"evaluation.method must be one of {sorted(EVAL_METHODS)}")
    for key in ("expected_evidence", "failure_conditions"):
        if not isinstance(task[key], list) or not task[key]:
            errs.append(f"{key} must be a non-empty list")
    if not isinstance(task["resources"], list) or not set(task["resources"]) <= RESOURCES:
        errs.append(f"resources must be a list drawn from {sorted(RESOURCES)}")
    if "expected_status" in task and task["expected_status"] not in STATUSES:
        errs.append(f"expected_status not in {sorted(STATUSES)}")
    if task["kind"] == "partially_blocked" and task.get("expected_status") not in ("BLOCKED", "PARTIAL"):
        errs.append("partially_blocked tasks must set expected_status to BLOCKED or PARTIAL")
    for fx in task.get("fixtures", []):
        p = (fixtures_root / fx).resolve()
        if fixtures_root.resolve() not in p.parents:
            errs.append(f"fixture '{fx}' escapes the fixtures directory")
        elif not p.exists():
            errs.append(f"fixture '{fx}' not found")
    return errs


def load_tasks(tasks_dir: Path) -> tuple[dict[str, dict], list[str]]:
    tasks: dict[str, dict] = {}
    errors: list[str] = []
    fixtures_root = tasks_dir.parent / "fixtures"
    files = sorted(tasks_dir.glob("*.json"))
    if not files:
        return tasks, [f"no task files in {tasks_dir}"]
    for f in files:
        try:
            task = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{f.name}: invalid JSON ({exc})")
            continue
        for e in validate_task(task, fixtures_root):
            errors.append(f"{f.name}: {e}")
        if isinstance(task, dict) and "id" in task:
            if f.stem != task["id"]:
                errors.append(f"{f.name}: file name must equal id '{task['id']}'")
            if task["id"] in tasks:
                errors.append(f"{f.name}: duplicate id {task['id']}")
            tasks[task["id"]] = task
    return tasks, errors


def corpus_summary(tasks: dict[str, dict]) -> tuple[dict, list[str]]:
    by_cat = defaultdict(int)
    by_kind = defaultdict(int)
    by_diff = defaultdict(int)
    for t in tasks.values():
        by_cat[t.get("category")] += 1
        by_kind[t.get("kind")] += 1
        by_diff[t.get("difficulty")] += 1
    warnings = []
    for cat in CATEGORIES:
        if by_cat.get(cat, 0) < 5:
            warnings.append(f"category '{cat}' has {by_cat.get(cat, 0)} tasks (target >= 5)")
    for kind in KINDS:
        if by_kind.get(kind, 0) == 0:
            warnings.append(f"no task of kind '{kind}'")
    return {"total": len(tasks), "by_category": dict(by_cat), "by_kind": dict(by_kind),
            "by_difficulty": dict(by_diff)}, warnings


# ----------------------------------------------------------------------------- plan
def make_plan(task_ids: list[str], envs: list[str], repeats: int, seed: int) -> list[dict]:
    trials = [{"task_id": t, "arm": arm, "environment": env, "repeat": r}
              for t in task_ids for arm in ARMS for env in envs for r in range(1, repeats + 1)]
    random.Random(seed).shuffle(trials)
    for i, tr in enumerate(trials, start=1):
        tr["trial_id"] = f"T{i:05d}"
        tr["order"] = i
    return trials


# ----------------------------------------------------------------------------- results
def validate_result(r: object, known_tasks: set[str]) -> list[str]:
    if not isinstance(r, dict):
        return ["result must be a JSON object"]
    errs = []
    for key in ("trial_id", "task_id", "arm", "environment", "model", "graded_success", "claimed_success", "grader"):
        if key not in r:
            errs.append(f"missing '{key}'")
    if errs:
        return errs
    if r["arm"] not in ARMS:
        errs.append(f"arm must be one of {ARMS}")
    if known_tasks and r["task_id"] not in known_tasks:
        errs.append(f"unknown task_id '{r['task_id']}'")
    for key in ("graded_success", "claimed_success"):
        if not isinstance(r[key], bool):
            errs.append(f"'{key}' must be true or false")
    grader = str(r["grader"])
    if grader.startswith("model:") and grader.split(":", 1)[1] == str(r["model"]):
        errs.append("grader is the model under test; use automated checks or an independent grader")
    for m in METRICS:
        v = r.get(m)
        if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
            errs.append(f"'{m}' must be a non-negative number or null")
    if "claimed_status" in r and r["claimed_status"] is not None and r["claimed_status"] not in STATUSES:
        errs.append("claimed_status not a known status")
    return errs


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for b, c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def _rate(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def _mean(values: list) -> tuple[float | None, int]:
    vals = [v for v in values if v is not None]
    return (statistics.fmean(vals) if vals else None), len(vals)


def aggregate(results: list[dict], tasks: dict[str, dict]) -> dict:
    by_arm: dict[str, list[dict]] = {a: [] for a in ARMS}
    for r in results:
        by_arm[r["arm"]].append(r)

    arms = {}
    for arm, rs in by_arm.items():
        succ = sum(r["graded_success"] for r in rs)
        false_claims = sum(1 for r in rs if r["claimed_success"] and not r["graded_success"])
        claims = sum(1 for r in rs if r["claimed_success"])
        arms[arm] = {
            "trials": len(rs),
            "success_rate": _rate(succ, len(rs)),
            "false_success_claims": false_claims,
            "false_claim_rate_among_claims": _rate(false_claims, claims),
            "security_regressions": sum(1 for r in rs if r.get("security_regression")),
            "critical_security_regressions": sum(1 for r in rs if r.get("critical_security_regression")),
            "metrics": {m: dict(zip(("mean", "n"), _mean([r.get(m) for r in rs]))) for m in METRICS},
        }

    def breakdown(key_fn) -> dict:
        table: dict = defaultdict(lambda: {a: [0, 0] for a in ARMS})
        for r in results:
            cell = table[key_fn(r)][r["arm"]]
            cell[0] += r["graded_success"]
            cell[1] += 1
        return {k: {a: {"success_rate": _rate(*v[a]), "trials": v[a][1]} for a in ARMS}
                for k, v in sorted(table.items())}

    by_category = breakdown(lambda r: tasks.get(r["task_id"], {}).get("category", "unknown"))
    by_environment = breakdown(lambda r: r["environment"])

    # Paired task-level comparison (majority over repeats) per environment/model.
    cells: dict = defaultdict(lambda: {a: [] for a in ARMS})
    for r in results:
        cells[(r["environment"], r["model"], r["task_id"])][r["arm"]].append(r["graded_success"])
    b = c = pairs = 0
    attributable_critical = 0
    crit_cells: dict = defaultdict(lambda: {a: False for a in ARMS})
    for r in results:
        if r.get("critical_security_regression"):
            crit_cells[(r["environment"], r["model"], r["task_id"])][r["arm"]] = True
    for v in crit_cells.values():
        if v["omniskill"] and not v["baseline"]:
            attributable_critical += 1
    for v in cells.values():
        if not v["baseline"] or not v["omniskill"]:
            continue
        pairs += 1
        base = sum(v["baseline"]) / len(v["baseline"]) >= 0.5
        omni = sum(v["omniskill"]) / len(v["omniskill"]) >= 0.5
        if omni and not base:
            b += 1
        elif base and not omni:
            c += 1

    envs_with_both = sorted({e for e, d in by_environment.items()
                             if d["baseline"]["trials"] and d["omniskill"]["trials"]})
    sb, so = arms["baseline"]["success_rate"], arms["omniskill"]["success_rate"]
    delta = None if sb is None or so is None else (so - sb) * 100
    return {
        "arms": arms,
        "delta_success_points": delta,
        "paired": {"task_pairs": pairs, "omniskill_only_success": b, "baseline_only_success": c,
                   "mcnemar_p": mcnemar_exact(b, c) if pairs else None},
        "attributable_critical_security_regressions": attributable_critical,
        "by_category": by_category,
        "by_environment": by_environment,
        "environments_with_both_arms": envs_with_both,
        "tasks_covered": len({r["task_id"] for r in results}),
        "tasks_in_corpus": len(tasks),
    }


def thresholds(agg: dict, min_envs: int) -> list[tuple[str, str, str]]:
    """Return (threshold, verdict PASS/FAIL/INSUFFICIENT_DATA, detail)."""
    out = []
    omni = agg["arms"]["omniskill"]
    if omni["trials"] == 0:
        return [("any threshold", "INSUFFICIENT_DATA", "no omniskill trials")]
    fc = omni["false_success_claims"]
    out.append(("No false success claim (omniskill arm)", "PASS" if fc == 0 else "FAIL", f"{fc} false claims"))
    ac = agg["attributable_critical_security_regressions"]
    out.append(("No critical security regression attributable to the skill", "PASS" if ac == 0 else "FAIL",
                f"{ac} task cells"))
    d = agg["delta_success_points"]
    if d is None:
        out.append(("Success rate +10 points", "INSUFFICIENT_DATA", "baseline arm missing"))
    else:
        p = agg["paired"]["mcnemar_p"]
        out.append(("Success rate +10 points", "PASS" if d >= 10 else "FAIL",
                    f"{d:+.1f} points; paired McNemar p={p:.3f}" if p is not None else f"{d:+.1f} points"))
    n_env = len(agg["environments_with_both_arms"])
    out.append((f">= {min_envs} environments evaluated (both arms)", "PASS" if n_env >= min_envs else "FAIL",
                f"{n_env}: {', '.join(agg['environments_with_both_arms']) or 'none'}"))
    cov = (agg["tasks_covered"], agg["tasks_in_corpus"])
    out.append(("Whole corpus run", "PASS" if cov[0] >= cov[1] else "FAIL", f"{cov[0]}/{cov[1]} tasks"))
    return out


def _fmt_rate(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def render(agg: dict, checks: list[tuple[str, str, str]]) -> str:
    L = ["# OMNISKILL benchmark report", "",
         "Generated by `scripts/run_benchmarks.py report` from graded trial results. "
         "Values marked n/a were not measured.", "",
         "## Overall", "", "| Metric | Baseline | OMNISKILL |", "|---|---|---|"]
    a, o = agg["arms"]["baseline"], agg["arms"]["omniskill"]
    L.append(f"| Trials | {a['trials']} | {o['trials']} |")
    L.append(f"| Success rate | {_fmt_rate(a['success_rate'])} | {_fmt_rate(o['success_rate'])} |")
    L.append(f"| False success claims | {a['false_success_claims']} | {o['false_success_claims']} |")
    L.append(f"| Security regressions (critical) | {a['security_regressions']} ({a['critical_security_regressions']}) "
             f"| {o['security_regressions']} ({o['critical_security_regressions']}) |")
    for m in METRICS:
        ma, mo = a["metrics"][m], o["metrics"][m]
        f = lambda x: "n/a" if x["mean"] is None else f"{x['mean']:.1f} (n={x['n']})"  # noqa: E731
        L.append(f"| Mean {m} | {f(ma)} | {f(mo)} |")
    d = agg["delta_success_points"]
    p = agg["paired"]
    delta_txt = "n/a" if d is None else "%+.1f points" % d
    p_txt = "n/a" if p["mcnemar_p"] is None else "%.3f" % p["mcnemar_p"]
    L += ["", f"Success delta: {delta_txt}. "
          f"Paired task cells: {p['task_pairs']} (OMNISKILL-only wins {p['omniskill_only_success']}, "
          f"baseline-only wins {p['baseline_only_success']}, exact McNemar p = {p_txt}).", ""]
    for title, key in (("By category", "by_category"), ("By environment", "by_environment")):
        L += [f"## {title}", "", "| Group | Baseline | OMNISKILL |", "|---|---|---|"]
        for g, v in agg[key].items():
            L.append(f"| {g} | {_fmt_rate(v['baseline']['success_rate'])} (n={v['baseline']['trials']}) "
                     f"| {_fmt_rate(v['omniskill']['success_rate'])} (n={v['omniskill']['trials']}) |")
        L.append("")
    L += ["## Publication thresholds", "", "| Threshold | Verdict | Detail |", "|---|---|---|"]
    L += [f"| {t} | {v} | {dt} |" for t, v, dt in checks]
    L += ["", "Thresholds are targets, not presumed results. A 30-task corpus is a starting point, "
          "not proof of general superiority.", ""]
    return "\n".join(L)


def load_results(paths: list[str], known: set[str]) -> tuple[list[dict], list[str]]:
    results, errors, seen = [], [], set()
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{path}: cannot read ({exc.strerror})")
            continue
        for n, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{n}: invalid JSON ({exc.msg})")
                continue
            errs = validate_result(r, known)
            if not errs and r["trial_id"] in seen:
                errs = [f"duplicate trial_id {r['trial_id']}"]
            if errs:
                errors += [f"{path}:{n}: {e}" for e in errs]
                continue
            seen.add(r["trial_id"])
            results.append(r)
    return results, errors


# ----------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    pv = sub.add_parser("validate")
    pv.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    pp = sub.add_parser("plan")
    pp.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    pp.add_argument("--env", action="append", required=True, help="environment label, repeatable")
    pp.add_argument("--repeats", type=int, default=1)
    pp.add_argument("--seed", type=int, required=True)
    pp.add_argument("--out", type=Path, required=True)
    pr = sub.add_parser("report")
    pr.add_argument("results", nargs="+")
    pr.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    pr.add_argument("--out", type=Path)
    pr.add_argument("--min-environments", type=int, default=3)
    pr.add_argument("--json", action="store_true")
    pr.add_argument("--strict", action="store_true", help="exit 1 unless every threshold PASSes")
    args = parser.parse_args(argv)

    tasks, task_errors = load_tasks(args.tasks)

    if args.cmd == "validate":
        summary, warnings = corpus_summary(tasks)
        for e in task_errors:
            print(f"ERROR {e}")
        for w in warnings:
            print(f"WARN  {w}")
        print(json.dumps(summary))
        print("VALID" if not task_errors else "INVALID")
        return 0 if not task_errors else 1

    if task_errors:
        print("error: task corpus is invalid; run 'validate' first", file=sys.stderr)
        return 1

    if args.cmd == "plan":
        if args.repeats < 1:
            print("error: --repeats must be >= 1", file=sys.stderr)
            return 2
        plan = make_plan(sorted(tasks), args.env, args.repeats, args.seed)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(t) + "\n" for t in plan), encoding="utf-8")
        print(f"wrote {len(plan)} trials to {args.out} (seed {args.seed})")
        return 0

    results, errors = load_results(args.results, set(tasks))
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    if errors:
        return 1
    if not results:
        print("error: no results", file=sys.stderr)
        return 1
    agg = aggregate(results, tasks)
    checks = thresholds(agg, args.min_environments)
    if args.json:
        output = json.dumps({"aggregate": agg, "thresholds": checks}, indent=2)
    else:
        output = render(agg, checks)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(output)
    if args.strict and any(v != "PASS" for _, v, _ in checks):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
