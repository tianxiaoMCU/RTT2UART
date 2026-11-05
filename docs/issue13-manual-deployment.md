# Issue #13: Manual deployment acceptance on another Windows host

Copy the prepared `RTT2UART-issue13-manual-windows.zip` to another Windows
computer and extract it completely into a new writable folder. Do not overwrite
an existing deployment or its settings. This round covers **GUI and deployment
compatibility**; no probe, Target or virtual serial pair is required.

The [independent-host receipt and representative screenshot](./evidence/issue13-independent-host-2026-11-03/README.md)
were returned on 2026-11-03. The operator reported that the idle GUI checks passed
on Windows 11 22H2 / build 22621.4317 x64 with 64-bit J-Link 7.52b; the final
launcher exit code was 0. Development tools were already installed, so the
clean-host subcase without development dependencies remained unverified. That
round did not cover H09 or other hardware tests. The original handoff steps are
preserved below; the returned receipt retains its template text and filled results.
The [evidence retention policy](./evidence/README.md) explains the compact current
record and how to recover the complete original captures from Git history.

## 1. Install prerequisites and record the environment

The [SSH deployment run on 2026-11-05](./evidence/issue13-deployment-2026-11-05/README.md)
completed the full idle GUI checklist, settings readback and native-module hash
checks on the specified Windows 11 / J-Link 7.54d host. CubeIDE/NI remained
installed, so the result passed within the deployment-compatibility and
development-dependency-isolation scope. At that point, the strict clean-host
requirement still needed either an actual qualifying run or explicit approval
of a scope adjustment. The operator subsequently accepted the
[documented scope qualification](./evidence/issue13-deployment-2026-11-05/gate-qualification-proposal.md)
and requested that #13 be closed within that scope. A bare Windows installation
without development software remains untested and is outside the pass claim.

The destination must run x86-64 Windows. The local baseline for this round is
Windows 10 build 19045 with J-Link 7.54d. Record the actual OS and Runtime versions
on the other machine; do not reuse the local results as its evidence.

If the destination does not have the J-Link Runtime installed, download
**J-Link Software and Documentation Pack → Windows → 64-bit Installer** from
the [official SEGGER download page](https://www.segger.com/downloads/jlink/)
and install it manually. The native Runtime/drivers are a separate prerequisite
and are not bundled in this acceptance package. Record the installer version
in the receipt. If it differs from the local 7.54d baseline, the acceptance result
covers only the combination actually tested. Running this EXE does not require
installing Python, PySide6, PyInstaller or a development IDE.

Do not connect production serial devices or probes for this round. At startup,
the application scans and briefly opens available serial ports. HHD installation
or a virtual-port license is not required. Without a serial pair, do not perform
transfer acceptance tests.

## 2. Verify the extracted files

Keep the following files together in the same folder:

- `rtt2uart.exe`
- `JLinkCommandFile.jlink`
- `JLinkDevicesBuildIn.xml`
- `LICENSE`
- `build-environment.json`
- `settings`: the package's dedicated six-key test configuration, containing no
  operator settings
- `start-test.cmd`, `SHA256SUMS.txt`, this guide and `acceptance-receipt.md`

Before the first launch, run this PowerShell command from that folder:

```powershell
Get-FileHash .\rtt2uart.exe -Algorithm SHA256
```

Expected EXE SHA-256:
`54ba4201db67641607d272ddee062a31aa53ec882f5953dc24e2ea1f8a0bd02d`.
Checksums for the other original files are in `SHA256SUMS.txt`. After the first
launch, interactions change `settings`, and the installed J-Link may refresh the
device-catalog XML. Retain the original ZIP as the baseline.

## 3. Perform the GUI checks in order

Double-click `start-test.cmd`. It sets the working directory to the extracted
folder and launches the same EXE. After normal exit, it writes the return code
to `last-exit-code.txt`. Use the test directory throughout.

1. **First launch:** Confirm that the main window, icon and text are complete,
   with no missing-module, resource or DLL error. The preset Target is
   STM32H750VB, with STM32F407VG also in history; the interface is SWD at
   1000 kHz and the baud rate is 115200. USB is selected and Auto Reconnect is
   unchecked. Use the ports actually enumerated on this machine; the field may
   be empty if no COM port exists. Save `01-initial.png`.
2. **Mode defaults:** Select Existing Session. Auto Reconnect should become
   checked, and the Target/interface/speed/Reset controls should become disabled.
   TCP/IP must remain disabled. Switch back to USB; Auto Reconnect should turn
   off and the relevant controls should become available. Save `02-existing.png`.
3. **Edit and save:** While USB is idle, select STM32F407VG from history, JTAG,
   750 kHz and 19200. Select and record a test port if one is available; otherwise
   record "No available port". Check Auto Reconnect. **Do not click Start**:
   these Target/JTAG values are configuration-test values only. Close the main
   window normally.
4. **Reopen:** Launch the script again. Confirm that the edited Target,
   interface, speed and baud rate remain selected, USB is selected, and Auto
   Reconnect is off again. Compare the port only if enumeration has not changed.
   Save `03-reopened.png`. If the displayed interface differs from the saved
   value, record the original display and steps before changing anything.
5. **Selector safeguards:** Click `...` beside Target and immediately choose
   Cancel; the original Target should remain unchanged. Reopen the selector and
   choose OK without selecting a row; the Target should again remain unchanged.
   Save the selector screenshot as `04-selector.png`.
6. **New and existing history:** Reopen the selector, click the first row, ARM7,
   confirm that ARM7 appears at the top, and choose OK. ARM7 should appear in the
   main window and history. Select STM32H750VB again from the main-window history.
   Test only the GUI: do not click Start or flash firmware. Restore SWD,
   1000 kHz and 115200.
7. **Single instance:** Keep one main window open and launch the script again.
   There should still be only one RTT2UART main window, and the second launcher
   should exit by itself. Do not terminate processes through Task Manager.
8. **Normal exit and reopen:** Close the idle USB window normally. Confirm that
   the window closes, the RTT2UART processes belonging to this test directory
   disappear from Task Manager, and `last-exit-code.txt` contains 0. Reopen and
   check the safe configuration and history. Switch to Existing Session and
   close normally again. Record the final exit behavior.

## 4. Return evidence and respect the acceptance scope

Complete the package's `acceptance-receipt.md` and return it with the screenshots
above and `last-exit-code.txt`. If an error occurs, retain the original screenshot,
Runtime version and exact failing step. Do not mark normal exit as passed after
terminating the process manually. Passwords, computer-account names and network
credentials are not needed in the receipt.

Mark unexecuted receipt items as "Not executed"; do not assume a pass. Record any
existing development environment accurately. This is still evidence from another
host, but it does not automatically prove a clean host with no installed
development dependencies.

This round can establish startup, resources, defaults, configuration/history,
selector behavior, single-instance behavior and normal exit on another Windows
host. It **does not replace** bidirectional probe/Target/serial transfer tests,
native blocking/Stop incomplete tests, two-probe exclusion, or low-level reset/halt
observation. To extend acceptance to real hardware, separately record and prepare
the corresponding probe, Target, drivers and test serial pair.
