# Integrated recovery and shutdown acceptance — #13

[Issue #13](https://github.com/tianxiaoMCU/RTT2UART/issues/13) passed for the
recorded setup and was closed as completed on2026-11-05, with the explicit
operator-approved deployment qualification. That #13 closure left parent#7 open.
Bare Windows without development software and real HHD driver-fault injection
were not tested; neither is claimed as a hardware/deployment pass.

On2026-11-05 the maintainer separately authorized squash integration of the
59 development commits into master and parent#7 closeout. The parent inherits
the same recorded qualifications, including H07's conditional live-driver
subcase. This changes neither the tested candidate nor the scope of the
historical hardware/deployment results. The earlier parent-unchanged statements
refer to the #13 execution, not a prohibition on this explicitly requested
parent closeout. Original development commit objects are local provenance;
see the evidence policy for squash/archive availability.

## Candidate and retained results

Tested source: `15a0b5398fd4f4e3ba9569b86ddc4aaf5b3603b3`.
Frozen EXE SHA256:
`54ba4201db67641607d272ddee062a31aa53ec882f5953dc24e2ea1f8a0bd02d`.
Production code/dependencies/EXE were unchanged during these acceptance rounds.
The firmware fixture is separate from the production application. #12 captures
belong to an older candidate and do not pass this one.

Evidence has been compacted under the [retention policy](./evidence/README.md).
Each dated record links one evidence.json containing selected original results,
source hashes, and explicit projection details. The [current artifact manifest](./evidence/issue13-artifacts.json)
replaces the per-attempt manifests. This is a documentation/evidence cleanup,
not a new test run; old pending fields describe their original capture dates.

| Gate / scope | Recorded result and necessary evidence |
| --- | --- |
| Candidate/build/environment; H01 | [Baseline](./evidence/issue13-2026-10-31/README.md): source/companion/EXE hashes, dependencies, successful compilation, fixture flash/readback and native library identity. |
| A01–A25 |61/61 controlled tests:10 bridge,13 Existing recovery,24 USB/pinned-wrapper,14 Qt. Final [suite log](./evidence/issue13-deployment-2026-11-05/controlled-suite.txt)61/61 in9.511s and [strict types](./evidence/issue13-deployment-2026-11-05/typecheck.txt)5 modules. These do not replace hardware rows. |
| H02/H03/H06/H10/H11 source paths | [Real COM/native record](./evidence/issue13-2026-10-31/README.md): USB and paced Existing Session exact binary echo, manual restart, external-owner preservation, endpoint loss/recovery/off policy, no observed marker replay and resource reacquisition. |
| H04 two probes; H10/H11 | [Source and frozen EXE](./evidence/issue13-two-probe-2026-11-03/README.md): A-only loss/restore while B available/unowned, A identity pinned, source24/EXE29 observed discards, B counters unchanged, retry Stop/normal close and resource release. |
| H05 Target/partial chain | [Physical SWCLK and partial RTT](./evidence/issue13-h05-2026-11-03/README.md): source/EXE recovery-on versus terminal-off, incomplete chain never Running, separate first-start readiness cases. |
| H05 runtime RTT-only fault | [Command-driven firmware](./evidence/issue13-rtt-cycle-2026-11-03/README.md): ACK, delay, live descriptor teardown, automatic firmware restoration, source/EXE on/off distinction and full Flash rollback. |
| H07 serial API errors | [Approved qualification](./evidence/issue13-h07-2026-11-03/README.md): required controlled terminal/cleanup/no-port-switch cases pass; live HHD6.2.0.1318 injection unexercised/non-blocking. |
| H08 independent observation | [Calibrated TIM2/TIM5](./evidence/issue13-h08-2026-11-03/README.md): one startup entry, source one explicit startup reset, approximately23ms recovery pause differences; no all-halt/electrical-reset absence claim. |
| H09 native cancellation | [Real IsOpen and12 EXE cases](./evidence/issue13-h09-2026-11-04/README.md):13.141s native call spans Stop, Stop incomplete4.016s after request, restart blocked/COM retained until natural cleanup; both modes waiting/active cancellation and close/Escape. |
| H12 active/local GUI; H13 traffic | [UIA/PrintWindow record](./evidence/issue13-gui-2026-11-02/README.md): settings/history/defaults/selector, actual USB/Existing recovery/normal active close,196 exact256-byte chunks; interrupted final prefix separately accounted. |
| H12 independent manual host | [Operator receipt](./evidence/issue13-independent-host-2026-11-03/README.md): Windows11/J-Link7.52b idle GUI only; developer tools present; transitions partly operator attestation. |
| H12 final deployment; closure | [SSH7.54d record](./evidence/issue13-deployment-2026-11-05/README.md):46 GUI assertions, exact settings/exits, two125-module snapshots/32 payload matches each, cleanup and literal operator approval/closed readback. CubeIDE/NI remain installed; finite dependency isolation only. |

## Recorded hardware setup

Windows10 x64/build19045, CPython3.12.13, pylink-square1.2.0, pyserial3.5,
PySide6/Addons/Essentials/shiboken6 6.6.1, J-Link7.54d. Build:
PyInstaller6.22.3/hooks-contrib2026.9. Exact hashes are in baseline evidence.json.
A J-Link PLUS601012352/HW11.00/V11 Mar15 2023, H750 UID
`003E0037 3030510D 35333339`; B59400616/HW9.40/V9 May7 2021, H750 UID
`00330045 30395104 39303838`. Both operator-identified STM32H750VBT6,
IDCODE0x20036450/128KiB Flash, SWD1000kHz/reference about3.28V. A NRST unconnected;
B NRST wiring and board/supply topology not supplied. Positive voltage does
not certify that topology or rule out back-power.

HHD tool6.03.00.1321/driver6.2.0.1318/oem2.inf, COM1↔COM2,115200/8N1/no flow
control. Source ownsCOM1/peerCOM2; EXE ownsCOM2/peerCOM1. COM13 is J-Link CDC,
unused. A/B normal firmware uses internal HSI, no other GPIO,888-byte echo image
SHA256 `822bbeabbaba6f200c7da0fcfa3ee59b09a38a102675e726d0b5c8b46196b1fa`.
Only approved known A firmware variants were used for H05/H08/H09. Full original
128KiB Flash was restored/read back, B image/counters checked, owners released.
[Reusable fixture, safe build/flash prerequisites and variants](../tests/fixtures/stm32h750_rtt/README.md).

Existing Session uses only the separately prepared test external JLinkGDBServerCL
owner at localhost:19021 for RTT traffic. H09's TCP backlog fixture tests actual
socket cancellation separately and does not prove Target readiness. Remote
Nov5 COM37 selection is not a live-transfer acceptance result.

## Automated matrix

These are controlled behavioral results, not physical hardware passes. B, R, U,
and G refer to [bridge](../tests/test_bridge.py),
[Existing Session recovery](../tests/test_recovery.py),
[USB/pinned-wrapper](../tests/test_usb.py), and
[Qt GUI](../tests/test_main_window.py) tests. The links identify representative
assertions; the full run includes every test in all four modules. Loopback TCP
tests use real sockets but controlled serial I/O. USB tests replace native I/O;
the pinned-wrapper tests exercise installed pylink 1.2.0 with controlled DLL/lock
boundaries. GUI tests run the real Qt event loop offscreen on Windows with
controlled external I/O; they do not exercise the native Windows Qt platform.
The confirmed public seam remains `Bridge.start / stop / snapshot`.

| ID | Required behavior | Representative test source |
| --- | --- | --- |
| A01 | Responsive Start and mode-specific readiness | [B: asynchronous start](../tests/test_bridge.py#L37), [G: both modes](../tests/test_main_window.py#L74), [G: USB](../tests/test_main_window.py#L137) |
| A02 | Acquisition failure rolls back and gates manual restart | [B: serial/endpoint](../tests/test_bridge.py#L95), [U: every preparation stage](../tests/test_usb.py#L469) |
| A03 | Failed first startup never becomes automatic recovery | [R: initial failure](../tests/test_recovery.py#L111), [U: enabled recovery](../tests/test_usb.py#L309) |
| A04 | Capture actual USB identity and pin recovery | [U: identity and frozen settings](../tests/test_usb.py#L79) |
| A05 | Reject the other probe before connecting or forwarding | [U: alternate identity](../tests/test_usb.py#L131) |
| A06 | Missing/invalid/conflicting identity fails safely | [U: identity validation](../tests/test_usb.py#L375) |
| A07 | Target and both RTT directions gate USB Running | [U: startup discovery](../tests/test_usb.py#L451), [U: recovery readiness](../tests/test_usb.py#L193), [U: descriptors](../tests/test_usb.py#L486) |
| A08 | Recovery preserves debug settings, without explicit reset | [U: reset separation](../tests/test_usb.py#L79) |
| A09 | Existing Session shows Target unverified and leaves external probe alone | [G: ready text and forbidden probe calls](../tests/test_main_window.py#L74) |
| A10 | Transport loss recovers only when enabled | [B: disabled recovery](../tests/test_bridge.py#L115), [R: EOF recovery](../tests/test_recovery.py#L58), [U: loss](../tests/test_usb.py#L131), [U: terminal policy](../tests/test_usb.py#L506) |
| A11 | Retry waits 1/2/5/5, with schedule reset after recovery | [R: schedule](../tests/test_recovery.py#L80), [U: schedule](../tests/test_usb.py#L131) |
| A12 | Stop fences waiting and delayed attempts/readiness | [R: wait](../tests/test_recovery.py#L121), [R: connect](../tests/test_recovery.py#L132), [U: native stages](../tests/test_usb.py#L221) |
| A13 | Blocked native work keeps GUI responsive and restart inhibited | [G: USB Stop incomplete](../tests/test_main_window.py#L202), [G: startup close](../tests/test_main_window.py#L234) |
| A14 | Late completion cleans up without resurrecting a run | [B: late connection](../tests/test_bridge.py#L63), [U: late startup](../tests/test_usb.py#L391) |
| A15 | Repeated Stop/window close waits for safe cleanup | [G: Existing Session close](../tests/test_main_window.py#L285), [G: USB close](../tests/test_main_window.py#L202), [G: Escape](../tests/test_main_window.py#L308) |
| A16 | Failed cleanup blocks clean states and restart until release | [B: close failure](../tests/test_bridge.py#L80), [R: failed retirement](../tests/test_recovery.py#L257), [U: recovery cleanup](../tests/test_usb.py#L287) |
| A17 | Serial failures remain terminal | [B: normal failures](../tests/test_bridge.py#L115), [R: wait/connect](../tests/test_recovery.py#L230), [U: recovery policy](../tests/test_usb.py#L309) |
| A18 | Drain/count input while waiting, opening and closing in recovery | [R: delayed connect](../tests/test_recovery.py#L58), [U: delayed native close](../tests/test_usb.py#L253), [G: visible counts](../tests/test_main_window.py#L164) |
| A19 | Stale queued/in-flight reads never enter restored transport | [R: handoff drain](../tests/test_recovery.py#L207), [U: in-flight read](../tests/test_usb.py#L168) |
| A20 | Uncertain tails never replay or inflate definite discards | [R: partial send](../tests/test_recovery.py#L164), [U: partial send](../tests/test_usb.py#L344) |
| A21 | Short writes preserve order; zero progress is bounded | [B: both directions](../tests/test_bridge.py#L138), [R: short writes](../tests/test_recovery.py#L156), [R: zero progress](../tests/test_recovery.py#L180), [U: writes](../tests/test_usb.py#L532) |
| A22 | Raw bidirectional bytes without extra framing/messages | [B: real TCP](../tests/test_bridge.py#L178), [U: owned USB](../tests/test_usb.py#L54), [G: transfer](../tests/test_main_window.py#L74) |
| A23 | Mode defaults and frozen/locked active configuration | [B: frozen config](../tests/test_bridge.py#L37), [G: defaults and locked recovery](../tests/test_main_window.py#L164) |
| A24 | GUI event-loop delivery of state/discards | [G: GUI thread](../tests/test_main_window.py#L376) |
| A25 | Legacy six-key settings/history survive save/reopen | [G: history reselection](../tests/test_main_window.py#L336), [G: round trip](../tests/test_main_window.py#L397), [G: Cancel/empty OK](../tests/test_main_window.py#L362) |

### Repeat the automated and build checks

Create a separate checkout at the recorded revision, or at the replacement
candidate revision when validating a change. Use the recorded dependency pins
and Python architecture; installing them is not itself a compatibility pass.
From that checkout in PowerShell (substitute the actual interpreter path):

```powershell
$pythonExe = 'D:\codex\RTT2UART\.venv\Scripts\python.exe'
git rev-parse HEAD
git status --porcelain=v1
& $pythonExe -m pip check
& $pythonExe -X faulthandler -m unittest tests.test_main_window -v
& $pythonExe -m mypy --strict rtt2uart.py usb_transport.py scripts/package_windows.py
& $pythonExe -m compileall -q rtt2uart.py usb_transport.py main_window.py scripts tests
& $pythonExe -X faulthandler -m unittest discover -s tests -v
& $pythonExe scripts/package_windows.py
```

Capture each command's output and exit code. In this run the parent process had
`QT_QPA_PLATFORM` unset; the GUI fixture sets it to `offscreen` before creating
the Qt application. Unset is not evidence that the native Windows Qt platform
was tested. Clear `QT_QPA_PLATFORM` before an interactive package launch.
Strict types cover the three named modules, not the entire
legacy GUI. A replacement build gets a new manifest/hash and requires its own
package and hardware results. Do not combine passing rows from different runtime
source hashes to declare a release pass.

## Hardware and package matrix

Record exact candidate, configuration, fault method, observed states/bytes and
owned-resource cleanup. Retain decisive evidence under the policy above; keep
full temporary output in ignored build storage while diagnosing failures.

| ID | Reproducible procedure | Required observation/evidence |
| --- | --- | --- |
| H01 | Confirm topology above; inventory both probes and Targets. Use a writable copy of the candidate with a disposable legacy settings fixture. Account for startup's serial-port scan. | Exact identities/firmware/driver/settings, candidate and companion hashes; no operator settings overwritten. |
| H02 | USB: select confirmed Target/interface/speed and bridge-side COM; observe Auto Reconnect off initially. Start, then exchange the agreed safe traffic separately in each direction. Stop, enable recovery and repeat. | Starting then Running with actual probe A serial; exact TX/RX byte values/order, no extra bytes; editable idle versus locked active controls. |
| H03 | Existing Session: start the known external owner, select this mode, confirm Auto Reconnect on. Exchange the same safe traffic both ways. | Starting then Endpoint connected with Target state unverified; exact bytes/order; record external owner identity and evidence it remains in control. |
| H04 | With both probes attached and their Targets observed independently, start on A. Disconnect only A, send an agreed harmless uniquely identifiable outage marker, then restore A while B remains present. Repeat an outage. | Reconnecting retains A identity; no connect/traffic to B, no false Running; restoration uses A; observed discard count changes; later outage starts a fresh retry schedule. Retain B-side observation, not just the GUI label. |
| H05 | Separately remove A, make Target A unavailable, and make its RTT channel unavailable, restoring only the probe/partial chain before restoring full readiness. Use a test fixture/firmware procedure agreed for this Target. Repeat transport loss with recovery off. | USB remains unready for partial restoration; enabled recovery versus terminal failure is distinct. Record each fault independently rather than treating probe removal as every fault. |
| H06 | Separately close the existing TCP connection/listener through its owning application; restore it. Repeat with recovery off and with the endpoint available while Target readiness is not independently established. | Enabled endpoint recovery versus terminal failure; recovered text still says Target unverified. Endpoint availability alone never establishes firmware readiness. Record how the peer socket was actually closed. |
| H07 | Required: controlled serial API error cases in USB and Existing Session during forwarding and recovery. Conditional: repeat with a real driver fault when the named virtual driver provides a reproducible supported method. | After owned cleanup, terminal Failed even with recovery enabled; no serial-port switch or automatic reopen. Preserve Stopping/Stop incomplete while cleanup is blocked. Required controlled coverage passes (A17); live HHD6.2.0.1318 injection is unexercised/non-blocking, not a hardware Pass. |
| H08 | With initial reset deliberately selected, observe startup and USB recovery independently. For the recorded internal method, calibrate TIM2/TIM5 and warm-reset retention, arm before the connection, seal before readback, and bound host time below timer wrap. | Pass for recorded source/EXE setup: one startup entry, no repeated explicit source reset, approximately23ms pause differences on native reconnections. Retain method/initialization/threshold/clock/freeze limitations; no absence claim for every halt or electrical reset. A boot counter alone is insufficient. |
| H09 | In both modes Stop during a retry wait and during a demonstrably active attempt. Use a known reproducible slow-native-call fixture if available; then release it. Also request close/Escape during starting/recovery. | No late readiness/forwarding/restart; responsive Stopping, then Stop incomplete after the 4 s observation deadline if still blocked; restart disabled until actual cleanup. Record whether a real blocked call was achieved; controlled tests do not fill that native row. |
| H10 | Send distinct agreed pre-outage, during-outage and post-recovery markers. Keep application retries disabled/recorded. Inspect Target input logs after full restoration in both modes. | Visible observed-discard delta and no bridge-driven replay of outage input; post-recovery traffic works. Record sent/observed bytes and external buffering. Counts describe observed discards, not total loss or exactly-once execution. |
| H11 | After Stop/normal close, acquire the same owned COM/probe with a suitable independent tool, release that tool, and restart RTT2UART. In Existing Session verify the external owner remains usable before/after bridge close. | Process exit, released serial/probe locks, no late worker restart; external session intact. An idle window close does not prove active-resource cleanup. |
| H12 | On this exact EXE perform the [packaged interactive checklist](./packaging-smoke.md#packaged-interactive-checklist), including settings/history, selector Cancel/empty OK, both defaults, second instance, save/normal close/reopen, state text and active recovery/Stop responsiveness. | Screenshots plus read-back values and actual process exits. Separate idle GUI rows from hardware-dependent active rows. Record deployment files and working directory. Repeat on a separate Windows setup without development-environment dependencies before claiming that scope. |
| H13 | On the supported direct-RTT use case, exchange agreed payloads for a recorded interval and operate GUI/Stop during traffic. Measure at named sender/receiver points. | Per-direction sent/received byte totals and duration, observed bytes/s, ordering/loss observations and GUI/Stop response timing. Record payload, load and timing method; no invented numeric pass target or unmeasured latency claim. |

If a required native stall, second probe, independent reset/halt measurement
or separate host cannot be exercised, keep that subcase pending with its
prerequisite. Apply the explicit H07 qualification to virtual-port fault
injection; it does not exempt other required rows. Available equipment alone
does not pass a test.
Do not force-kill native threads or silently fall back from USB to a localhost
listener. A Stop incomplete run must resolve before the same resources are
reused. Keep failed artifacts/logs in ignored build storage for diagnosis; retain unresolved limitations in the summary.

## Gate decision and rollback

The required rows passed within their recorded scope and explicit qualifications.
The Nov5 approval and closed/completed tracker readback are retained in
[deployment evidence.json](./evidence/issue13-deployment-2026-11-05/evidence.json)
under gate-approval.json and tracker-readback.json. No issue is changed by this
compaction. No code push, PR merge, release or tag is implied by issue closure.

H07 live-driver injection remains unexercised/non-blocking only for this named
virtual driver; reassess if driver/version or supported injection changes.
H08 has timer/initialization/reset-sensitivity limits. H09 directly traces source
DLL timing, while EXE native entry is not hooked. Native workers were not killed.
No finite no-replay observation establishes total loss accounting or exactly-once
execution. The failed unpaced Existing burst remains a measured limitation;
paced echo does not establish unlimited throughput.

Original independent Standards/Spec reviews for the hardware slices ended with
0 remaining findings. Nov5 deployment had independent Standards0; independent
Spec was unavailable due quota, and its primary-agent scope check is separate.
These are historical reviews, not a new review of this compaction. Review does
not execute or substitute for hardware acceptance. Raw rejected attempts and
controllers remain retrievable at the fixed pre-compaction Git revision.

The [package rollback procedure](./packaging-smoke.md#baseline-and-rollback)
retains pre-#12 `d656150042d6a2017510febbf6fa9ee8294af7a4` and pre-lifecycle
`96609b324cd52a00ab15fddc8f4461e4404b744a` source references. Stop/close after
cleanup, back up deployment/settings, and restore a separately retained tested
deployment. Historical source commits are not certified rollback binaries.
