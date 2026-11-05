# H07 serial failure qualification — 2026-11-03

Mandatory controlled serial-error coverage passed in USB and Existing Session,
during normal forwarding and recovery. After owned cleanup, errors terminate
Failed even with reconnect enabled; no alternate port or automatic reopen.
Blocked cleanup still requires Stopping/Stop incomplete and H09 handling.

The operator explicitly accepted this gate adjustment. Conditional real-driver
fault injection is **unexercised, non-blocking only for recorded HHD6.2.0.1318
COM1↔COM2**. No real-driver error pass is claimed. Removing the HHD bridge did
not invalidate already-open handles, so it was not a valid fault injection.
No physical serial adapter was available or required for this virtual-port use.
Reassess this qualification for another driver/version or when a supported
repeatable injection method exists; other gates remain required.

[Evidence](./evidence.json) retains gate-qualification.json (approval, scope and
61/61 qualification rerun), final-checks.json (actual pair/driver/restoration
checks) and cleanup-controlled-checks.json (six harness cleanup cases, no
hardware). Historical `pending` fields predate approval and are not current
status. Product serial API error cases remain in the A17 tests linked by the
[integrated matrix](../../integration-acceptance.md#automated-matrix).
Independent Standards/Spec review ended with0 remaining findings. Repeated
unsuccessful driver-injection logs/controllers are in the
[historical snapshot](../README.md), not additional passing hardware evidence.
