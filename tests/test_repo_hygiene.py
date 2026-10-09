"""Repository-level checks: JSON validity, no sensitive files, no secrets, helpers behave."""

import json
import unittest

from helpers import ROOT, fake_secret

from _common import FrontmatterError, find_secrets, parse_frontmatter

SKIP_DIRS = {".git", "__pycache__", "dist", "node_modules", ".venv"}
SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", ".npmrc", ".pypirc", "credentials.json"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".jsonl", ".yml", ".yaml", ".txt", ".csv", ".conf", ".log", ""}


def repo_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS):
            yield p


class Hygiene(unittest.TestCase):
    def test_all_json_parses(self):
        for p in repo_files():
            if p.suffix == ".json" and "invalid" not in p.parts:
                with self.subTest(file=str(p.relative_to(ROOT))):
                    json.loads(p.read_text(encoding="utf-8"))

    def test_no_sensitive_files(self):
        for p in repo_files():
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertNotIn(p.name, SENSITIVE_NAMES)
                self.assertNotIn(p.suffix, SENSITIVE_SUFFIXES)

    def test_no_secrets_in_text_files(self):
        for p in repo_files():
            if p.suffix in TEXT_SUFFIXES:
                with self.subTest(file=str(p.relative_to(ROOT))):
                    self.assertEqual(find_secrets(p.read_text(encoding="utf-8", errors="replace")), [])

    def test_governance_files_present(self):
        for name in ("LICENSE", "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
                     "CHANGELOG.md", "SKILL.md"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_no_fabricated_benchmark_results(self):
        results = [p for p in (ROOT / "benchmarks/results").iterdir() if p.name != "README.md"]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        if not results:
            self.assertIn("aucun benchmark", readme.lower())


class Helpers(unittest.TestCase):
    def test_find_secrets(self):
        self.assertEqual(find_secrets("nothing here, AKIA is a prefix"), [])
        self.assertIn("aws_access_key", find_secrets("key=" + fake_secret("aws")))
        self.assertIn("private_key", find_secrets(fake_secret("private_key")))
        self.assertEqual(find_secrets('password = "<your-password-here>"'), [])

    def test_frontmatter(self):
        meta, body = parse_frontmatter("---\nname: x\nmetadata:\n  version: \"1.0\"\nflag: true\n---\nBody")
        self.assertEqual(meta, {"name": "x", "metadata": {"version": "1.0"}, "flag": True})
        self.assertEqual(body, "Body")
        for bad in ("no frontmatter", "---\nname: x\n", "---\n  orphan: 1\n---\n", "---\nname: a\nname: b\n---\n",
                    "---\njust text\n---\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(FrontmatterError):
                    parse_frontmatter(bad)


if __name__ == "__main__":
    unittest.main()
