# STM32H750VB hardware echo fixture

This hardware-only fixture prepares issue #13's otherwise blank Target. It is
not production firmware or an automated substitute for the virtual COM tests.
The operator approved internal HSI and no other GPIO initialization. It relies
on a normal Target reset: HSI is left at its reset setting, caches and interrupts
are not enabled, and GPIO, external clocks, external memory and option bytes
are not configured.

The image starts at internal Flash `0x08000000`, limited to 128 KiB. Stack, data
and RTT use AXI SRAM `0x24000000..0x2407ffff`, matching the device catalog's work
RAM range. Reset copies data, zeroes BSS, relocates the vector table, initializes
RTT channel 0 and sends exactly `RTT2UART-H750-ECHO/1\r\n` once. Subsequent input
bytes are echoed unchanged, including NUL/0xff and line endings. There are no
commands with peripheral side effects, unsolicited periodic messages or resets.
The firmware waits for sufficient up-buffer space before consuming input.

`test_stats` exposes a signature (`0x48525454`), received/echoed byte counters
and loop iterations as four 32-bit words for debugger observation. These reset
on each boot, wrap naturally, and do not prove the absence of a brief halt or
reset. The counters are not part of the RTT protocol.

## Build without connecting hardware

Use the ARM GCC bin directory installed with STM32CubeIDE. Build from the
repository root:

```powershell
$gccBin = 'C:\ST\STM32CubeIDE_1.9.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.10.3-2021.10.win32_1.0.0.202111181127\tools\bin'
.\.venv\Scripts\python.exe tests/fixtures/stm32h750_rtt/build.py --toolchain $gccBin --rtt-zip 'C:\Program Files\SEGGER\JLink\Samples\RTT\SEGGER_RTT_V754d.zip'
```

The build uses the installed, hash-pinned SEGGER RTT 7.54d sources without
modifying their copyright/license headers. Only those sources are extracted
into ignored build output; no new compiler/runtime dependency is installed.
The project's own configuration is copied beside the sources in the vendor's
expected `Config/` layout. Outputs are `build/issue13-h750/rtt-echo.elf`, `.bin`,
`.map` and `firmware-build.json`, including compiler, source/image hashes,
symbol addresses and assert-based image checks. Build does not open a probe or
write Flash. Do not use Python `-O`, which disables these assertions.

## Hardware use

Use only the confirmed STM32H750VB test Target, SWD, 1000 kHz and the recorded
probe serial. Identify the attached Target and read/back up all 128 KiB before
programming. A blank chip or a recognized matching test fixture may be prepared
under the operator's explicit flashing instruction; preserve the original backup
in either case. Stop and reassess the scope if it contains unidentified data.
Program only the internal image, verify every image byte,
reset and run. Do not mass-erase, change protection/option bytes, configure
external Flash or use COM13 as a serial endpoint.

After reset, a direct RTT reader should first receive the banner. Drain it,
then send a known binary payload and compare its echo byte for byte. Record
image/probe identity, debug settings, actual bytes and timing, cleanup and any
native reset/halt effects. For RTT2UART acceptance, repeat through a genuine
virtual COM pair in both modes; a direct RTT echo alone does not pass that gate.
Only one application may own the probe at a time.

