"""Check the shared local/CI command without running nested check suites."""
from contextlib import redirect_stderr, redirect_stdout
import io
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

            for failure_step in range(1, 6):
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
            self.assertEqual(sorted(len(list(run.glob("*.log"))) for run in runs), [1, 2, 3, 4, 5])
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

            self.assertEqual(len(calls), 5)
            for command, cwd, environment in calls:
                self.assertEqual(command[0], sys.executable)
                self.assertEqual(cwd, root.resolve())
                self.assertEqual(environment["QT_QPA_PLATFORM"], "offscreen")
                self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
            logs = list((root / "build" / "checks").rglob("*.log"))
            self.assertEqual(len(logs), 5)
            self.assertTrue(all("check passed — 测试" in p.read_text(encoding="utf-8") for p in logs))

    def test_cli_failure_has_nonzero_exit_and_does_not_launch_later_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "check.py").write_bytes(Path(check.__file__).read_bytes())
            (root / "pip").mkdir()
            (root / "pip" / "__init__.py").touch()
            (root / "pip" / "__main__.py").write_text(
                "print('controlled dependency failure')\nraise SystemExit(23)\n", encoding="utf-8")

            result = subprocess.run([sys.executable, str(root / "scripts" / "check.py")],
                                    cwd=root, capture_output=True, text=True, encoding="utf-8")

            self.assertEqual(result.returncode, 23)
            self.assertIn("controlled dependency failure", result.stderr)
            self.assertEqual([p.name for p in (root / "build" / "checks").rglob("*.log")], ["dependencies.log"])
