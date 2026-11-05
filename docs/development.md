# Development

[Project overview](../README.md) | [Getting started](./getting-started.md) | [Architecture](./architecture.md) | [Glossary](../GLOSSARY.md)

This guide covers the current Windows source workflow, UI generation, and a
reproducible packaging procedure. Hardware setup is covered in
[Getting started](./getting-started.md).

## Source layout

| Path | Purpose |
| --- | --- |
| [`main_window.py`](../main_window.py) | GUI entry point, device list, saved settings, and bridge lifecycle controls |
| [`rtt2uart.py`](../rtt2uart.py) | Qt-independent lifecycle for both modes, recovery in both modes, and discard accounting |
| [`usb_transport.py`](../usb_transport.py) | Owned USB direct RTT, probe identity, readiness, and pinned-dependency cleanup |
| [`tests/`](../tests/) | Behavioral bridge tests and controlled Qt integration tests |
| [`rtt2uart.ui`](../rtt2uart.ui) | Main control panel source for Qt Designer |
| [`sel_device.ui`](../sel_device.ui) | Device selector source for Qt Designer |
| [`ui_rtt2uart.py`](../ui_rtt2uart.py), [`ui_sel_device.py`](../ui_sel_device.py) | Generated Python UI modules |
| [`icons.qrc`](../icons.qrc), [`rc_icons.py`](../rc_icons.py) | Qt resource source and generated Python resource module |
| [`requirements.txt`](../requirements.txt) | Pinned Python runtime dependencies |
| [`JLinkCommandFile.jlink`](../JLinkCommandFile.jlink) | Commander script that exports the device database and exits |
| [`JLinkDevicesBuildIn.xml`](../JLinkDevicesBuildIn.xml) | Device database read by the selector and refreshed through Commander |

## Run from source

### Prepare Python and external software

Install a Python version and architecture compatible with the pinned packages
and the installed J-Link runtime. The repository does not declare a tested
Python/Windows/J-Link version matrix.

The commands below use Python 3.11 as an explicit example environment. This
environment was not installed or tested during the documentation review; it is
not a new compatibility guarantee. Use `py --list` to inspect your installed
interpreters, and validate your chosen environment against the pinned packages.

