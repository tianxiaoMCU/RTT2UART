"""Run the hardware-free checks shared by local development and Windows CI."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    logs = root / "build" / "checks"
    logs.mkdir(parents=True, exist_ok=True)
    run_logs = Path(tempfile.mkdtemp(prefix="run-", dir=logs))
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PYTHONIOENCODING"] = "utf-8"
    commands = (
        ("whitespace", ["scripts/check_whitespace.py"]),
        ("dependencies", ["-m", "pip", "check"]),
        ("evidence", ["scripts/check_evidence.py"]),
        ("types", ["-m", "mypy", "--strict", "rtt2uart.py", "usb_transport.py", "device_catalog.py",
                   "scripts/package_windows.py", "scripts/check.py", "scripts/check_evidence.py",
                   "scripts/accept_windows.py", "scripts/check_whitespace.py",
                   "tests/fixtures/stm32h750_rtt/build.py",
                   "tests/fixtures/stm32h750_rtt/smoke_usb.py"]),
        ("compile", ["-m", "compileall", "-q", "rtt2uart.py", "usb_transport.py",
                     "main_window.py", "device_catalog.py", "scripts", "tests"]),
        ("tests", ["-X", "faulthandler", "-m", "unittest", "discover", "-s", "tests", "-v"]),
    )
    print(f"Check logs: {run_logs}", flush=True)
    for name, arguments in commands:
        path = run_logs / f"{name}.log"
        print(f"Running {name}...", flush=True)
        with path.open("wb") as log:
            result = subprocess.run([sys.executable, *arguments], cwd=root,
                                    env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print(path.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
            print(f"{name} failed (exit {result.returncode}); see {path}", file=sys.stderr)
            return result.returncode
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
