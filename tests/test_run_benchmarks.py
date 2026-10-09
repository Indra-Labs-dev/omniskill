"""Tests for the benchmark tooling. All result lines here are synthetic test fixtures, not measurements."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run_script

import run_benchmarks as rb

TASKS, TASK_ERRORS = rb.load_tasks(rb.DEFAULT_TASKS)


def result(trial, task, arm, env="env-a", success=True, claimed=True, **extra):
    r = {"trial_id": trial, "task_id": task, "arm": arm, "environment": env, "model": "model-x",
         "graded_success": success, "claimed_success": claimed, "grader": "automated",
         "tokens": None, "tool_calls": 5, "duration_s": 10.0}
    r.update(extra)
    return r


class Corpus(unittest.TestCase):
    def test_repository_corpus_is_valid_and_balanced(self):
        self.assertEqual(TASK_ERRORS, [])
        summary, warnings = rb.corpus_summary(TASKS)
        self.assertEqual(summary["total"], 30)
        self.assertEqual(warnings, [])
        self.assertEqual(set(summary["by_category"].values()), {6})

    def test_essential_failures_in_task_definitions(self):
        good = copy.deepcopy(TASKS["DEV-001"])
        fx = rb.DEFAULT_TASKS.parent / "fixtures"
        self.assertEqual(rb.validate_task(good, fx), [])
        cases = {
            "id": dict(id="DATA-001"),
            "essential": dict(acceptance_criteria=[{"id": "C1", "text": "x", "essential": False}]),
            "escapes": dict(fixtures=["../../SKILL.md"]),
            "not found": dict(fixtures=["dev-001/nope.py"]),
            "kind": dict(kind="weird"),
            "expected_status": dict(kind="partially_blocked", expected_status="VERIFIED"),
        }
        for fragment, change in cases.items():
            with self.subTest(fragment=fragment):
                t = copy.deepcopy(good)
                t.update(change)
                self.assertTrue(any(fragment in e for e in rb.validate_task(t, fx)), rb.validate_task(t, fx))

    def test_cli_validate(self):
        self.assertEqual(run_script("run_benchmarks.py", "validate").returncode, 0)
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "tasks").mkdir()
            (tmp / "tasks" / "DEV-999.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(run_script("run_benchmarks.py", "validate", "--tasks", str(tmp / "tasks")).returncode, 1)
        finally:
            shutil.rmtree(tmp)


class Plan(unittest.TestCase):
    def test_plan_is_complete_and_reproducible(self):
        ids = sorted(TASKS)
        p1 = rb.make_plan(ids, ["a", "b"], 2, seed=7)
        p2 = rb.make_plan(ids, ["a", "b"], 2, seed=7)
        p3 = rb.make_plan(ids, ["a", "b"], 2, seed=8)
        self.assertEqual(len(p1), 30 * 2 * 2 * 2)
        self.assertEqual(p1, p2)
        self.assertNotEqual([t["task_id"] for t in p1], [t["task_id"] for t in p3])
        self.assertEqual(len({t["trial_id"] for t in p1}), len(p1))
        keys = {(t["task_id"], t["arm"], t["environment"], t["repeat"]) for t in p1}
        self.assertEqual(len(keys), len(p1))

    def test_cli_plan_writes_only_out(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "plan.jsonl"
            proc = run_script("run_benchmarks.py", "plan", "--env", "x", "--seed", "1", "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(out.read_text().splitlines()), 60)
            self.assertEqual([p.name for p in tmp.iterdir()], ["plan.jsonl"])
        finally:
            shutil.rmtree(tmp)


class Stats(unittest.TestCase):
    def test_mcnemar(self):
        self.assertEqual(rb.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(rb.mcnemar_exact(10, 0), 2 / 1024)
        self.assertAlmostEqual(rb.mcnemar_exact(5, 5), 1.0)
        self.assertLess(rb.mcnemar_exact(12, 2), 0.05)


class Results(unittest.TestCase):
    def test_rejects_self_grading_and_bad_fields(self):
        known = set(TASKS)
        self.assertEqual(rb.validate_result(result("T1", "DEV-001", "omniskill"), known), [])
        cases = {
            "model under test": dict(grader="model:model-x"),
            "arm": dict(arm="treatment"),
            "unknown task_id": dict(task_id="DEV-999"),
            "graded_success": dict(graded_success="yes"),
            "tokens": dict(tokens=-5),
        }
        for fragment, change in cases.items():
            with self.subTest(fragment=fragment):
                r = result("T1", "DEV-001", "omniskill")
                r.update(change)
                errs = rb.validate_result(r, known)
                self.assertTrue(any(fragment in e for e in errs), errs)
        self.assertEqual(rb.validate_result(result("T1", "DEV-001", "omniskill", grader="model:other"), known), [])

    def test_aggregate_counts_false_claims_and_delta(self):
        rs = [
            result("T1", "DEV-001", "baseline", success=False, claimed=True),   # false claim
            result("T2", "DEV-001", "omniskill", success=True),
            result("T3", "SEC-001", "baseline", success=True),
            result("T4", "SEC-001", "omniskill", success=True),
            result("T5", "DOC-001", "baseline", success=False, claimed=False),
            result("T6", "DOC-001", "omniskill", success=False, claimed=False,
                   security_regression=True, critical_security_regression=True),
        ]
        agg = rb.aggregate(rs, TASKS)
        self.assertEqual(agg["arms"]["baseline"]["false_success_claims"], 1)
        self.assertEqual(agg["arms"]["omniskill"]["false_success_claims"], 0)
        self.assertAlmostEqual(agg["delta_success_points"], (2 / 3 - 1 / 3) * 100)
        self.assertEqual(agg["paired"]["omniskill_only_success"], 1)
        self.assertEqual(agg["paired"]["baseline_only_success"], 0)
        self.assertEqual(agg["attributable_critical_security_regressions"], 1)
        self.assertEqual(agg["arms"]["omniskill"]["metrics"]["tokens"]["n"], 0)  # null never estimated
        checks = dict((t, v) for t, v, _ in rb.thresholds(agg, 3))
        self.assertEqual(checks["No false success claim (omniskill arm)"], "PASS")
        self.assertEqual(checks["No critical security regression attributable to the skill"], "FAIL")
        self.assertEqual(checks[">= 3 environments evaluated (both arms)"], "FAIL")
        self.assertEqual(checks["Whole corpus run"], "FAIL")

    def test_report_cli_and_strict(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            lines = [result("T1", "DEV-001", "baseline", success=False),
                     result("T2", "DEV-001", "omniskill", success=True)]
            f = tmp / "r.jsonl"
            f.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
            out = tmp / "REPORT.md"
            proc = run_script("run_benchmarks.py", "report", str(f), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = out.read_text(encoding="utf-8")
            for heading in ("## Overall", "## By category", "## By environment", "## Publication thresholds"):
                self.assertIn(heading, text)
            self.assertEqual(run_script("run_benchmarks.py", "report", str(f), "--strict").returncode, 1)
            dup = tmp / "dup.jsonl"
            dup.write_text(json.dumps(lines[0]) + "\n" + json.dumps(lines[0]) + "\n", encoding="utf-8")
            self.assertEqual(run_script("run_benchmarks.py", "report", str(dup)).returncode, 1)
            bad = tmp / "bad.jsonl"
            bad.write_text("{oops\n", encoding="utf-8")
            self.assertEqual(run_script("run_benchmarks.py", "report", str(bad)).returncode, 1)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
