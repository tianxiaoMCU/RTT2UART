"""Check the shared local/CI command without running nested check suites."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import check


class CheckCommandTests(unittest.TestCase):
    def test_failed_step_returns_its_status_and_stops_with_output_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            for failure_step in range(1, 7):
                with self.subTest(failure_step=failure_step):
                    calls = []

                    def fail(command, **kwargs):
                        calls.append(command)
                        kwargs["stdout"].write(b"check output\n")
                        return subprocess.CompletedProcess(command, 23 if len(calls) == failure_step else 0)

                    output = io.StringIO()
                    with patch.object(check, "__file__", str(root / "scripts" / "check.py")), \
                            patch.object(check.subprocess, "run", side_effect=fail), \
                            redirect_stdout(output), redirect_stderr(output):
                        status = check.main()

                    self.assertEqual(status, 23)
                    self.assertEqual(len(calls), failure_step)
                    self.assertIn("check output", output.getvalue())
            runs = list((root / "build" / "checks").iterdir())
            self.assertEqual(sorted(len(list(run.glob("*.log"))) for run in runs), [1, 2, 3, 4, 5, 6])
            self.assertTrue(all(log.read_bytes() == b"check output\n" for run in runs for log in run.glob("*.log")))

    def test_success_uses_current_python_and_checkout_with_isolated_qt_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = []

            def succeed(command, **kwargs):
                calls.append((command, kwargs["cwd"], kwargs["env"]))
                kwargs["stdout"].write("check passed — 测试\n".encode("utf-8"))
                return subprocess.CompletedProcess(command, 0)

            with patch.object(check, "__file__", str(root / "scripts" / "check.py")), \
                    patch.object(check.subprocess, "run", side_effect=succeed), \
                    patch.dict(check.os.environ, {"QT_QPA_PLATFORM": "windows"}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(), 0)
                self.assertEqual(check.os.environ["QT_QPA_PLATFORM"], "windows")

            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[0][0], [sys.executable, 'scripts/check_whitespace.py'])
            for command, cwd, environment in calls:
                self.assertEqual(command[0], sys.executable)
                self.assertEqual(cwd, root.resolve())
                self.assertEqual(environment["QT_QPA_PLATFORM"], "offscreen")
                self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
            logs = list((root / "build" / "checks").rglob("*.log"))
            self.assertEqual(len(logs), 6)
            self.assertTrue(all("check passed — 测试" in p.read_text(encoding="utf-8") for p in logs))

    def test_cli_failure_has_nonzero_exit_and_does_not_launch_later_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "check.py").write_bytes(Path(check.__file__).read_bytes())
            (root / "scripts/check_whitespace.py").write_bytes(
                Path(check.__file__).with_name('check_whitespace.py').read_bytes())
            subprocess.run(['git', 'init', '--quiet'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '--quiet', '--allow-empty', '-m', 'fixture'], cwd=root, check=True)
            (root / "pip").mkdir()
            (root / "pip" / "__init__.py").touch()
            (root / "pip" / "__main__.py").write_text(
                "print('controlled dependency failure')\nraise SystemExit(23)\n", encoding="utf-8")

            result = subprocess.run([sys.executable, str(root / "scripts" / "check.py")],
                                    cwd=root, env={k: v for k, v in os.environ.items() if k != 'EVIDENCE_BASE'},
                                    capture_output=True, text=True, encoding="utf-8")

            self.assertEqual(result.returncode, 23)
            self.assertIn("controlled dependency failure", result.stderr)
            self.assertEqual(sorted(p.name for p in (root / "build" / "checks").rglob("*.log")),
                             ["dependencies.log", "whitespace.log"])


class WhitespaceCommandTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/check.py').write_bytes(Path(check.__file__).read_bytes())
        (self.root / 'scripts/check_whitespace.py').write_bytes(
            Path(check.__file__).with_name('check_whitespace.py').read_bytes())
        (self.root / '.gitattributes').write_bytes(b'* text=auto eol=lf\n*.json -text\n')
        (self.root / 'sample.json').write_bytes(b'{}\n')
        self.git('init', '--quiet')
        self.git('add', '.')
        self.commit()
        self.environment = os.environ.copy()
        self.environment.pop('EVIDENCE_BASE', None)

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.root).decode().strip()

    def commit(self):
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--quiet', '-m', 'fixture')

    def run_whitespace(self, base=None):
        environment = self.environment.copy()
        if base is not None:
            environment['EVIDENCE_BASE'] = base
        return subprocess.run([sys.executable, str(self.root / 'scripts/check_whitespace.py')],
                              cwd=self.root.parent, env=environment,
                              capture_output=True, text=True, encoding='utf-8')

    def test_local_cli_detects_worktree_staged_and_masked_index_errors_without_edits(self):
        for location in ('worktree', 'staged', 'masked-index'):
            for content in (b'{} \n', b'{}\r\n'):
                with self.subTest(location=location, content=content):
                    sample = self.root / 'sample.json'
                    sample.write_bytes(b'{}\n')
                    self.git('add', 'sample.json')
                    sample.write_bytes(content)
                    if location != 'worktree':
                        self.git('add', 'sample.json')
                    if location == 'masked-index':
                        sample.write_bytes(b'{}\n')
                    before = sample.read_bytes(), self.git('status', '--porcelain')
                    result = self.run_whitespace()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('sample.json', result.stdout)
                    self.assertEqual((sample.read_bytes(), self.git('status', '--porcelain')), before)

    def test_ci_baseline_detects_committed_errors_including_new_staged_files(self):
        base = self.git('rev-parse', 'HEAD')
        (self.root / 'sample.json').write_bytes(b'{} \n')
        self.git('add', 'sample.json')
        self.commit()
        self.assertEqual(self.run_whitespace().returncode, 0)
        result = self.run_whitespace(base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sample.json', result.stdout)
        (self.root / 'sample.json').write_bytes(b'{}\n')
        self.git('add', 'sample.json')
        (self.root / 'new.json').write_bytes(b'{}\r\n')
        self.git('add', 'new.json')
        result = self.run_whitespace(base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('new.json', result.stdout)

    def test_initial_push_uses_empty_tree_and_respects_git_attributes(self):
        with (self.root / '.gitattributes').open('ab') as attributes:
            attributes.write(b'allowed.txt -text whitespace=cr-at-eol\n')
        (self.root / 'allowed.txt').write_bytes(b'allowed CRLF\r\n')
        self.git('add', '.gitattributes', 'allowed.txt')
        self.commit()
        (self.root / 'untracked.txt').write_bytes(b'not staged \n')
        for length in (40, 64):
            with self.subTest(zero_hash_length=length):
                result = self.run_whitespace('0' * length)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / 'sample.json').write_bytes(b'{}\r\n')
        self.git('add', 'sample.json')
        self.commit()
        self.assertEqual(self.run_whitespace().returncode, 0)
        for length in (40, 64):
            with self.subTest(zero_hash_length=length):
                result = self.run_whitespace('0' * length)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('sample.json', result.stdout)

    def test_invalid_baselines_fail_without_treating_them_as_git_options(self):
        for base in ('missing-reference', '--output=unexpected-file'):
            with self.subTest(base=base):
                result = self.run_whitespace(base)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Whitespace check failed', result.stderr)
                self.assertFalse((self.root / 'unexpected-file').exists())

    def test_shared_cli_rejects_crlf_before_running_dependencies(self):
        (self.root / 'sample.json').write_bytes(b'{}\r\n')
        (self.root / 'pip').mkdir()
        (self.root / 'pip/__init__.py').touch()
        (self.root / 'pip/__main__.py').write_bytes(b"print('dependencies reached')\nraise SystemExit(23)\n")
        result = subprocess.run([sys.executable, str(self.root / 'scripts/check.py')],
                                cwd=self.root, env=self.environment,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sample.json', result.stderr)
        self.assertNotIn('dependencies reached', result.stdout + result.stderr)
        self.assertEqual([p.name for p in (self.root / 'build/checks').rglob('*.log')], ['whitespace.log'])
