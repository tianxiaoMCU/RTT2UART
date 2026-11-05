# Frozen EXE GUI and active cleanup — 2026-11-02

Passed on the recorded Windows10/J-Link7.54d/HHD6.2.0.1318 setup, using the
unchanged candidate, disposable six-key settings, native UIA and PrintWindow.
[Evidence](./evidence.json) retains result.json, saved settings/history,
single-instance/close/resource/byte records, physical USB recovery states and
explicit cJTAG/SWD save/reopen states. Repeated UIA pattern metadata is omitted;
committed values, enabled flags and states remain.

GUI defaults, locked controls, history, selector Cancel/empty OK, save/reopen,
first-start terminal failure, second-instance exit0, active USB and Existing
normal close passed. Existing Session's external test owner still echoed after
bridge close. It retained Target-unverified text through recovery.
[Representative Reconnecting/count26 frame](./existing-reconnecting.png).

Actual EXE USB unplug/restoration recovered the same probe with27 observed
discards and fresh exact echo. Recovery-off loss remained Failed after
restoration; manual Start and active normal close released COM/probe.
No outage marker was observed replayed in the recorded output windows.

Traffic completed196 exact256-byte chunks (50,176 bytes); totals were50,432 sent,
50,177 received over17.172s, including the intentionally interrupted final chunk
and its1-byte prefix. That prefix is not a full-echo pass. Stop to observed
Stopped was0.301s including UIA/poll overhead, not a universal bound.

Stripped development PATH passed on this development host, separately from
later deployment acceptance. Historical pending fields in result.json describe
that date; later H09 and deployment results supersede them. The unresolved
original interface-display discrepancy is not claimed fixed. Independent
Standards/Spec review ended with0 remaining findings; no reviewer reran UI or
hardware. See the [retention policy](../README.md) for original controllers and
removed diagnostic screenshots, and the [integrated record](../../integration-acceptance.md)
for final scope.
