"""Hardware-free acceptance-runner tests using real Windows child processes."""
import json
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import _thread
import unittest
from unittest.mock import patch

from scripts import accept_windows
from scripts.accept_windows import run_acceptance


@unittest.skipUnless(sys.platform == 'win32', 'Windows process/ACL acceptance')
class WindowsAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / 'package'
        self.package.mkdir()
        for name in ('rtt2uart.exe', 'JLinkCommandFile.jlink', 'JLinkDevicesBuildIn.xml',
                     'LICENSE', 'build-environment.json'):
            (self.package / name).write_text('controlled fixture', encoding='utf-8')

    def assert_exited(self, pid):
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x00100001, False, pid)
        if handle:
            try:
                status = api.WaitForSingleObject(handle, 0)
                if status == 258:
                    api.TerminateProcess(handle, 1)
                    api.WaitForSingleObject(handle, 5000)
                self.assertEqual(status, 0, f'PID {pid} still alive after runner cleanup')
            finally:
                api.CloseHandle(handle)
        else:
            self.assertEqual(ctypes.get_last_error(), 87)

    def test_timeout_records_failure_restores_acl_and_reaps_only_owned_process_tree(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: unrelated.wait(timeout=5))
        self.addCleanup(unrelated.kill)
        program = self.root / 'sleeper.py'
        program.write_text(
            "from pathlib import Path\nimport os,subprocess,sys,time\n"
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
            "try:\n (Path.cwd().parent/'program'/'blocked-write').write_text('bad')\n"
            "except PermissionError:\n Path('write-denied').touch()\n"
            "Path('pids.json').write_text(__import__('json').dumps([os.getpid(),child.pid]))\n"
            "time.sleep(60)\n", encoding='utf-8')
        output = self.root / 'run'
        code = run_acceptance(self.package, output, timeout=3,
                              command=[sys.executable, str(program)])
        result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 124, result)
        self.assertEqual(result['status'], 'timeout')
        self.assertTrue(result['process_tree_clean'])
        self.assertTrue(result['acl_restored'], result)
        self.assertEqual(result['cleanup_errors'], [])
        self.assertIsNone(unrelated.poll())
        self.assertEqual(result['files_before'], result['files_after'])
        self.assertTrue((output / 'work' / 'pids.json').exists())
        self.assertTrue((output / 'work' / 'write-denied').exists())
        for pid in json.loads((output / 'work' / 'pids.json').read_text()):
            self.assert_exited(pid)
        (output / 'program' / 'write-probe').write_text('ACL restored')

    def test_normal_exit_keeps_original_package_and_global_environment_unchanged(self):
        original_environment = os.environ.copy()
        output = self.root / 'normal'
        command = [sys.executable, '-c',
                   "import os;from pathlib import Path;Path('settings').write_bytes(b'fixture');"
                   "Path(os.environ['LOCALAPPDATA'],'cache').write_text('fixture')"]
        code = run_acceptance(self.package, output, command=command)
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['acl_restored'])
        self.assertTrue(result['process_tree_clean'])
        self.assertEqual((output / 'work' / 'settings').read_bytes(), b'fixture')
        self.assertEqual((output / 'user' / 'cache').read_text(), 'fixture')
        self.assertEqual(os.environ, original_environment)
        for path in self.package.iterdir():
            self.assertEqual(path.read_text(), 'controlled fixture')

    def test_delayed_job_assignment_cannot_let_the_real_interpreter_escape(self):
        output = self.root / 'delayed-assignment'
        actual_add = accept_windows._Job.add
        def delayed_add(job, pid):
            time.sleep(0.7)
            actual_add(job, pid)
        with patch.object(accept_windows._Job, 'add', delayed_add):
            code = run_acceptance(self.package, output, timeout=1, command=[
                sys.executable, '-c', "import os,time;from pathlib import Path;"
                "Path('target.pid').write_text(str(os.getpid()));time.sleep(15)"])
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(code, 124, result)
        self.assertTrue(result['process_tree_clean'])
        self.assert_exited(int((output / 'work' / 'target.pid').read_text()))

    def test_launch_failure_is_recorded_after_acl_and_process_cleanup(self):
        output = self.root / 'launch-failure'
        self.assertEqual(run_acceptance(self.package, output,
                                       command=[str(self.root / 'missing.exe')]), 1)
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(result['acl_restored'])
        self.assertTrue(result['process_tree_clean'])
        self.assertNotEqual(result['exit_code'], 0)
        self.assertIn(b'FileNotFoundError', (output / 'process.log').read_bytes())

    def test_launcher_exit_does_not_leave_a_descendant_or_claim_normal_shutdown(self):
        output = self.root / 'orphan'
        code = run_acceptance(self.package, output, command=[sys.executable, '-c',
            "import subprocess,sys;from pathlib import Path;"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
            "Path('orphan.pid').write_text(str(p.pid))"])
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(code, 1, result)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Descendants remained', result['error'])
        self.assertTrue(result['process_tree_clean'])
        self.assertTrue(result['acl_restored'])
        self.assert_exited(int((output / 'work' / 'orphan.pid').read_text()))

    def test_keyboard_interrupt_records_interruption_and_still_cleans_up(self):
        output = self.root / 'interrupted'
        finished = threading.Event()
        def interrupt_when_running():
            while not finished.wait(0.02):
                if (output / 'work' / 'ready').exists():
                    _thread.interrupt_main()
                    return
        interrupter = threading.Thread(target=interrupt_when_running)
        interrupter.start()
        try:
            code = run_acceptance(self.package, output, timeout=3, command=[
                sys.executable, '-c', "from pathlib import Path;import time;Path('ready').touch();time.sleep(60)"])
        finally:
            finished.set()
            interrupter.join(timeout=5)
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(code, 130, result)
        self.assertEqual(result['status'], 'interrupted')
        self.assertTrue(result['acl_restored'])
        self.assertTrue(result['process_tree_clean'])

    def test_acl_cleanup_failure_cannot_turn_successful_process_into_a_pass(self):
        output = self.root / 'restore-failure'
        actual_acl = accept_windows._acl
        restored = False
        def fail_readback(directory, action, original=''):
            nonlocal restored
            result = actual_acl(directory, action, original)
            if action == 'restore':
                restored = True
                raise OSError('controlled restore/readback failure')
            return result
        with patch.object(accept_windows, '_acl', side_effect=fail_readback):
            code = run_acceptance(self.package, output, command=[sys.executable, '-c', 'pass'])
        result = json.loads((output / 'result.json').read_text())
        self.assertTrue(restored)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['exit_code'], 0)
        self.assertFalse(result['acl_restored'])
        self.assertIn('controlled restore/readback failure', result['cleanup_errors'][0])

    def test_existing_output_is_rejected_without_overwriting_evidence(self):
        output = self.root / 'existing'
        output.mkdir()
        (output / 'result.json').write_text('previous evidence')
        with self.assertRaises(FileExistsError):
            run_acceptance(self.package, output)
        self.assertEqual((output / 'result.json').read_text(), 'previous evidence')


if __name__ == '__main__':
    unittest.main()
