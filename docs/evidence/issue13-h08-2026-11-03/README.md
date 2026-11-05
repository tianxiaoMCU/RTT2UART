# H08 independent internal reset/halt observation — 2026-11-03

Passed for this internal method on the recorded A/Windows10/J-Link7.54d setup.
Recovery caused approximately23ms pause differences; uninterrupted execution is
not claimed. No external instrument or safe GPIO was available. The2144-byte
HSI-only observer image SHA256 is
`63275bdda185a6da2e53192d8c96d7fd33b1519ae5a15ed960a142ccb4af9a00`.
[Fixture method/build](../../../tests/fixtures/stm32h750_rtt/README.md#internal-h08-observer-variant).

TIM2 runs during debug halt, TIM5 freezes through DBGMCU_APB1LFZ1 bit3.
Nominal64MHz32-bit timers record differential intervals at6400ticks/100us;
NOLOAD SRAM retains startup entries across tested warm resets. A45s capture
seals immutable in-window boot/reset/events. An independent session arms and
closes before application ownership, then reads only after sealing and normal
application cleanup. Host bounds57.453s/source and60.9525s/EXE are below67.109s
timer wrap. No observer shared the live bridge probe.

[Evidence](./evidence.json): dual-calibration.json retains baseline, three
positive halt controls, warm-reset and reset-after-seal controls. Baseline
max lag0.140625us/lead0.015625us, no event/overflow/invalid configuration.
Observed halt controls26.373/34.717/74.415ms include native overhead;26.373ms is
the shortest demonstrated control, not a calibrated100us detection floor.
Software reset increments retained startup count; post-seal reset changes
global fields but leaves sealed fields/events unchanged.

source.json retains the delegate-only native trace and sealed record:
one startup reset, four connects (three recovery), one startup entry3→4;
initial pause22.799ms, recovery23.414/22.973/23.595ms. gui-observer.json/gui.json
record one startup entry5→6, initial23.159ms, recovery23.262/22.641/24.309ms.
Both captures sealed valid, zero dropped/invalid samples. Source/EXE discarded
24/32 observed bytes and fresh echo passed; gui-peer.json corroborates traffic.

Full original128KiB Flash rollback and baseline echo passed; package-final.json
confirms original A/B images, unchanged B counters and resource release.
TIM5 freeze bit returned to reset default, but the prior debug-register value
was not recorded; exact original register/SRAM restoration is not claimed.
The rejected DWT prototype became invalid after J-Link disabled DWT on release;
GUI preparation/controller failures are excluded, available via the
[historical snapshot](../README.md). They are not passing observations.

Limits: no calibrated external timebase/electrical NRST measurement; no capture
before or inside reset initialization; startup counts can miss resets bypassing
the handler. Clock/freeze/counter manipulation while halted can escape sampling;
below-threshold and sub-ms sensitivity are not independently calibrated.
Final independent Standards/Spec findings were0; neither reviewer ran hardware.
