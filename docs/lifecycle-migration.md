# RTT bridge lifecycle migration

This implements [#8](https://github.com/tianxiaoMCU/RTT2UART/issues/8) and
[#9](https://github.com/tianxiaoMCU/RTT2UART/issues/9), and
[#10](https://github.com/tianxiaoMCU/RTT2UART/issues/10), and
[#11](https://github.com/tianxiaoMCU/RTT2UART/issues/11) from
[parent specification #7](https://github.com/tianxiaoMCU/RTT2UART/issues/7).
[#12](https://github.com/tianxiaoMCU/RTT2UART/issues/12) adds settings compatibility
coverage and a reproducible Windows build. Its interactive package smoke passed
on 2026-10-30; hardware/release validation remains #13. See [Package smoke](./packaging-smoke.md).
The [integrated #13 acceptance record](./integration-acceptance.md) maps A01–A25
to current tests and records the candidate, final evidence and scope limits.

## Parent #7 integration — 2026-11-05

All implementation/acceptance slices #8–#13 are completed. The maintainer
authorized a single squash commit on master from development tip
`ce38a8fee2e0b27429907d05b73896f909ffbc24`, followed by parent #7 closeout.
The final acceptance is limited to the recorded setup and approved qualifications:
H07 live HHD driver-fault injection remains unexercised/non-blocking, H08/H09
retain their observation/native-call limits, and deployment passes the supplied
Windows11/J-Link7.54d dependency-isolation scope with CubeIDE/NI installed.
Bare Windows without development software is not claimed.

The [integrated record](./integration-acceptance.md) and
[compact evidence policy](./evidence/README.md) are authoritative for final
status. Dated results below retain earlier pending statements as history.
The original candidate EXE was not rebuilt by squash integration; a future
package build has its own identity and requires its own acceptance evidence.
Squash integration is not a release/tag or a resolution of unrelated #5.
The squash working tree passed 61/61 controlled tests, strict types for five
modules, dependency consistency and Python compilation. No hardware or packaged
GUI run was repeated for this integration; the recorded #13 scope is retained.

## Baseline and scope

- Initial migration baseline: `96609b324cd52a00ab15fddc8f4461e4404b744a`.
  Recovery extends #8 at `70e4fd428c55775c15739f8e4f5ba1fa1dc38e2a`.
  USB extends #9 at `4a3572757a1023bac2e830b9720de63113edacac`.
  USB recovery extends #10 at `052dcd1c5e70d6583b511b6b08230701f4324522`.
- Runtime requirements remain pylink_square 1.2.0, pyserial 3.5, and PySide6 /
  Addons / Essentials / shiboken6 6.6.1.
- Every Existing Session run uses `Bridge` in `rtt2uart.py`. Auto Reconnect is
  enabled by default and frozen from the GUI selection at Start. Disabling it
  gives terminal endpoint-loss behavior.
- USB now uses the same `Bridge` with an owned direct-RTT adapter. The old USB
  localhost backend and GUI running flag are removed. USB Auto Reconnect is
  optional and defaults off. Idle mode selection restores the mode default;
  the chosen policy stays fixed throughout the run.
- Saved settings and device selection retain their established behavior. The
  GUI still constructs its J-Link library object for device selection at startup.
  The Existing Session bridge never receives that object or performs external
  probe open/reset/stop/close operations.

Retain the source baselines for comparison in separate checkouts. Do not change
running application code underneath an active bridge.

## Public interface and ownership

`Bridge.start(BridgeConfig(...))` takes immutable serial, endpoint (default
`localhost:19021`), recovery, and optional `USBConfig` settings. With no USB
configuration it uses Existing Session and defaults recovery on; with USB it
defaults recovery off. `USBConfig` separates Target, interface, speed, optional
requested serial number, and explicit startup reset. It returns `Starting` promptly and
starts background work. `Endpoint connected — Target state unverified` permits
forwarding after both owned paths open; it never certifies firmware readiness
or command consumption.

`Bridge.snapshot` returns immutable state, reason, cleanup error, and
`discarded_bytes`, and `probe_serial_number`. USB publishes `Running` only after
serial and Target/RTT readiness; the serial number is the observed identity, not
just the requested setting. Neither ready state proves firmware execution.
`snapshot.can_start` is true only for `Stopped` or clean
`Failed`. A new Start resets the count. `Bridge.stop()` invalidates forwarding
and requests cleanup without blocking the GUI. Repeated Stop is safe.

One I/O worker owns serial acquisition, reads, writes, and close, and normal
endpoint forwarding. During recovery a temporary connector opens one replacement
endpoint, or closes the retired one, while that worker continues draining serial
input even if native close is slow. There is no second
serial reader, forwarding queue, or independently restarting timer. The connector
exits and is joined before transport ownership transfers again. Factories return
unopened resources registered for cleanup before open.

Startup failure is terminal even when recovery is enabled; it rolls back and
requires manual retry. Runtime EOF and socket read/write failures recover only
after prior readiness and when enabled. USB probe/Target/RTT loss uses the same
recovery path. Serial failure is always terminal.
Eligible recovery retains the original serial handle and frozen configuration.
USB recovery derives a configuration pinned to the initially observed serial
number with explicit startup reset disabled. It preserves Target/interface/speed,
repeats Target/RTT readiness and rejects any different probe identity before
forwarding. Only initial startup can perform the selected explicit reset.
Retry waits are **1, 2, 5, 5, ... seconds** with no attempt limit; attempt time is
additional. Confirmed recovery resets the schedule for a later outage.

The serial owner finishes/discards in-flight recovery reads and drains pending
input through an idle read before publishing readiness. No old serial read can
complete later on a second forwarding worker. Uncertain write tails are abandoned.
Stop during waiting, connect, or handoff prevents every later ready transition.
Late resources are cleaned up, without forcibly closing concurrently with open.

An observer joins the I/O worker before publishing `Stopped` or `Failed`.
User Stop ends in `Stopped`; terminal errors end in `Failed`, unless cleanup is
incomplete. Failed closes are retried only for unreleased resources. Cleanup
failure ends recovery and keeps `Stop incomplete` until release succeeds.
Restart cannot overlap a prior worker or connector. No destructor is required.

The GUI polls snapshots every 20 ms on its Qt event loop. Workers never touch
widgets. Configuration stays locked during active work and incomplete cleanup.
Window close and Escape request the same Stop and defer closure/settings save
until cleanup completes. Both modes use this same state presentation.

## Engineering deadlines

| Operation | Parameter | Behavior at limit |
| --- | --- | --- |
| USB RTT discovery | 3 s observation, 10 ms cancellable waits | Startup fails or a recovery attempt retries if channel-0 descriptors remain unavailable; native calls may exceed this deadline |
| Socket connect | 3 s timeout | Initial failure or another scheduled recovery attempt |
| Socket read/write | 10 ms timeout | Idle reads are normal; write timeout has possible partial delivery |
| Serial read | 10 ms | No bytes is idle |
| Serial write | 1 s | Terminal serial error on timeout |
| Write zero progress | 3 consecutive zero results, 10 ms cancellable waits | Endpoint recovery or terminal loss by policy; serial writes are terminal |
| Cleanup observation | 4 s from Stop/terminal error | `Stop incomplete`; restart remains prohibited |
| Failed close retry | 250 ms, or repeated Stop | Retry only unreleased resources |

These parameters do not forcibly interrupt OS/DLL calls or DNS resolution.
An operation may outlast them; cleanup continues after it returns. The observer
keeps the GUI responsive and restart disabled. Unresolved cleanup keeps the
application open rather than terminating native threads.

## Pinned USB dependency contract

Verified against the installed `pylink_square==1.2.0` sources:
`pylink/jlink.py`, `pylink/structs.py`, `pylink/enums.py`, and `pylink/jlock.py`.
The module performs no native calls from the GUI or cleanup observer. Initial
startup and forwarding run on the I/O owner. During recovery the connector owns
probe open/preparation or active-recovery close exclusively; it is joined
before any further transport operation or final cleanup. Same-object native operations remain serialized.

- `open(serial_no=...)` selects USB. After successful open, `serial_number` is an
  integer property. Missing, nonpositive, noninteger, or conflicting identity
  fails safely; selection never falls back to another probe.
- `set_tif()` must return true. `connect(target, speed=...)` explicitly supplies
  the configured speed instead of allowing its default `'auto'` to overwrite it.
  cJTAG is not in this version's interface enum and is rejected visibly.
- Explicit initial `reset(halt=False)` follows Target connect and is separate
  from reusable Target preparation. Native connect may itself reset/halt some
  Targets; absence of an explicit reset is not evidence of non-intrusion.
- `rtt_start()` begins processing. `target_connected()` and channel counts plus
  `rtt_get_buf_descriptor(0, up=True/False)` gate readiness. Descriptor index and
  direction must match, and `SizeOfBuffer` must be at least two bytes (a ring
  buffer must have room for payload). Discovery gets a bounded wait; runtime
  readiness loss triggers recovery when enabled, otherwise terminates the run.
  No firmware handshake is sent.
- `rtt_read(0, 1024)` returns a byte list; an empty list is idle. `rtt_write(0,
  list(data))` returns an accepted count. Short writes preserve order; uncertain
  tails are not replayed after errors. No USB TCP client is created.
- Native open/connect/close expose no cancellation parameters. Checks between
  native calls fence late completion; no concurrent close/reset interrupts them.
- The pinned wrapper increments `_open_refcount` only after open initialization
  completes, and decrements it before native close. Its `close()` can therefore
  silently do nothing after partial open or a failed native close. The localized
  cleanup adapter restores that guard only when `opened()` reports an open DLL,
  calls wrapper close sequentially, and verifies closure. It retains the probe
  selection lock across wrapper close and releases it explicitly, including when
  open failed before native acquisition. Descriptor closure and lockfile removal
  are tracked separately: pinned `JLock.release()` is not safely retryable after
  a deletion failure. Retries remove only the remaining owned lockfile, without
  closing its descriptor twice or deleting another process's unacquired lock.
  Failed release keeps Stop incomplete.
  These private-field adaptations are version-specific and must be revalidated
  on a dependency upgrade. The regression suite exercises the installed wrapper
  against controlled DLL/lock failures, not only an imitation of its API.
- An RTT-stop error can occur after probe loss. Verified probe closure still
  establishes release; a failed or unverifiable close blocks restart. Cleanup
  does not depend on garbage collection.

[SEGGER's RTT description](https://kb.segger.com/RTT) explains channel descriptors
and ring buffers. The installed pinned source above is authoritative for the
Python signatures; newer online API documentation is not a substitute.

## Byte handling and counter meaning

Healthy forwarding preserves raw byte values/order. The bridge adds no framing,
encoding conversion, line endings, readiness probes, or heartbeat commands.
Short writes complete in order on the same connection. Repeated zero progress
is bounded and cancellable.

`Observed discarded input` counts only bytes read during recovery and deliberately
not submitted for forwarding, including the final handoff drain. It is cumulative
for this run and remains visible after recovery and Stop. It excludes bytes lost
elsewhere and uncertain in-flight writes. It is **not** total end-to-end loss,
an acknowledgement, or proof of firmware execution. A partial/failed write may
already have reached or executed on the Target; its uncertain remainder is never
replayed across connections.

Serial applications, RTT servers, drivers, and firmware can have their own
buffers or retries. Application framing, resynchronization, and execution
semantics remain their responsibility. Exactly-once delivery is not guaranteed.

## Reproducible checks

Use a Python 3.12 x64 environment. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/check.py
```

The [shared entry point](../scripts/check.py) runs Git whitespace checks,
dependency consistency, retained-evidence checks, strict typechecking, Python
compilation and the complete unittest suite in order.
It uses the calling Python environment and the checkout root even when invoked
from another directory. The first failed step returns its nonzero exit code,
prints its captured output and prevents all subsequent checks from running.
Strict types cover the bridge, USB adapter, packaging/check scripts and the two
fixture Python tools. The legacy GUI is covered by compilation and Qt integration,
not repository-wide strict typing.

The [whitespace check](../scripts/check_whitespace.py) uses Git's own whitespace
rules and attributes. It checks both the working tree and index against
`EVIDENCE_BASE`, defaulting to `HEAD` locally; new files must be staged to be
included. CI supplies the existing PR/push baseline. An initial push's all-zero
baseline means the empty tree. Invalid or unavailable baselines fail. Errors
are retained in `whitespace.log` and stop later checks; files are never rewritten.

Evidence checks verify the file inventory, byte counts/hashes, duplicate content
and local Markdown destinations, and report evidence file/byte growth. See the
[retention rules and baseline options](./evidence/README.md#automated-checks).
They do not determine whether evidence is necessary or prove hardware behavior.

Each invocation saves separate step logs under ignored `build/checks/run-*/`.
Success prints a short status and log location; failure also prints the failing
step's output. Logs are temporary build output, not committed acceptance records.
The runner selects offscreen Qt only in child processes; the calling shell is
unchanged. Individual test modules can still be run directly during development.

[Windows CI](../.github/workflows/check.yml) installs `requirements-dev.txt` on
Windows Server 2022 / Python 3.12 x64 and invokes the same entry point for pushes,
pull requests and manual runs. Check logs are uploaded as temporary artifacts
with seven-day retention. No J-Link runtime, virtual COM driver, ARM compiler,
firmware operation or package build is required by these controlled checks.

Tests drive the confirmed public `start`/`stop`/`snapshot` seam. Controlled I/O
induces failures, partial writes, blocked connections/reads/close, and cleanup
failure. A manually advanced monotonic clock checks retries without real
1/2/5-second sleeps. Production socket tests exercise loopback transfer, EOF,
and reconnection. Qt tests use the real window/event loop and bridge with
controlled external I/O and an inert J-Link library boundary. They demonstrate
visible recovery/discards, new-only forwarding, locked controls, and Stop/window
close during a delayed retry. No hardware is required for these checks.

Automated results remain separate from hardware/release acceptance. Passing this
entry point is not a new probe/Target, transfer or packaged-GUI validation.
Historical hardware results and their limits are in the
[integrated acceptance record](./integration-acceptance.md); package checks are
recorded separately in [Package smoke](./packaging-smoke.md).

### Recorded automated baseline — #8, 2026-10-24

Windows 10 build 19045, CPython 3.12.13 (64-bit), pinned runtime packages above;
mypy 2.4.0 and types-pyserial 3.5.0.20260712. The #8 baseline passed 16 tests,
strict bridge typechecking, compilation, and `pip check`. Its two-axis review
had no remaining findings. This historical result does not certify #9 recovery.

### Recorded automated result — #9, 2026-10-24

- Same recorded Windows/CPython and pinned dependency environment as #8.
- Full discovery: **30 tests passed** (10 baseline bridge checks, 13 recovery
  checks including production loopback TCP, and 7 real Qt integration checks).
- Strict bridge typecheck, Python compilation, `pip check`, local Markdown link
  checks, and `git diff --check`: passed.
- Independent two-axis code review: **Standards 0, Spec 0** actionable findings.
- Hardware, real virtual COM pairs, USB migration, and packaged application:
  **not tested**; parent #7 hardware/release acceptance remains pending.

### Recorded automated result — #10, 2026-10-25

- Windows 10 build 19045, CPython 3.12.13 (64-bit); runtime dependencies remain
  pinned as above. No real J-Link DLL/probe/Target is used by the automated suite.
- Full discovery: **47 tests passed** (10 baseline bridge, 13 Existing Session
  recovery, 15 USB/pinned-dependency, and 9 real Qt integration checks).
- USB checks cover actual identity enforcement, initial reset and debug settings,
  channel readiness/discovery, raw bidirectional transfer, short/zero writes,
  terminal failures, delayed native cancellation, cleanup/restart exclusion,
  partial native open, and safe selection-lock deletion retries. The lock
  regressions use the installed pylink wrapper/lock with controlled boundaries.
- An initial default-discovery run exposed a native Qt crash; isolated Qt tests
  and package-qualified discovery passed. Moving the shared probe fixture out
  of the test module removes duplicate test-module imports. Default discovery
  then passed, including three further bounded reproducer runs. A deeper native
  root cause is not claimed from this observation.
- Strict typecheck for `rtt2uart.py` and `usb_transport.py`, Python compilation,
  dependency consistency, local Markdown links, and whitespace checks: passed.
- Running/Failed GUI renders were inspected offscreen with an explicitly loaded
  Segoe UI font (the offscreen platform initially had no fonts). This is a layout
  check, not an interactive Windows or packaged-app smoke test.
- Code review: Standards **0**, Spec **0** remaining actionable findings. The
  unsafe pinned-lock retry found in review was fixed and independently rechecked.
- USB Auto Reconnect remains off/unavailable; #11 adds recovery. Real Target/DLL
  behavior, connection-side reset/halt effects, virtual COM drivers, throughput,
  and packaged application validation remain pending under #13. Parent #7's
  hardware/release acceptance is not complete.


### Recorded automated result — #11, 2026-10-25

- Same Windows/CPython and pinned dependency environment as #10.
- Full discovery: **58 tests passed** (10 baseline bridge, 13 Existing Session
  recovery, 24 USB/pinned-dependency, and 11 real Qt integration checks).
- USB recovery tests cover the original probe versus a different observed probe,
  preserved settings, no repeated explicit reset, full Target/RTT readiness,
  repeated outages with 1/2/5-second scheduling, delayed native results, terminal
  serial failure, stale/in-flight input discard, no uncertain-tail replay,
  cancellation, cleanup failure, and restart exclusion.
- Review found that native close during active recovery could pause serial
  draining. A regression reproduced this before the fix; recovery open and close
  now both lend exclusive transport ownership while the serial worker drains.
  Delayed-close tests cover both initial retirement and failed-attempt cleanup.
- GUI tests demonstrate USB Reconnecting back to Running, visible discard counts,
  mode defaults, locked configuration, and responsive Stop/window close during
  delayed recovery. Reconnecting, Running, and Stop incomplete renders were
  inspected offscreen with Segoe UI loaded; this is not a packaged-app smoke test.
- Strict bridge/USB typecheck, Python compilation, dependency consistency,
  local Markdown links, and whitespace checks: passed.
- Independent code review after repairs: **Standards 0, Spec 0** remaining
  actionable findings. The Spec reviewer reran focused cleanup/cancellation tests.
- Actual two-probe/Target/DLL behavior, native connection reset/halt side effects,
  virtual COM drivers, throughput, and packaged application validation remain
  pending under #13. Settings/packaging compatibility is tracked by #12.

### Recorded compatibility result — #12, 2026-10-25

- Baseline `d656150042d6a2017510febbf6fa9ee8294af7a4` already includes #11.
  Full discovery: **61 tests passed**, including 14 Qt integration checks.
- Added a legacy six-key settings fixture with multi-Target history and serial
  selection; save/reopen preserves the format without persisting new fields.
  Re-selecting an existing history Target now updates the visible selection;
  cancelling or accepting an empty catalog choice leaves history unchanged.
- Qt coverage observes background lifecycle/discard label delivery on the GUI
  thread. The icon resource resolves. Existing dual-mode byte/recovery/locked
  controls and delayed-close checks continue to pass.
- Expanded repeated-window tests initially reproduced a native Qt access
  violation during event processing. Explicit fixture window destruction before
  replacement/teardown removed the observed failure; subsequent focused runs
  and full discovery passed. This is not proof of a deeper native root cause.
- Strict bridge/USB/build-script typechecking, compilation, dependency
  consistency, local Markdown links, and whitespace checks passed.
- Legacy mixed-parameter and duplicate USB lifecycle paths were already removed
  by earlier slices; only unused GUI imports were removed here. UI/resource
  sources and generated outputs are unchanged. Runtime dependency pins remain.
- Independent review: **Standards 0** actionable findings; **Spec 0** actionable
  code findings, with the package interactive acceptance explicitly incomplete.
- The reproducible Windows build succeeded, and the actual EXE loaded legacy
  settings and enforced single-instance behavior. See the exact environment,
  package hash, blocked interactive steps and rollback procedure in
  [Package smoke](./packaging-smoke.md). #12 stays open until that pending
  acceptance item passes; #13 hardware/release acceptance remains pending.

### Recorded package follow-up — #12, 2026-10-30

- Retested the exact recorded EXE using Windows UI Automation and inspected
  Win32 PrintWindow captures. Main GUI/icon/catalog rendering, idle mode controls
  and defaults, edited settings save/normal close/reopen, cancel/empty Target
  selection, and single-instance checks passed. No application code changed.
- UIA WindowPattern.Close exited both package processes; no forced termination
  was needed. Both idle modes closed normally, and reopening restored USB/off
  defaults with the saved Target/interface/speed/baud/COM selections intact.
- Full evidence and the Qt popup keyboard-confirmation method are in
  [Package smoke](./packaging-smoke.md#interactive-follow-up--12-2026-10-30).
  This completes the previously pending #12 GUI package acceptance, not #13's
  real-hardware/active-run/clean-host release gate. The earlier native capture
  tool failure is not claimed repaired.
