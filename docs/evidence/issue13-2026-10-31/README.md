# Integrated baseline and real transfer — 2026-10-31 to 11-02

Passed for the recorded candidate, Windows10 build19045/x64, Python3.12.13,
J-Link7.54d and HHD COM1↔COM2/115200/8N1. COM13 was unused J-Link CDC.
This is historical acceptance, not a claim that hardware is currently connected.

[Evidence](./evidence.json) retains build-environment.json (source, dependencies,
companion and EXE hashes), environment.json, compilation exits, fixture build and
flash/readback, direct RTT load, actual source USB/Existing Session traffic,
endpoint recovery, physical USB recovery and Stop-during-retry records.
Use the original filenames as keys under `records`.

USB and paced Existing Session binary echo, manual restart, owned COM release,
USB probe reacquisition and continued external-owner echo after Existing Stop
passed. Existing endpoint loss/restoration discarded29 observed bytes; physical
USB recovery discarded24, retained the original probe and made no repeated
explicit reset. A separate retry Stop stayed Stopped after operator-confirmed
restoration and released resources.

The unpaced Existing Session burst failed; its original failed record and raw
socket control remain in evidence.json. Pacing one256-byte chunk until complete
echo passed. No sustained unpaced losslessness, exactly-once execution or total
loss accounting is claimed. The old cJTAG/SWD display discrepancy was not
reproduced by later committed-selection round trips; no cause or code fix is
claimed. Driver-repair troubleshooting, repeated logs and early preparation
failures are available in the historical snapshot described in the
[retention policy](../README.md), rather than tracked again here.

The initial885-byte firmware had an unaligned load image and was never flashed;
the corrected888-byte fixture was programmed/read back. The [fixture sources
and build instructions](../../../tests/fixtures/stm32h750_rtt/README.md) remain.
Original independent Standards/Spec reviews ended with0 remaining findings;
reviews inspected saved records and did not exercise hardware.
Later gates and the final approved closure are in the
[integrated record](../../integration-acceptance.md).