Install the external J-Link software, including its runtime library and
Commander. For end-to-end use, also prepare the virtual COM port pair and target
described in the [prerequisites](./getting-started.md#before-you-begin).

### Create an environment and launch

Open PowerShell in the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe .\main_window.py
```

Calling the environment's interpreter directly avoids requiring PowerShell
activation-script changes. Keep `.venv` out of commits.

The pinned runtime dependencies are:

| Dependency | Version |
| --- | --- |
| `pylink_square` | `1.2.0` |
| `pyserial` | `3.5` |
| `PySide6` | `6.6.1` |
| `PySide6_Addons` | `6.6.1` |
| `PySide6_Essentials` | `6.6.1` |
| `shiboken6` | `6.6.1` |

`PySide6==6.6.1` appears twice in `requirements.txt`. This documentation records
the existing dependency file; it does not change the dependency set. PyInstaller
is a separate development tool and is not pinned there.

Run the GUI entry point, `main_window.py`.
`rtt2uart.py` provides the common lifecycle; `usb_transport.py` provides the owned
USB adapter. Neither is a separate GUI entry point. The legacy USB localhost
backend has been removed.

### Working directory and settings

Launch from the repository root so that relative paths resolve to the tracked
command file and XML database. The current code also reads and writes a binary
`settings` file in the current working directory. It stores device history and
selection indices; see [Settings and startup files](./architecture.md#settings-and-startup-files).

If saved settings prevent startup, close the program and rename that file before
retrying. This resets the saved selections for that working directory. Reselect
the target, interface, speed, serial port, and baud rate after restarting.

The Windows export path currently replaces the process `PATH` with the directory
of the discovered J-Link library before running `JLink.exe`. This is process
behavior, not a persistent system environment change. It explains why Commander
must be available beside the library and why shell lookup assumptions can differ
inside the program.

## Regenerate the UI and resources

Edit the `.ui` files and `icons.qrc` as sources, then regenerate the corresponding
Python modules. Generated UI files identify Qt UI Compiler 6.6.1 and warn that
manual changes are overwritten by regeneration.

Run from the repository root after installing the Python requirements:

```powershell
.\.venv\Scripts\pyside6-uic.exe .\rtt2uart.ui -o .\ui_rtt2uart.py
.\.venv\Scripts\pyside6-uic.exe .\sel_device.ui -o .\ui_sel_device.py
.\.venv\Scripts\pyside6-rcc.exe .\icons.qrc -o .\rc_icons.py
```

Review the generated diff, then launch the GUI to check layout, signal wiring,
and the resource icon. These generation commands were not executed for this
documentation-only change.

## Package for Windows

Install the runtime baseline and the separately pinned build tools, then run the
recipe from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-build.txt
.\.venv\Scripts\python.exe .\scripts\package_windows.py
```

The recipe creates `dist/windows/rtt2uart.exe`, copies the Commander script,
XML catalog, and license, and writes `build-environment.json`. That record contains
Python/Windows/tool versions, Git revision and dirty state, source hashes, and the
EXE hash. Build from a stable checkout; do not edit the inputs during packaging.
It does not certify a launch or hardware transfer. See the
[package smoke procedure and recorded result](./packaging-smoke.md).

For a diagnostic build, remove `--noconsole` from the recipe to keep logging visible. A one-file
executable does not make the entire deployment self-contained:

- The J-Link runtime and Commander remain external prerequisites.
- `JLinkCommandFile.jlink` and `JLinkDevicesBuildIn.xml` must be available in the
  working directory. Copying them beside the executable works when launched
  from that directory; embedding them into a one-file archive alone does not
  change the current code's relative file access.
- The Qt runtime, generated UI modules, and compiled resources must be included
  by the packaging process. Verify their presence by running the result.
- The virtual COM port driver and pair must be configured on the destination
  host.
- Include the [license](../LICENSE) with the distribution and review the
  distribution requirements of the external dependencies you ship.

Launch the candidate from its distribution directory:

```powershell
Push-Location .\dist\windows
try {
    .\rtt2uart.exe
} finally {
    Pop-Location
}
```

Test it on a separate Windows setup without relying on a development virtual
environment. Do not describe the package as verified until the checks below
pass for the recorded configuration.

## Validation checklist

After installing `requirements-dev.txt`, run the same hardware-free checks used
by Windows CI:

```powershell
.\.venv\Scripts\python.exe scripts/check.py
```

The first failure stops the run. Temporary logs are written under ignored
`build/checks/`; CI retains them as artifacts for seven days. See
[Lifecycle migration](./lifecycle-migration.md#reproducible-checks) for the check
scope and [Windows CI](../.github/workflows/check.yml) for the workflow.
Use a recorded manual check for behavior that needs real drivers, probe, Target,
or the packaged application.

| Layer | Check | Evidence to record |
| --- | --- | --- |
| Documentation | Check links, paths, code references, and Markdown whitespace | Source revision and check result |
| Source environment | Install the pinned dependencies in a clean environment and launch `main_window.py` | Python/Windows/J-Link versions and any dependency errors |
| GUI and resources | Open the main window and device selector; check labels, icon, controls, and selection | Screenshots and selected device |
| Device list | Confirm automatic export, and separately check use of the existing XML when export is unavailable | Working directory, Commander version, export output, and database used |
| USB receive | Emit a known target RTT message and observe it through the paired COM endpoint | Probe/target/firmware, interface, speed, COM pair, and observed message |
| USB send | Send a known firmware-supported RTT command and observe the expected target result | Command bytes/line endings and target response |
| Existing Session | Repeat both directions through an externally owned local RTT endpoint | Owning application, endpoint, target, and transfer results |
| Existing Session reconnect | With Auto Reconnect selected, deliberately close and restore the RTT endpoint after initial success | How the socket was closed, retry logs, recovery result, and any missing data |
| USB reconnect | Enable Auto Reconnect, interrupt the original probe/Target/RTT path, attach another probe, then restore the original | Both probe identities, Target/interface/speed, retry results, discarded input, no repeated explicit reset, native connection reset/halt side effects, and Stop during recovery |
| Stop and restart | Stop/close and restart the bridge; verify ports and the intended probe ownership | Resource availability and observed settings after restart |
| Distribution | Run the executable with its companion files from the intended working directory on a separate setup | Asset name, contents, build-tool versions, and runtime results |

Test USB probe loss, Target/RTT loss, and Existing Session endpoint loss
separately. Serial-port loss remains terminal even with Auto Reconnect enabled. A passed receive
test is not a passed send test. A successful package build is not a successful
hardware test.

Current automated and package results are recorded in
[Lifecycle migration](./lifecycle-migration.md) and [Package smoke](./packaging-smoke.md).
Hardware acceptance remains separate.
