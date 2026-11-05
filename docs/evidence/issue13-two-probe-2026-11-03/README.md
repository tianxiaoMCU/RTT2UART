# Two-probe exclusion — 2026-11-03

Passed for A-primary/B-available, in source Bridge and the same frozen EXE.
A: J-Link PLUS601012352, HW11.00/V11 Mar15 2023, H750 UID
`003E0037 3030510D 35333339`. B:59400616, HW9.40/V9 May7 2021, H750 UID
`00330045 30395104 39303838`. Both report IDCODE0x20036450/128KiB Flash.
SWD1000kHz/J-Link7.54d; A NRST unconnected, B NRST wiring unspecified.
Both verified888-byte minimal HSI echo images; no other GPIO initialized.

[Evidence](./evidence.json): flash-A-after-power-cycle.json, flash-B.json and
B-production-smoke.json preserve preparation. B's immediate RTT discovery
failed after successful programming/readback; its later65,536-byte exact echo
passed. A initially failed to connect, then connected after operator power/USB
sequencing. The isolated cause is unknown; an unconnected probe reset-input
reading does not establish MCU NRST voltage. Full Flash backups stay ignored.

two-probe-source-observed.json retains the accepted delegate-only trace.
B's observer was closed during forwarding/outage/recovery, so no B ownership
lock prevented fallback. Only A USB was unplugged, leaving B available. All11
recorded open requests named A; successful connect/reset/write identities were
A; reset count stayed1 (initial startup).24 outage bytes were observed discarded.
Restoration recovered A/fresh echo. A second loss followed by Stop reached
Stopped in0.034s; operator-confirmed restoration caused no late restart.

The EXE used explicit A/reset off/reconnect on. Its
[Reconnecting frame](./package-two-reconnecting.png) and retained UIA state show
29 discards while only B remained. Recovery used A, count29 persisted and fresh
echo passed. package-B-before.json/package-two-final.json independently show
B RX/echo65536/65536 unchanged. Active normal close released COM/probe.

No observed marker replay is a finite workload result; no exactly-once or
all-duration reset/halt exclusion follows. Reverse roles/all hardware combinations
were not tested. Standards/Spec independent reviews ended with0 remaining
findings. Original troubleshooting/controllers are recoverable through the
[retention policy](../README.md).
