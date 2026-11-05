# H09 real native blocking and safe cancellation — 2026-11-04

Passed for source and the frozen EXE on Windows10/build19045, J-Link7.54d,
HHD6.2.0.1318 COM1↔COM2 and A601012352/H750. Reset off;10kHz for slow startup,
1000kHz for recovery. B59400616 was never selected by Bridge.
[Evidence](./evidence.json) contains accepted source cases, all12 GUI case
results, real peer records, rollback/resource checks and historical final checks.

Source tracer records/delegates actual ctypes DLL entry/return; only the observer
persists trace files. There was no inserted sleep/Event gate, suspended worker
or forced native close. Slow work was `JLINKARM_IsOpen`, not GETNUMBUF; SDK internal
wait attribution is unknown. Source-starting-final.json keeps all native calls:
selected call45 took13.141s across Stop; Stop incomplete observed4.016s after Stop,
restart rejected, COM1 retained. Natural cleanup reached Stopped13.453s after
Stop, serial reacquired, no late native restart.

USB retry-wait-2 retains retirement before Stop, only initial OpenEx,0.016s
cleanup. USB retry-connect-3 retains recovery-worker OpenEx spanning Stop,
0.078s delegate/cleanup. Both verify firmware ACK, fresh baseline and no late
restart through command+22s. Repeated IsOpen/RTT polling is replaced by exact
name counts; every lifecycle call and selected pending call retains its original
index/timing. Original full arrays remain in Git history.
The [three earlier source TCP cases](../issue13-h09-2026-11-03/README.md)
cover Existing Session waiting/active connection.

| Frozen EXE cases | Recorded observation |
| --- | --- |
| USB starting Stop / close / Escape | Stop incomplete4.239/4.122/4.069s after request; restart button disabled and COM2 owned. Stop eventually Stopped; close/Escape defer exit until natural cleanup (11.820/12.036s). |
| USB recovery Stop / close / Escape | Real command-driven RTT loss, Reconnecting, cancellation, no restart through firmware restore. Stop0.259s; close/Escape exit0 in0.788/0.786s. |
| Existing starting close / Escape | EXE-owned SynSent before request; Stopping; late connect fenced and socket EOF, no forwarding. |
| Existing active retry Stop / close / Escape | Real COM↔TCP baseline and endpoint loss; SynSent during cancellation, late socket EOF, listener still usable after cleanup. |
| Existing retry-wait Stop | No active connection at request, no later retry, Stopped and normal exit. |

All12 GUI cases exit0 and reacquire serial. Native UIA/PrintWindow verified
states; [representative Stop incomplete frame](./gui-starting-stop-incomplete.png).
Repeated unchanged state polls are omitted; first/last samples of every state
plateau remain. No DLL hook was injected into the EXE, so its exact native entry
and recovery phase are not traced; direct source timing supplies that evidence.
TCP cases use a real local fixture, not a verified Target, and its3s timeout
does not independently prove4s blocking. Host timings include UIA/poll overhead.

The1332-byte RTT-off fixture was programmed only onto known A, then full128KiB
Flash restored exactly to SHA256
`ff0be13233a1521526a6088f9f5a24b5a1b7dd3375a400b3e640c42953f80984`.
post-cleanup.json verifies baseline echo, manual Bridge restart/Stop, both COMs
and probes released, both original images and B65536/65536 counters unchanged.
No native worker/process was force-killed.

Excluded attempts missed the chosen call, hit tracer file I/O errors or failed
serial baselines; they are not hardware passes. Controllers/diagnostics remain
recoverable through the [retention policy](../README.md). Later replay guards
require retirement before Stop and persist evidence even if peer close fails;
controlled guard checks are not hardware reruns. Final independent review at
893a971 against abb94cd ended Standards0/Spec0. Historical final-check fields
predate deployment closure; current status is in the
[integrated record](../../integration-acceptance.md).
