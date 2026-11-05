# H09 Existing Session native socket cancellation — 2026-11-03

The three corrected-marker source cases passed: Existing Session starting,
retry waiting and an active retry. [Evidence](./evidence.json) retains the full
existing-starting.json, existing-retry-wait.json and existing-retry-connect.json
records, including real connect delegate entry/return, state events and cleanup.

Actual Windows loopback TCP backlog pressure delayed socket connection; HHD
COM1↔COM2 supplied real serial traffic. No new J-Link owner/Target readiness is
inferred from this socket fixture. Cancellation blocked restart, fenced late
successful sockets without forwarding, cancelled waiting retries and released
the owned serial port while leaving the external listener usable.

No sleep, worker suspension or synthetic gate replaced the socket operation.
These short TCP cases do not demonstrate the4s Stop incomplete row. That row
and the frozen EXE matrix were completed in the
[2026-11-04 H09 record](../issue13-h09-2026-11-04/README.md).
Earlier pre-marker/preparation attempts are excluded and available in the
[historical snapshot](../README.md). Initial independent reviews ended with
0 remaining findings for their recorded partial scope.
