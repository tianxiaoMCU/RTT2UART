"""Build the Windows candidate and record its exact inputs; no hardware access."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This packaging recipe is validated only on Windows.")
    root = Path(__file__).resolve().parents[1]
    destination = root / "dist" / "windows"
    work = root / "build" / "windows"
    destination.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--noconsole", "--name", "rtt2uart",
        "--icon", str(root / "swap_horiz_16px.ico"),
        "--distpath", str(destination), "--workpath", str(work),
        "--specpath", str(work), str(root / "main_window.py"),
    ], cwd=root, check=True)
    companions = ["JLinkCommandFile.jlink", "JLinkDevicesBuildIn.xml", "LICENSE"]
    for name in companions:
        shutil.copyfile(root / name, destination / name)
    sources = ["main_window.py", "rtt2uart.py", "usb_transport.py", "device_catalog.py",
               "ui_rtt2uart.py", "ui_sel_device.py", "rc_icons.py",
               "rtt2uart.ui", "sel_device.ui", "icons.qrc", "swap_horiz_16px.ico",
               "requirements.txt", "requirements-build.txt", "scripts/package_windows.py",
               *companions]
    packages = ["pylink-square", "pyserial", "PySide6", "PySide6-Addons",
                "PySide6-Essentials", "shiboken6", "PyInstaller",
                "pyinstaller-hooks-contrib", "altgraph", "packaging", "pefile",
                "pywin32-ctypes", "setuptools"]
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    record = {
        "revision": git("rev-parse", "HEAD"),
        "working_tree_changes": git("status", "--short"),
        "python": sys.version,
        "windows": platform.platform(),
        "architecture": platform.machine(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in sources},
        "exe_sha256": hashlib.sha256((destination / "rtt2uart.exe").read_bytes()).hexdigest(),
        "external_prerequisites": ["J-Link runtime and Commander", "Virtual COM port pair for transfer"],
        "smoke_result": "Not established by building; record the manual checklist separately.",
    }
    (destination / "build-environment.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Candidate: {destination}")


if __name__ == "__main__":
    main()
