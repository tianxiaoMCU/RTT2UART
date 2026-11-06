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
failing-then-passing regression test. Full shared checks remain to be recorded.

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

Build and native Windows GUI checks pending.

## Limits

Binary/script change, export failure, timeout, cancellation, publication failure
and missing-tool isolation are controlled tests. No actual J-Link installation
upgrade was performed. Known-input matching does not detect every external
Commander database/configuration. Catalog readiness proves neither Target support
nor probe/firmware/RTT readiness. New hardware acceptance and a clean second Windows
host are outside this catalog change; existing lifecycle regressions remain in scope.
