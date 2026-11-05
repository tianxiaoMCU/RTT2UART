# Getting started

[Project overview](../README.md) | [Development](./development.md) | [Architecture](./architecture.md) | [Glossary](../GLOSSARY.md)

This guide walks an embedded developer through the Windows workflow: connect a
target through a USB J-Link probe, receive RTT output in a serial application,
and send data back to firmware that handles RTT input.

## Before you begin

Prepare the following:

| Item | What you need |
| --- | --- |
| Windows host | A writable application directory and permission to install the required probe and virtual serial port drivers |
| RTT2UART | The extracted release package, or a source checkout prepared using the [development guide](./development.md#run-from-source) |
| J-Link software | A discoverable J-Link runtime library and J-Link Commander (`JLink.exe`); installing Python dependencies alone does not provide them |
| Probe and target | A USB J-Link connection to the correct target debug interface, with target power and wiring already checked |
| Target firmware | Working RTT output; an RTT input handler is also required to test host-to-target traffic |
| Virtual serial ports | A connected virtual COM port pair, such as COM4 and COM5 |
| Serial application | A terminal or existing tool that can open the other endpoint of that pair |

RTT2UART does not install target firmware or configure its RTT buffers. Confirm
the firmware's RTT setup using your normal J-Link workflow before using the
bridge. USB uses direct RTT channel 0 on its owned probe. Existing Session needs
a working local RTT TCP endpoint at `localhost:19021`. There is no control for
selecting another RTT channel or control-block address. Current-source USB
behavior is covered by automated tests; real Target and package validation
remain pending, and older release packages may behave differently.

## 1. Prepare the application directory

Download the Windows ZIP from
[GitHub Releases](https://github.com/tianxiaoMCU/RTT2UART/releases) and extract it
to a writable directory. The published `v2.0.0` asset is named
`rtt2uart_v2.0.0.zip`. Keep all files from the package together.

For the current source workflow, the working directory must contain:

- `JLinkCommandFile.jlink`, used to export the device list through Commander.
- `JLinkDevicesBuildIn.xml`, used by the device selector. A successful export can
  refresh it; an existing copy is needed when export fails.

If your package is missing these files, use the matching source version to
prepare a complete directory as described in [Packaging](./development.md#package-for-windows).
Do not assume that a single executable contains these external files.

Launch the program with its extracted directory as the working directory. In
PowerShell, change to that directory and run the executable supplied in the
package. For a build named `rtt2uart.exe`, for example:

```powershell
.\rtt2uart.exe
```

Only one application instance is intended to run at a time. If no window
appears, check whether RTT2UART is already running.

## 2. Create a virtual COM port pair

Install a virtual serial port tool, such as the
[com0com tool referenced by the original README](http://com0com.sourceforge.net/),
and create a connected pair. The example below uses **COM4 for RTT2UART** and
**COM5 for the serial application**; use the actual names on your host.

![Example virtual COM port pair](../picture/VirtualSerialPort.png)

Each application opens a different endpoint. Close other programs that hold
either endpoint before selecting it. RTT2UART's **Scan** briefly opens and
closes enumerated serial ports and lists only those it can open.

## 3. Configure the USB connection

1. Select **USB** under **Connection to J-Link**.
2. If you need a specific probe, select **Serial NO** and enter its serial
   number. Otherwise, probe selection is delegated to the J-Link runtime.
3. Under **Specify Target Device**, click **...**, select the exact target
   device, and confirm with **OK**. Selecting a row populates the device choice.
4. Set **Target Interface And Speed** for your actual wiring and target. On a
   first run without saved settings, the GUI selects **SWD** and **4000 kHz**.
   These are application defaults, not a recommendation for every target.
5. Choose whether to enable **Reset target**. Enable it only when resetting the
   target is appropriate for the session; the USB startup path requests a reset
   with `halt=False` after its Target connection, only during initial startup.
6. Optionally select **Auto Reconnect** (off by default for USB). After a ready
   run loses its probe, Target debug connection, or RTT channels, the bridge
   retries only the original probe. Returning to USB mode while idle restores
   the off default; Existing Session defaults to on. The choice is frozen at Start.

USB recovery preserves Target, interface, and speed and never repeats the explicit
startup reset. **Running** requires the original probe and the complete
Target/RTT/serial chain to be ready. Another attached probe is never substituted.
Native J-Link connection sequences can still reset/halt particular Targets;
verify those effects on the actual hardware.

Recovery waits 1, 2, then 5 seconds, continuing at 5 seconds until success or Stop.
The serial port stays open and incoming bytes are discarded and counted, including
during a slow native connection. Pending stale input and uncertain write tails
are never replayed. **Stop** cancels waiting and invalidates a late connection;
a blocked native call may leave **Stop incomplete** until it returns and cleanup
finishes. Initial startup and serial-port failures remain terminal.

![Device selection example](../picture/SeleteDevice.png)

The interface list includes JTAG, SWD, cJTAG, and FINE, but the current
cJTAG selection is rejected as unsupported by the pinned pylink 1.2.0 interface enum. The list does not establish that
every interface is usable with your probe and target.

## 4. Select the serial endpoint and start

1. Click **Scan** and select the RTT2UART endpoint, **COM4** in this example.
2. Choose a baud rate. The first-run GUI default is **115200**. Configure the
   peer serial application consistently with the virtual port driver's
   requirements; use 115200 for this example.
3. Click **Start**. The status shows **Starting** while configuration is locked,
   then **Running** with the actual USB probe serial number after readiness.
4. Open **COM5**, the other endpoint, in the serial application.

The serial baud rate is a host serial-port setting. It does not set the RTT data
rate or the J-Link debug-interface speed. RTT2UART leaves the other serial
format and flow-control properties at the serial library's defaults.

**Running** requires an open serial port, verified probe identity, a Target debug
connection, and usable RTT channel-0 up/down buffers. It does not prove that
firmware has consumed a command. With Auto Reconnect off, runtime USB loss
cleans up and shows **Failed**; retry manually. With it on, eligible USB loss
shows **Reconnecting**. A serial failure always ends the run. **Stop incomplete** keeps restart and window closure
pending while a native call or cleanup is outstanding. Confirm actual traffic
in the next step.

![Serial application on the other COM endpoint](../picture/serialcomtool.png)

The screenshots are historical workflow examples. Available controls and their
layout can differ from the version shown.

## 5. Verify each direction

### Receive target output

Have the firmware emit a known RTT message, such as a diagnostic counter or
startup message. Confirm that the expected message appears in the serial
application on COM5. Ensure the firmware is running and that the message is
emitted after the bridge is connected.

### Send data to the target

Use a command that the target firmware already accepts through RTT input.
Configure the serial application's encoding and line endings for that command,
send it through COM5, and confirm a specific response or target-side effect.
RTT2UART does not add line endings or interpret commands.

Record the two results separately. Receiving output proves the receive path;
it does not prove that the firmware consumes RTT input. If no input handler is
available, record the send test as **not performed** rather than passed.

Click **Stop** when finished, then close the serial application. Stop the
bridge before changing connection mode or connection parameters.

## Use an existing J-Link session

Choose **Existing Session** when another local J-Link application owns the
probe connection and provides the RTT endpoint.

1. Start and configure the external J-Link session. Confirm that it provides
   the intended target's RTT data at `localhost:19021`.
2. Start RTT2UART. A discoverable J-Link runtime is still required because the
   GUI creates a J-Link object during startup, even in this mode.
3. Select **Existing Session**. The target device, debug interface, debug
   speed, and reset controls are disabled; the external session owns those
   choices.
4. Select the bridge's COM endpoint and baud rate. **Auto Reconnect** is checked
   by default; uncheck it if an endpoint loss should end the run.
5. Click **Start**, open the paired endpoint in the serial application, and
   verify both directions as above.

After **Starting**, the status reports **Endpoint connected — Target state
unverified**. This permits forwarding but does not prove that firmware is ready
or has executed a command. Settings are locked for the active run.

With Auto Reconnect enabled, loss of an established endpoint (EOF or socket
read/write failure) shows **Reconnecting**. Attempts wait 1, 2, then 5 seconds,
remaining at 5 seconds until success or Stop. Connection time is additional.
A failed first startup rolls back and requires manual retry. Serial-port failure
ends the run; the bridge never substitutes another serial port.

During recovery the original serial port stays open. Input is continuously
discarded, including during a slow connection attempt. **Observed discarded
input** counts bytes the bridge read and definitely discarded; it is not total
end-to-end loss or evidence of firmware execution. Pending stale local input is
drained before forwarding resumes. Uncertain or partially sent commands are
never replayed; a write error does not prove that a command failed to execute.
The count remains visible after recovery and resets on a new Start.

The bridge forwards raw bytes without framing, handshake, or heartbeat commands.
The serial application and firmware remain responsible for protocol boundaries,
resynchronization after interruption, and any application retries.

**Stop** cancels recovery. Closing the window requests the same shutdown; a late
connection result is cleaned up. **Stop incomplete** keeps restart disabled and
window closure pending until owned operations and cleanup finish. Existing
Session leaves the externally owned J-Link session untouched. See
[Lifecycle migration](./lifecycle-migration.md) for deadlines and validation scope.

## Refresh the target device list

On Windows, application startup attempts to run J-Link Commander with
`JLinkCommandFile.jlink` to export `JLinkDevicesBuildIn.xml` into the working
directory. A successful export is the normal refresh path.

If a target is missing:

1. Check that the installed J-Link software knows the exact target model.
2. Check that `JLink.exe` is present alongside the discovered J-Link library and
   that the command file and working directory are writable/available.
3. Close RTT2UART. From its working directory, run Commander from your J-Link
   installation to repeat the export. Replace the example path below with the
   path to your installed `JLink.exe`:

   ```powershell
   & 'C:\path\to\JLink.exe' -CommandFile .\JLinkCommandFile.jlink
   ```

4. Confirm that the XML was created, then restart RTT2UART and reopen the
   device selector.

If automatic export fails, the program logs the error and the selector uses
the XML already in the working directory. It does not search other locations
for a replacement. Exporting manually is a fallback, not a requirement after
every successful startup.

![Historical device-list export example](../picture/exportdevicelist.png)

## Troubleshooting

| Symptom | Check or next action |
| --- | --- |
| `Find jlink dll failed !` | Install or repair the J-Link runtime and check its discoverability and architecture compatibility with the program. Existing Session has the same startup requirement. |
| `Can not find device database !` | Check the working directory and `JLinkDevicesBuildIn.xml`; follow the refresh steps above. |
| `Select a Target device` | Select an actual device row and confirm it before starting USB mode. |
| Expected COM port is missing from Scan | Confirm that the driver created the port and that another program has not opened that endpoint. Retry Scan while stopped. |
| Serial port cannot be opened | Check the selected endpoint, permissions, and other programs using it. RTT2UART and the serial application must use different endpoints of the pair. |
| USB identity mismatch or unavailable | Check the requested serial number and physical probe. The bridge fails safely without selecting another probe. |
| RTT channel 0 readiness timed out | Verify Target power/debug connection and initialized channel-0 up/down buffers in the firmware. USB does not use a localhost listener. |
| Endpoint connect failure | For Existing Session, check the intended external session at `localhost:19021`. |
| Stop incomplete | Wait for the outstanding operation/cleanup to complete. Restart stays disabled; the GUI remains responsive. |
| Failed after previously Running | With USB Auto Reconnect off, correct the visible failure and restart after cleanup. When enabled, eligible USB loss shows Reconnecting; serial failure is always terminal. |
| Output is received but target ignores sent data | Verify the firmware's RTT input handler, the session's buffer mapping, and the command's encoding and line endings. |
| Settings appear to change after moving the program | Settings are read from the current working directory; launch consistently and recheck the selected ports. |
| No new window appears | Check for an already running RTT2UART process; the GUI entry point uses a single-instance guard. |

For diagnostic output, run from a console using the
[source instructions](./development.md#run-from-source) or build without
`--noconsole`. The code configures Python logging but does not configure a log
file. A console-free executable may not expose these messages.

When reporting a problem, include the source revision or release asset name,
Windows/Python versions where applicable, J-Link software and probe versions,
target model and firmware, connection mode, COM pair, settings, exact error,
and which transfer direction failed. Use the
[repository issue tracker](https://github.com/tianxiaoMCU/RTT2UART/issues).
