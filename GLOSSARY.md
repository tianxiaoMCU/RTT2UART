# RTT2UART

RTT2UART bridges a target's RTT communication and a host serial application.
This glossary defines the terms used in the user and developer documentation.

## Language

**Target**:
The embedded device whose firmware provides RTT communication through a J-Link probe.
_Avoid_: Host, serial application

**RTT bridge**:
The connection between the target's RTT communication and the serial port used by the host application.
_Avoid_: Target UART, hardware UART converter

**RTT endpoint**:
The host-side network endpoint through which RTT2UART exchanges RTT data with a J-Link session.
_Avoid_: COM port, debug interface

**Existing Session**:
A bridge connection that uses an RTT endpoint maintained by another J-Link application.
_Avoid_: USB connection, remote probe connection

**Virtual COM port pair**:
Two connected virtual serial ports on the host, with one endpoint used by RTT2UART and the other by a serial application.
_Avoid_: Target debug interface

**Serial application**:
The host program that exchanges data with RTT2UART through the other endpoint of the virtual COM port pair.
_Avoid_: Target firmware, RTT2UART
