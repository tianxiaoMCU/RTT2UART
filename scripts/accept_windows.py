"""Own one isolated Windows EXE acceptance run, including failure cleanup."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


FILES = ('rtt2uart.exe', 'JLinkCommandFile.jlink', 'JLinkDevicesBuildIn.xml',
         'LICENSE', 'build-environment.json')


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class _Limits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [('times', ctypes.c_int64 * 4), ('faults', wintypes.DWORD),
                ('total', wintypes.DWORD), ('active', wintypes.DWORD),
                ('terminated', wintypes.DWORD)]


class _Job:
    def __init__(self) -> None:
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [wintypes.LPVOID, wintypes.LPCWSTR], wintypes.HANDLE),
            ('SetInformationJobObject', [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                         wintypes.DWORD], wintypes.BOOL),
            ('QueryInformationJobObject', [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                           wintypes.DWORD, wintypes.LPVOID], wintypes.BOOL),
            ('OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            ('AssignProcessToJobObject', [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            ('TerminateJobObject', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            ('CloseHandle', [wintypes.HANDLE], wintypes.BOOL),
        ):
            function = getattr(self.api, name)
            function.argtypes = args
            function.restype = result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits),
                                                ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def add(self, pid: int) -> None:
        process = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.api.CloseHandle(process)

    def active(self) -> int:
        info = _Accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info),
                                                  ctypes.sizeof(info), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(info.active)

    def terminate(self) -> None:
        if not self.api.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def wait_empty(self) -> bool:
        deadline = time.monotonic() + 5
        while self.active():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)
        return True

    def close(self) -> None:
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None


_ACL_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$path = $env:RTT2UART_ACCEPTANCE_DIR
if ($env:RTT2UART_ACL_ACTION -eq 'read') {
    (Get-Acl -LiteralPath $path).Sddl
} elseif ($env:RTT2UART_ACL_ACTION -eq 'deny') {
    $acl = Get-Acl -LiteralPath $path
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $sid, 'Write, Delete, DeleteSubdirectoriesAndFiles',
        'ContainerInherit, ObjectInherit', 'None', 'Deny'))
    Set-Acl -LiteralPath $path -AclObject $acl
} else {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetSecurityDescriptorSddlForm($env:RTT2UART_ORIGINAL_ACL)
    Set-Acl -LiteralPath $path -AclObject $acl
}
'''


def _acl(directory: Path, action: str, original: str = '') -> str:
    environment = os.environ.copy()
    environment.pop('PSModulePath', None)
    environment.update(RTT2UART_ACCEPTANCE_DIR=str(directory), RTT2UART_ACL_ACTION=action,
                       RTT2UART_ORIGINAL_ACL=original)
    powershell = shutil.which('pwsh')
    if powershell is None:
        raise FileNotFoundError('PowerShell 7 (pwsh) is required for acceptance ACL handling')
    result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', _ACL_SCRIPT],
                            env=environment, capture_output=True, text=True, encoding='utf-8',
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    if result.returncode:
        raise OSError(result.stderr.strip())
    return result.stdout.strip()


def _hashes(directory: Path) -> dict[str, str]:
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in FILES}


def _save(output: Path, record: dict[str, object]) -> None:
    temporary = output / 'result.tmp'
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    os.replace(temporary, output / 'result.json')


def run_acceptance(package: Path, output: Path, timeout: float = 1800, *,
                   command: list[str] | None = None) -> int:
    """Run a copied package; command overrides only the process in controlled tests."""
    if sys.platform != 'win32':
        raise RuntimeError('EXE acceptance is supported only on Windows')
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be a finite positive number')
    package, output = package.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    program, work, user = (output / name for name in ('program', 'work', 'user'))
    errors: list[str] = []
    record: dict[str, object] = {'status': 'running', 'timeout_seconds': timeout,
                                'process_tree_clean': True, 'acl_restored': True,
                                'cleanup_errors': errors}
    _save(output, record)
    job = None
    worker = None
    original_acl = None
    try:
        for directory in (program, work, user):
            directory.mkdir()
        for name in FILES:
            shutil.copyfile(package / name, program / name)
        record['files_before'] = _hashes(program)
        original_acl = _acl(program, 'read')
        (output / 'program-acl.sddl').write_text(original_acl, encoding='utf-8')
        record['acl_restored'] = False
        _acl(program, 'deny')
        environment = os.environ.copy()
        environment['LOCALAPPDATA'] = str(user)
        environment.pop('QT_QPA_PLATFORM', None)
        job = _Job()
        # Use the real interpreter: the venv redirector can spawn outside the job.
        interpreter = Path(sys.base_prefix) / 'python.exe'
        # The supervisor cannot spawn the EXE until it has joined our job.
        supervisor = ('import json,subprocess,sys; '
                      'sys.exit(subprocess.call(json.load(sys.stdin)))')
        with (output / 'process.log').open('wb') as log:
            worker = subprocess.Popen([str(interpreter), '-c', supervisor], cwd=work,
                                      env=environment, stdin=subprocess.PIPE, stdout=log,
                                      stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            record['supervisor_pid'] = worker.pid
            record['process_tree_clean'] = False
            job.add(worker.pid)
            _save(output, record)
            assert worker.stdin is not None
            worker.stdin.write(json.dumps(command if command is not None else
                                          [str(program / 'rtt2uart.exe')]).encode('utf-8'))
            worker.stdin.close()
            print(f'Acceptance run: {output}', flush=True)
            code = worker.wait(timeout=timeout)
            record['exit_code'] = code
            record['status'] = 'passed' if code == 0 else 'failed'
            if code:
                record['error'] = f'Test process exited with code {code}; see process.log'
    except subprocess.TimeoutExpired as error:
        record.update(status='timeout', error=str(error))
    except KeyboardInterrupt:
        record.update(status='interrupted', error='Acceptance interrupted')
    except Exception as error:
        record.update(status='failed', error=str(error))
    finally:
        try:
            if worker is not None and worker.stdin is not None and not worker.stdin.closed:
                worker.stdin.close()
            if job is not None and record['status'] == 'passed' and not job.wait_empty():
                record.update(status='failed', error='Descendants remained after launcher exit')
            if job is not None and job.active():
                job.terminate()
            if job is not None and not job.wait_empty():
                raise TimeoutError('Owned process tree did not exit')
            record['process_tree_clean'] = job is None or job.active() == 0
        except (Exception, KeyboardInterrupt) as error:
            errors.append(f'Process cleanup: {error}')
        finally:
            if job is not None:
                try:
                    job.close()
                except (Exception, KeyboardInterrupt) as error:
                    errors.append(f'Job close: {error}')
        if worker is not None:
            try:
                if worker.poll() is None:
                    worker.kill()
                worker.wait(timeout=5)
            except (Exception, KeyboardInterrupt) as error:
                record['process_tree_clean'] = False
                errors.append(f'Supervisor cleanup: {error}')
        if original_acl is not None:
            try:
                _acl(program, 'restore', original_acl)
                restored = _acl(program, 'read')
                # Set-Acl may stamp AI (auto-inherited); it does not change the ACEs.
                record['acl_restored'] = (re.sub(r'(D:[A-Z]*)AI', r'\1', restored) ==
                                          re.sub(r'(D:[A-Z]*)AI', r'\1', original_acl))
                if not record['acl_restored']:
                    raise OSError('Restored ACL does not match the saved descriptor')
            except (Exception, KeyboardInterrupt) as error:
                errors.append(f'ACL restore: {error}')
        try:
            if 'files_before' in record:
                record['files_after'] = _hashes(program)
                if record['files_before'] != record['files_after']:
                    errors.append('Copied program/companion files changed')
        except (Exception, KeyboardInterrupt) as error:
            errors.append(f'File verification: {error}')
        if errors and record['status'] == 'passed':
            record['status'] = 'failed'
        _save(output, record)
    return {'passed': 0, 'timeout': 124, 'interrupted': 130}.get(str(record['status']), 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path('dist/windows'))
    parser.add_argument('--output', type=Path, required=True, help='New run directory; must not exist')
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    return run_acceptance(args.package, args.output, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