To repeat the bounded native-adapter load check after flashing (new output file
required), run from the repository root without Python `-O`:

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.stm32h750_rtt.smoke_usb --serial 601012352 --output build/issue13-h750/repeat-usb.json
```

This uses the production USB adapter with initial reset off. It drains/records
existing output, sends `bytes(range(256))` repeated 256 times in chunks of at
most 1024 bytes, and compares all 65,536 echoed bytes. A 1 ms host-loop sleep and
native readiness/descriptor calls are included in elapsed time. The 15 s loop
deadline is a test-harness limit, not a throughput requirement or a native-call
cancellation guarantee. The measured rate is not maximum link capacity.
The JSON records partial results/errors and checked cleanup as well as success.
This direct test deliberately does not open COM13 or any serial device.

References: [ST datasheet](https://www.st.com/resource/en/datasheet/stm32h750vb.pdf),
[SEGGER STM32H7 guidance](https://kb.segger.com/STM32H7), and
[SEGGER RTT](https://kb.segger.com/RTT). These references do not certify this
particular board or the bridge's complete acceptance matrix.

The [2026-11-03 two-probe record](../../../docs/evidence/issue13-two-probe-2026-11-03/README.md)
uses two distinct operator-identified STM32H750VBT6 chips with this same image.
B was erased; A already matched the fixture. It retains backup/read-back hashes,
the raw transient RTT-startup failure and later successful production-adapter
check, initial A connection failures and the operator power-sequence follow-up.
Those dated results do not replace the preconditions for a different bench.

## Command-driven RTT fault variant

Append `--fault-cycle` to the same build command to produce a separate image
under `build/issue13-h750-fault-cycle/`; the default image keeps its original
raw-echo behavior. The variant shares startup, memory layout and pinned vendor
sources. It adds only a polled core SysTick; no interrupts, GPIO, external clock
or option bytes are configured. Its banner is `RTT2UART-H750-FAULT/1\r\n`.

Send the exact 16-byte command `ESC [ H05:RTT-OFF ] CR LF`, without the shown
spaces: hex `1b5b4830353a5254542d4f46465d0d0a`. The parser handles fragmented
input; other bytes echo unchanged. An incomplete prefix is held until it
matches or mismatches, so arbitrary input ending in a partial prefix can wait.

1. Normal -> command recognized -> `H05 ACK delay=3000ms off=15000ms\r\n`.
2. Continue raw echo during a nominal 3000 ms delay; commands in this armed
   interval are echoed, not queued as another cycle.
3. Clear the RTT ID, set configured up/down counts and channel-0 buffer sizes
   to zero, then make **no RTT API calls** for a nominal 15000 ms. The CPU and
   debug access remain active. This is RTT registration/processing loss, not
   Target power/debug loss or an application-commanded reset.
4. Reinitialize both rings/control block, emit `H05 RESUMED\r\n`, resume normal
   operation and accept a later command. Buffered input is cleared on restore;
   host/native delayed writes are still uncertain and must be measured rather
   than claimed exactly-once or replay-free.

`fault_stats` (address in build manifest) contains eleven 32-bit words:
signature `0x48303546`, phase (0 normal / 1 acknowledged delay / 2 off),
milliseconds, accepted commands, off count, resume count, ACK time, off time,
resume time, pending down bytes discarded on resume, write-error count.
The original four `test_stats` words remain: RX counts include command bytes;
TX counts include ACK/resume messages but exclude the initial banner.
Counters are continuous across the cycle and reset on boot.

Timing assumes the reset-default 64 MHz HSI/core clock and polling more often
than every millisecond. Native halt/debug effects and HSI tolerance mean these
are firmware-time intervals, not independently calibrated wall-clock promises.
Record actual host ACK/off/resume times and phase snapshots. References:
[ST RM0433, HSI divider reset](https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743-753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf),
[Arm SysTick registers](https://arm-software.github.io/CMSIS_5/Core/html/structSysTick__Type.html).

Use only A (601012352) on the approved test bench, back up all Flash before
programming and verify the exact image/read-back. Preserve B and restore A's
original verified echo image after testing. A live SDK may keep cached RTT
descriptors even while this firmware is off; observe that outcome without
closing the native session or fabricating an RTT error.


## Internal H08 observer variant

Use --core-observer instead of --fault-cycle for a separate image in
`build/issue13-h750-core-observer/`. It includes the same H05 command cycle,
plus TIM2 at reset-default64MHz with debug freeze disabled, and TIM5 at the
same clock with debug freeze enabled. It enables no interrupts/GPIO or external clocks. The
normal build remains the identical888-byte raw-echo image.

A NOLOAD .noinit SRAM structure records warm boot entries and differential
free-running/debug-frozen timer intervals independently of host API tracing. A new nonzero31-bit
request at structure word4 arms a capture; word5 acknowledges it. Bit31
requests an early seal. States:0 idle,1 capturing,2 sealed,3 invalid/sealed.
An active capture is designed to retain data across warm resets (calibration
required) and seals automatically after
2880000000 timer ticks (nominal45s). Sealing freezes captured events and
seal-time boot/reset flags; read it only after the application releases its
probe. Global boots/reset_flags still update on a later boot, so use
sealed_boot/sealed_reset_flags for in-window attribution.
The boot count is SRAM retention evidence, not a power-loss-safe boot count.

Twenty-two header words precede64 events of8 words each; `bench.py` in the H08
evidence folder names and decodes the fields. Event kinds:0 arm,1 warm boot,
2 differential interval,3 invalid configuration/counter interval. The nominal
event threshold is6400ticks/100microseconds; this is not a calibrated minimum
detectable halt until actual positive controls have passed. Positive lag means
TIM2 advanced farther than TIM5; a debugger modifying counter or clock/freeze state
can invalidate attribution. Negative differential events are also retained.
Invalid settings/long ambiguous counter intervals seal the record rather
than silently repairing it during capture. Overflow is recorded.

Calibration must first demonstrate no false events at baseline, continuing
TIM2/stationary TIM5 during deliberate native halts, detected resumed events,
and a retained active capture/boot increment across a deliberate software
reset. Only then run production recovery with no extra observer connection.
Start before the initial connection/reset and read after automatic sealing;
correlate the independent record with a delegate-only API trace.

Limits: no external calibrated clock; HSI-derived times are nominal. No
measurement before observer initialization or during reset initialization;
very short pauses below the threshold remain unobserved. Settings changed
and restored entirely while halted can escape firmware sampling. Reset
entries and flags do not identify every physical reset cause; loss/corruption
of retained SRAM invalidates comparisons. This instrument changes the test
firmware's TIM2/TIM5 configuration and certifies only the recorded setup.
TIM2 wraps every67.109 nominal seconds. A pause spanning a whole wrap may
alias to a smaller modular interval; the long-delta guard cannot detect every
such case. Bound a claimed measurement window by independent host time below
one timer wrap and reject native operations exceeding that bound. Sealed
records alone do not prove this bound or exclude a halt while TIM2 is frozen.

Register definitions: [ST STM32H750 CMSIS header](https://github.com/STMicroelectronics/cmsis-device-h7/blob/master/Include/stm32h750xx.h),
[ST RM0433](https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743-753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf),
and [Arm Cortex-M7 TRM](https://documentation-service.arm.com/static/5e906dc68259fe2368e2abbe).

The first TIM2/DWT prototype calibrated in one session but became invalid
when J-Link disabled DWT during session release. Its failed source attempt
and original build are retained separately; that method is not accepted as
a H08 observation. The45s dual-timer variant avoids DWT and leaves enough
margin to keep the conservative host measurement bound below one67.109s
timer wrap, including arm/close/read overhead.
