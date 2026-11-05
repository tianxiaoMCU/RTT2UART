# H05 live firmware RTT teardown/restoration — 2026-11-03

Passed for source Bridge and the unchanged frozen EXE on A, SWD1000kHz,
J-Link7.54d/HHD COM1↔COM2, reset off. The approved fixture command
`ESC[H05:RTT-OFF]CRLF` acknowledges, echoes for3000 nominal firmware ms, removes
RTT ID/counts/buffer sizes for15000ms without RTT API calls, reinitializes both
rings, then emits `H05 RESUMED`. HSI time is not externally calibrated.
The1332-byte image SHA256 is
`8c018288b062fb381d4113b1e1967ed3cf96b8c1fab4807417a68b407abff345`.
[Fixture source/method](../../../tests/fixtures/stm32h750_rtt/README.md#command-driven-rtt-fault-variant).

[Evidence](./evidence.json) keeps build metadata, direct-cycle.json, source
on/off, EXE peer records and selected UIA states, six-cycle counters and rollback.
The same native session observed phase1/2/0; RTT-off began3.000s after ACK and
restoration17.969s after ACK. During off, Target remained accessible/running at
sample and actual ID/counts/sizes were zero. Cached native counts remained1/1,
but descriptors reported zero sizes and were rejected by production readiness.

Source recovery-on entered Reconnecting3.016s after ACK, discarded28 bytes,
stayed unready throughout off and recovered fresh echo. Recovery-off failed
at3.047s, stayed Failed through ACK+21s and required manual Start.
EXE UIA/PrintWindow showed the same recovery-on/off distinction;32 discards were
retained on recovery. [Recovered frame](./cycle-exe-recovered.png).
No outage marker replay was observed in the finite output window.

Six completed cycles gave command/off/resume6/6/6 and zero write errors.
restore-A.json verifies full128KiB restoration SHA256
`ff0be13233a1521526a6088f9f5a24b5a1b7dd3375a400b3e640c42953f80984`,
baseline echo; package-final.json confirms B unchanged and resource release.
No production change/rebuild was needed. This does not cover every firmware
failure that leaves apparently valid descriptors, or prove absence of brief
halt/reset. Duplicate screenshot-inspection retries were excluded from the
minimal retained set; no capture root cause or flag0 success was established.
Independent Standards/Spec reviews ended with0 remaining findings. Controllers
and excluded attempts remain in the [historical snapshot](../README.md).
