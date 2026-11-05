# H05 Target loss and partial readiness — 2026-11-03

Passed for recorded physical Target-access and partial-readiness cases on A,
with B and both USB devices connected. Common candidate/setup are in the
[integrated record](../../integration-acceptance.md).
[Evidence](./evidence.json) retains target-source.json/rtt-source.json, actual
RAM mutations, selected EXE UIA states, echo/marker and final resource records.

The operator disconnected only A SWCLK. Source and frozen EXE entered
Reconnecting with recovery on, observed21/25 discarded marker bytes respectively,
and recovered fresh echo after reconnection. Recovery off ended Failed and stayed
Failed after restoration, then manual restart passed. The USB presence of A/B
was checked independently; this was not a USB removal test.

During source partial restoration, SRAM down-count was held zero: Target access
alone did not produce Running; full two-direction RTT readiness did. A separate
source run mutated configured RTT counts and deliberately retired the session.
EXE first-start cases with only up, only down, or neither channel failed;
restoring full RTT did not auto-restart that failed startup. Manual Start passed.

These count-only mutations did not establish live firmware RTT disappearance
detection: native counts remained1/1 while actual buffers still had4096-byte
sizes. native-metadata-diagnostic.json retains this limitation. The subsequent
[command-driven firmware experiment](../issue13-rtt-cycle-2026-11-03/README.md)
supplies that separate runtime result. Do not reinterpret session retirement as
automatic runtime fault detection.

package-final.json verifies restored1/1 counts, both original888-byte images,
B counters65536/65536 and COM/probe release. Source trace/state/identity evidence
is preserved; preparation failures are excluded, accessible in the
[historical snapshot](../README.md). The accepted helper was9598e40; later replay
cleanup guards passed controlled checks without a hardware rerun. Final
independent Standards/Spec findings were0. Review and hardware are separate.
