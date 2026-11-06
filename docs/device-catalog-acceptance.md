# Issue #14: Target catalog acceptance

Date: 2026-11-06 (Asia/Shanghai). Development baseline: `74da3ff`.
Scope: automatic known-input invalidation, validated user cache, background export,
live selector presentation and existing selection/bridge compatibility.

## Controlled checks

The agreed seam is `DeviceCatalog.prepare()` / `snapshot`, also used by the GUI.
`tests/test_device_catalog.py` uses small XML fixtures, temporary directories,
controlled source/export adapters and real owned child processes for deadline and
cancellation checks. `tests/test_main_window.py` retains legacy history/settings
and bridge lifecycle coverage and adds loading, same-dialog completion, fallback,
Retry, event-loop delivery and closed-dialog safety checks.

Targeted run: `.venv\Scripts\python.exe -m unittest tests.test_device_catalog tests.test_main_window -v`
passed 31 tests. Strict mypy passed for the new module and changed check/build scripts.
Independent Standards review found no hard rule violations or actionable smells;
it found stale resource/PATH documentation, now corrected. Spec review found one
P2 diagnostic gap (cache-read cause lost when discovery also fails), fixed with a
failing-then-passing regression test. Both reviewers confirmed closure at `edad0a6`.

Final `.venv\Scripts\python.exe scripts/check.py` passed: dependency consistency,
evidence integrity, strict mypy, compilation and **91 tests** (21.452 seconds).
No product code changed after that run. The [compact evidence record](./evidence/issue14-2026-11-06/evidence.json)
retains the tested candidate identity, build inputs, results and limits.

## Real installed Commander and source GUI

Windows 10 x64 build 19045; Python 3.12.13; pylink-square 1.2.0; PySide6 6.6.1;
pyserial 3.5. Default pylink discovery selected the following original installed
inputs (not the random temporary DLL copy):

| Input | SHA-256 |
| --- | --- |
| `C:\Program Files\SEGGER\JLink\JLink.exe` | `f371800c81ec158c3beb8240bf894e08c1570c8907e67ff384993302f69a870b` |
| `C:\Program Files\SEGGER\JLink\JLink_x64.dll` | `82ad22e5642867d14884eaf4bfe09fbebc1a7cc8de30c15981083f48b903aa43` |
| Exact shipped script | `5c9dc5862f477ee27700fe3bb0bca5ea49c75bd8ad08aa23830156e63b20c90f` |
| Shipped fallback XML | `15e02e5ff528f656c46d426ce4553aa0919625288773e3be856f5df004e8b464` |

Known-input fingerprint: `2892d9bd32efb0a1915ba75be232fe7087a899b7bff9a9583308e2abc476cbf1`.
First preparation produced **8,788 records** and one real Commander invocation;
two new catalog instances returned `cached`, still one total invocation. The child
ran the explicit selected executable/script in its own temporary directory. Global
PATH/CWD and shipped companions remained unchanged. Observed preparation times
were 0.641 / 0.140 / 0.141 seconds; these are one-host observations, not a benchmark.

The source GUI was launched from a different writable working directory containing
a deliberately invalid decoy XML. It showed Loading and populated 8,788 rows in
the same dialog while the Qt event loop continued; normal close completed. This
was an offscreen Qt integration run, not native Windows visual acceptance.

The same check was repeated with copied source/resources in a directory carrying
an explicit current-user write-deny ACL (a write probe raised PermissionError).
The GUI, first export, two matching-cache preparations and normal close passed;
8,788 records remained available. The writable launch directory retained settings
and private user data. The original ACL was restored after the check. No production
installation, saved settings, probe or Target was modified.

Temporary drivers, JSON results and diagnostic captures are under ignored
`build/issue14/`; this concise record retains the decisive results.

## Windows package

Built with `.venv\Scripts\python.exe scripts/package_windows.py` at source revision
`edad0a6260965a5129b3947e11c4264feb0d97e3`, with pinned runtime/build dependencies.
Only the pre-existing untracked Harness assessment was outside the clean tracked
checkout. Candidate EXE SHA-256:
`ced4cdbf9ec00fbfc12421b4a58831f5dc804ac325b5c12793073557816c025a`.

Native GUI acceptance used **agent-desktop 1.2.0**, headless semantic UIA operations
and window screenshots, on the same Windows/J-Link setup. A copied EXE/resources
directory carried an explicit current-user write-deny ACL. Launch CWD, settings and
private LOCALAPPDATA were separate writable directories; an invalid decoy XML in
CWD was ignored. No physical mouse/keyboard fallback was used.

- The main window, icon, labels and saved STM32F103C8/SWD/1000 kHz/115200 settings
  were readable. The source-matched selector displayed its expected columns/data.
- Cancel and OK without a selected row retained STM32F103C8 and its two-entry history.
- Retry showed [Loading with selection disabled](./evidence/issue14-2026-11-06/selector-loading.png),
  then [ready data in the same native dialog](./evidence/issue14-2026-11-06/selector-ready.png).
  The cache modification time changed from `1793925223184215500` to
  `1793926866683913000` ns and contained 8,788 validated records. Refresh did not
  change the current Target.
- A subsequent application launch retained that cache modification time, history
  and settings. Existing Session disabled Target/interface/speed controls and
  checked Auto Reconnect; TCP/IP remained disabled.
- Final normal close was verified as graceful process exit by agent-desktop and
  exit code **0** by the launch driver. Companion script/XML hashes were unchanged.
  The original resource-directory ACL was restored and no test app was left running.

The first agent-desktop run outlasted its driver's 300-second wait; that attempt's
exit code is excluded. The final repeat used a longer observation window and
completed normally. A large ready-selector accessibility dump exceeded the tool's
1 MB RefMap limit; scoped `find` and screenshots supplied the relevant observations.
Semantic selection of a main-window dropdown option could not be confirmed by the
adapter. Historical Target reselection remains covered by the passing controlled
GUI regression, with no additional native selection claim. Failed-export/fallback,
timeout and cancellation cases are also controlled acceptance, not real failure
injection into the installed J-Link pack.

## Limits

Binary/script change, export failure, timeout, cancellation, publication failure
and missing-tool isolation are controlled tests. No actual J-Link installation
upgrade was performed. A controlled whitespace-only change to the exact export
script, executed by real Commander, produced a new validated fingerprint;
restoring the original script refreshed it back. Known-input matching does not detect every external
Commander database/configuration. Catalog readiness proves neither Target support
nor probe/firmware/RTT readiness. New hardware acceptance and a clean second Windows
host are outside this catalog change; existing lifecycle regressions remain in scope.
