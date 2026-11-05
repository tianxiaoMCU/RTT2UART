# SSH deployment and dependency isolation — 2026-11-05

Passed for the operator-supplied Windows11 Pro x64/build26200/J-Link7.54d setup
under the [explicitly approved qualification](./gate-qualification-proposal.md).
CubeIDE1.9.0 and NI remained installed. Bare Windows without development tools
was not tested and is outside the closure claim. No Start/RTT/Target transfer
was performed on this host; COM37 was only enumerated/selected, including the
ordinary startup scan. Earlier active-hardware rows remain separate.

[Evidence](./evidence.json) retains baseline, exact package transfer, vendor
runtime/signature selection, all46 GUI assertions and exits, both complete
125-module snapshots, their32 bundle-file hashes with independent candidate
payload baselines, returned settings checks, cleanup, approval and final tracker
readback. Every record cites its canonical original Git SHA256. Captured paths
are historical; current inventory is [issue13-artifacts.json](../issue13-artifacts.json).

Candidate EXE SHA256:
`54ba4201db67641607d272ddee062a31aa53ec882f5953dc24e2ea1f8a0bd02d`.
The45,427,454-byte handoff ZIP hash was
`f9ab7cf7d64f5788db1cd346cb8bb03df2fec73d7e0d39e6d696aaf0d778e237`.
Standalone7.54d vendor-signed installer/hash and selected user-scope DLL/hash
are retained. CubeIDE7.62a was discovered, not GUI-tested. No Python/Qt install
was performed. Runtime remained installed under the final operator instruction.

SSH password was entered by the operator in a local console; no credential,
new SSH key or account was scripted. SSH session0 launched a temporary task in
interactive session6 for native UIA/PrintWindow. Disposable deployment/settings
were used, not a source checkout/virtualenv. Launch PATH contained Windows and
the selected standalone runtime; Python/Qt/Conda overrides were cleared if set.
Temporary task removal and no remaining candidate processes were checked.

All46 assertions passed: cold startup/resources/defaults, mode controls,
USB return, F407/JTAG750/19200/COM37 save/normal close/reopen, Cancel/empty OK,
actual ARM7 selection/history, second-instance exit0/original survival and final
H750/SWD1000/115200 restoration/history. Three main exits and second-instance
exit were0. [Existing controls frame](./evidence/02-existing.png),
[reopened persisted settings frame](./evidence/04-reopened.png).
Returned six-key settings were independently read with a restricted unpickler.

Each125-module sample has32 native `_MEI` files matching independent extraction
from the same frozen EXE; all other sampled modules belong to Windows/candidate.
No sampled CubeIDE/NI/external Python/Qt module. This is finite sampling, not
continuous file-I/O or in-process sys.path tracing, nor proof of tool absence.
Exact in-process J-Link catalog-load instant was not traced.

First controller attempt used the wrong selector AutomationId, stopped after
save/reopen and closed normally; it is excluded. Corrected full run used actual
UIA identity and original disposable settings. Supplemental remote source
rehash did not return; local uploaded-byte comparison supported helper provenance,
not a remote rehash receipt. Original return ZIP/hash and exact measured/replay
controllers remain in the [historical snapshot/local ignored build](../README.md).
Personal account/profile prefixes in published JSON were redacted before the
original commit; screenshots/settings were unchanged.

The [retained final suite log](./controlled-suite.txt) passed61/61 in9.511s;
[strict types](./typecheck.txt) passed5 modules. Independent Standards review
ended with0 remaining findings after replay cleanup ownership was guarded.
Independent Spec review was unavailable due usage limit; the primary-agent
scope check is separate, not an independent Spec pass. Later controlled replay
guard checks did not rerun remote GUI.

gate-approval.json records the literal operator approval; tracker-readback.json
confirms #13 closed/completed, all criteria checked, parent#7 unchanged/open.
This compaction adds no test run, issue mutation or new acceptance claim.
