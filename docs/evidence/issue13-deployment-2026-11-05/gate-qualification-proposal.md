# Operator-approved deployment-gate qualification — 2026-11-05

**Accepted explicitly by the operator:** “接受提案，按记录范围关闭 #13”.
This approval qualifies #13's remaining deployment gate for the recorded
candidate/host/runtime; it does not assert an IDE-free Windows installation.

The recorded host retains CubeIDE/NI, so it does not satisfy the existing
literal clean-host statement in [packaging-smoke.md](../../packaging-smoke.md#packaged-interactive-checklist).
The complete SSH run nevertheless passes the supplied Windows11/J-Link7.54d
GUI checklist and independently verifies the sampled native payloads/settings.

Approved release qualification:

- Require the unchanged candidate on the operator-supplied separate Windows
  host, with no application source/venv or extra Python/Qt installation.
- Require development-related variable/PATH isolation, observed Python/Qt
  native payloads matching the EXE, the full idle GUI checklist, settings
  readback, normal process exits and temporary-controller cleanup.
- Limit the accepted combination to recorded Windows11 x64/build26200 and
  standalone J-Link7.54d; retain all existing CubeIDE/NI inventory facts.
- Treat the passed deployment/dependency-isolation checks as
  satisfying #13's remaining deployment gate. Keep a Windows installation
  without any development software as **not exercised**, without claiming a
  bare-OS pass. All existing hardware, H07 and H08/H09 qualifications remain.

This is a scope qualification, not a claim that the supplied machine is clean.
The remaining release gate is satisfied within this approved scope and #13 may
close. A Windows host/VM without any development environment remains untested
and is outside this approved closure claim. Parent#7 is not modified.
