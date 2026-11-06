"""Exercise evidence validation through its command-line boundary in a Git fixture."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_evidence.py"


class EvidenceCommandTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.evidence = self.root / "docs" / "evidence"
        self.evidence.mkdir(parents=True)
        self.git("init", "-q")
        (self.root / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
        (self.evidence / "result.json").write_bytes(b'{"passed":true}\n')
        (self.evidence / "README.md").write_text("[Result](result.json)\n", encoding="utf-8")
        self.write_manifest()
        self.git("add", ".")
        tree = self.git("write-tree").stdout.strip()
        self.git("update-ref", "refs/heads/baseline", self.git("commit-tree", tree, input="baseline\n").stdout.strip())

    def git(self, *arguments, **kwargs):
        return subprocess.run(["git", "-c", "user.name=Evidence Test", "-c", "user.email=test@example.invalid",
                               *arguments], cwd=self.root, capture_output=True, text=True, check=True, **kwargs)

    def write_manifest(self):
        entries = []
        for p in sorted(self.evidence.rglob("*")):
            if p.is_file() and p.name != "issue13-artifacts.json":
                data = p.read_bytes().replace(b"\r\n", b"\n")
                entries.append({"path": p.relative_to(self.root).as_posix(), "bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()})
        (self.evidence / "issue13-artifacts.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": entries}), encoding="utf-8")

    def check(self, base="baseline"):
        return subprocess.run([sys.executable, str(CHECKER), "--base", base], cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8")

    def test_valid_manifest_and_links_report_added_file_count_and_bytes(self):
        (self.evidence / "new.txt").write_bytes(b"new evidence\n")
        self.write_manifest()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Added evidence files: 1 (13 bytes)", result.stdout)

    def test_unlisted_file_is_rejected(self):
        (self.evidence / "unexpected.txt").write_text("temporary output", encoding="utf-8")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected.txt", result.stdout + result.stderr)

    def test_changed_or_missing_record_is_rejected(self):
        result_path = self.evidence / "result.json"
        result_path.write_bytes(b'{"passed":false}\n')
        self.assertNotEqual(self.check().returncode, 0)
        result_path.unlink()
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing evidence file", result.stderr)

    def test_duplicate_content_is_rejected_even_when_both_files_are_listed(self):
        (self.evidence / "copy.json").write_bytes((self.evidence / "result.json").read_bytes())
        self.write_manifest()
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate evidence content", result.stderr)

    def test_broken_inbound_and_reference_links_fail_but_examples_and_remote_links_do_not(self):
        doc = self.root / "guide.md"
        doc.write_text("[Result](docs/evidence/missing.json)\n", encoding="utf-8")
        self.git("add", "guide.md")
        self.assertNotEqual(self.check().returncode, 0)
        doc.write_text("[result][record]\n\n[record]: docs/evidence/missing.json\n", encoding="utf-8")
        self.assertNotEqual(self.check().returncode, 0)
        doc.write_text("""[remote](https://example.invalid/never-contacted)
![Result](<docs/evidence/result.json>)
`[example](absent.txt)`
```markdown
[example](absent.txt)
```
""", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manifest_cannot_repeat_paths_or_escape_evidence_directory(self):
        manifest = self.evidence / "issue13-artifacts.json"
        original = json.loads(manifest.read_text(encoding="utf-8"))
        for name in ["../outside.txt", "docs/evidence/../../outside.txt", "docs/evidence/result.json"]:
            with self.subTest(name=name):
                data = json.loads(json.dumps(original))
                data["artifacts"].append({**data["artifacts"][-1], "path": name})
                manifest.write_text(json.dumps(data), encoding="utf-8")
                self.assertNotEqual(self.check().returncode, 0)

    def test_git_text_normalization_and_escaped_link_paths(self):
        result_path = self.evidence / "result.json"
        result_path.write_bytes(b'{"passed":true}\r\n')
        (self.evidence / "with space.txt").write_bytes(b"space\n")
        (self.evidence / "README.md").write_text(
            '[Result](result.json)\n[Space](with%20space.txt "title")\n', encoding="utf-8")
        self.write_manifest()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bad_baseline_fails_and_initial_push_counts_every_file(self):
        self.assertNotEqual(self.check("missing-baseline").returncode, 0)
        result = self.check("0" * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Added evidence files: 3", result.stdout)

    def test_git_binary_and_bare_cr_detection_preserve_canonical_bytes(self):
        for payload in [b"\x01" * 100 + b"\r\n", b"line\r\nbare\rreturn\n"]:
            with self.subTest(payload=payload):
                path = self.evidence / "raw.dat"
                path.write_bytes(payload)
                self.write_manifest()
                manifest = self.evidence / "issue13-artifacts.json"
                data = json.loads(manifest.read_text(encoding="utf-8"))
                item = next(e for e in data["artifacts"] if e["path"].endswith("raw.dat"))
                item.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                manifest.write_text(json.dumps(data), encoding="utf-8")
                index_before = (self.root / ".git" / "index").read_bytes()
                objects_before = {p.relative_to(self.root) for p in (self.root / ".git" / "objects").rglob("*") if p.is_file()}
                result = self.check()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.root / ".git" / "index").read_bytes(), index_before)
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual({p.relative_to(self.root) for p in (self.root / ".git" / "objects").rglob("*") if p.is_file()}, objects_before)

    def test_parenthesized_titles_are_checked_and_undefined_brackets_remain_plain_text(self):
        guide = self.root / "guide.md"
        guide.write_text("[Result](docs/evidence/absent.json (evidence record))\n", encoding="utf-8")
        self.git("add", "guide.md")
        self.assertNotEqual(self.check().returncode, 0)
        guide.write_text("[row][col]\n[Result](docs/evidence/result.json (evidence record))\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
