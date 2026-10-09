import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, run_script

import validate_skill

MODES = ("quick", "pro", "autonomous", "audit")
GOOD_BODY = "\n".join(["# Core", "Modes: `modes/pro.md`, `modes/autonomous.md`, `modes/audit.md`."])


def make_skill(tmp: Path, front: str, body: str = GOOD_BODY, modes=MODES, name="omniskill") -> Path:
    d = tmp / name
    (d / "modes").mkdir(parents=True)
    for m in modes:
        (d / "modes" / f"{m}.md").write_text(f"# {m}\n", encoding="utf-8")
    (d / "SKILL.md").write_text(front + body, encoding="utf-8")
    return d


FRONT = "---\nname: omniskill\ndescription: A universal working protocol used for testing the validator here.\n---\n"


class ValidateSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_repository_skill_is_valid(self):
        result = validate_skill.validate(ROOT)
        self.assertTrue(result["valid"], result["errors"])
        self.assertLessEqual(result["info"]["core_tokens_estimate"], validate_skill.DEFAULT_MAX_CORE_TOKENS)

    def test_cli_exit_codes(self):
        self.assertEqual(run_script("validate_skill.py", str(ROOT)).returncode, 0)
        self.assertEqual(run_script("validate_skill.py", str(self.tmp / "nope")).returncode, 2)
        self.assertEqual(run_script("validate_skill.py", str(self.tmp)).returncode, 1)  # no SKILL.md

    def test_minimal_valid_skill(self):
        d = make_skill(self.tmp, FRONT)
        self.assertTrue(validate_skill.validate(d)["valid"])

    def test_missing_frontmatter(self):
        d = make_skill(self.tmp, "", body="# no frontmatter")
        r = validate_skill.validate(d)
        self.assertFalse(r["valid"])
        self.assertIn("frontmatter", r["errors"][0])

    def test_unclosed_frontmatter(self):
        d = make_skill(self.tmp, "---\nname: omniskill\n", body="")
        self.assertFalse(validate_skill.validate(d)["valid"])

    def test_bad_name(self):
        for bad in ("OmniSkill", "omni--skill", "-omni", "omni_skill", "a" * 65):
            with self.subTest(bad=bad):
                tmp = Path(tempfile.mkdtemp(dir=self.tmp))
                d = make_skill(tmp, FRONT.replace("name: omniskill", f"name: {bad}"))
                self.assertFalse(validate_skill.validate(d)["valid"])

    def test_description_too_long(self):
        d = make_skill(self.tmp, FRONT.replace("A universal", "x" * 1100))
        r = validate_skill.validate(d)
        self.assertTrue(any("1024" in e for e in r["errors"]))

    def test_missing_description(self):
        d = make_skill(self.tmp, "---\nname: omniskill\n---\n")
        self.assertFalse(validate_skill.validate(d)["valid"])

    def test_missing_mode_file(self):
        d = make_skill(self.tmp, FRONT, modes=("quick", "pro", "audit"))
        r = validate_skill.validate(d)
        self.assertTrue(any("modes/autonomous.md" in e for e in r["errors"]))

    def test_mode_not_referenced(self):
        d = make_skill(self.tmp, FRONT, body="# Core\n`modes/pro.md` `modes/audit.md`")
        r = validate_skill.validate(d)
        self.assertTrue(any("does not reference modes/autonomous.md" in e for e in r["errors"]))

    def test_broken_cited_path(self):
        d = make_skill(self.tmp, FRONT, body=GOOD_BODY + "\nSee `references/missing.md`.")
        r = validate_skill.validate(d)
        self.assertTrue(any("references/missing.md" in e for e in r["errors"]))

    def test_core_over_budget(self):
        d = make_skill(self.tmp, FRONT, body=GOOD_BODY + "\n" + "word " * 2000)
        self.assertFalse(validate_skill.validate(d, max_core_tokens=500)["valid"])

    def test_unknown_key_is_warning_not_error(self):
        d = make_skill(self.tmp, FRONT.replace("---\nname", "---\nfoo: bar\nname"))
        r = validate_skill.validate(d)
        self.assertTrue(r["valid"])
        self.assertTrue(any("foo" in w for w in r["warnings"]))

    def test_name_must_match_directory(self):
        d = make_skill(self.tmp, FRONT, name="other-dir")
        self.assertFalse(validate_skill.validate(d)["valid"])
        self.assertTrue(validate_skill.validate(d, allow_dir_mismatch=True)["valid"])

    def test_metadata_values_must_be_strings(self):
        d = make_skill(self.tmp, FRONT.replace("---\nname", "---\nmetadata:\n  stable: true\nname"))
        self.assertTrue(any("metadata" in e for e in validate_skill.validate(d)["errors"]))

    def test_non_utf8_file(self):
        d = make_skill(self.tmp, FRONT)
        (d / "SKILL.md").write_bytes(b"---\nname: \xff\xfe\n---\n")
        self.assertFalse(validate_skill.validate(d)["valid"])

    def test_does_not_modify_files(self):
        d = make_skill(self.tmp, FRONT)
        before = (d / "SKILL.md").read_bytes()
        validate_skill.validate(d)
        self.assertEqual(before, (d / "SKILL.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
