import json
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run_script

import bundle
from _common import estimate_tokens


class Bundle(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.out)

    def test_each_mode_contains_core_and_only_its_mode(self):
        core_marker = "## 6. Verify with evidence"
        for mode in bundle.MODES:
            with self.subTest(mode=mode):
                text = bundle.build(mode)
                self.assertTrue(text.startswith(bundle.MARKER))
                self.assertIn(core_marker, text)
                self.assertNotIn("\nname: omniskill", text)  # frontmatter stripped
                for other in bundle.MODES:
                    heading = f"# Mode {other.upper()}"
                    if other == mode and mode != "quick":
                        self.assertIn(heading, text)
                    else:
                        self.assertNotIn(heading, text)

    def test_bundles_stay_small(self):
        for mode in bundle.MODES:
            self.assertLess(estimate_tokens(bundle.build(mode, with_evidence=True)), 4000)

    def test_writes_all_modes(self):
        proc = run_script("bundle.py", "--mode", "all", "--out", str(self.out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         sorted(f"omniskill-{m}.md" for m in bundle.MODES))

    def test_rerun_overwrites_own_output(self):
        run_script("bundle.py", "--mode", "pro", "--out", str(self.out))
        self.assertEqual(run_script("bundle.py", "--mode", "pro", "--out", str(self.out)).returncode, 0)

    def test_refuses_to_overwrite_foreign_file(self):
        foreign = self.out / "omniskill-pro.md"
        foreign.write_text("my own notes\n", encoding="utf-8")
        proc = run_script("bundle.py", "--mode", "pro", "--out", str(self.out))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(foreign.read_text(encoding="utf-8"), "my own notes\n")
        self.assertEqual(run_script("bundle.py", "--mode", "pro", "--out", str(self.out), "--force").returncode, 0)

    def test_stdout(self):
        proc = run_script("bundle.py", "--mode", "audit", "--stdout")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("# Mode AUDIT", proc.stdout)
        self.assertEqual(run_script("bundle.py", "--mode", "all", "--stdout").returncode, 2)


class Capabilities(unittest.TestCase):
    def test_json_shape(self):
        proc = run_script("detect_capabilities.py", str(ROOT), "--json", "--only", "python3,git")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        snap = json.loads(proc.stdout)
        schema = json.loads((ROOT / "schemas/capabilities.schema.json").read_text(encoding="utf-8"))
        for key in schema["required"]:
            self.assertIn(key, snap)
        self.assertTrue(snap["runtimes"]["python3"].startswith("Python"))
        self.assertEqual(set(snap["runtimes"]) | set(snap["tools"]), {"python3", "git"})
        self.assertIn("SKILL.md", snap["project"]["agent_instructions"])
        self.assertIn("sub_agents", snap["not_detectable"])

    def test_bad_dir(self):
        self.assertEqual(run_script("detect_capabilities.py", "/nonexistent/dir").returncode, 2)

    def test_absent_executable_is_null(self):
        import detect_capabilities as dc
        self.assertIsNone(dc.version_of("definitely-not-a-real-binary-omniskill", ["--version"]))

    def test_writes_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            run_script("detect_capabilities.py", str(tmp), cwd=tmp)
            self.assertEqual(list(tmp.iterdir()), [])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
