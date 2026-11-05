# Acceptance evidence retention

Keep the smallest inspectable record supporting each conclusion: candidate and
environment identity, method, decisive measured values/state transitions,
cleanup/rollback, scope limits and any operator-approved exception. Controlled,
real hardware, GUI and operator-reported evidence must remain distinguishable.
The gate matrix and results live in [integration acceptance](../integration-acceptance.md).

For #13, each dated directory keeps one concise README and one evidence.json.
Selected original JSON values are consolidated under their original filename
keys. Each has a source SHA256 at fixed revision `06e2c1911a79d1b2eab85842e7bd7f99277acce3`. Full original
values are retained unless the entry explicitly documents a projection:
redundant UIA pattern metadata, repeated native status/RTT polls, or unchanged
GUI polling plateaus. Key timestamps, original indices, call counts, blocked
calls, calibration, traffic and cleanup remain inspectable. Paths inside
captured payloads and historical check summaries describe that original run;
they are not current file dependencies or fresh verification claims.

Only seven representative #13 PNGs, the operator's unchanged filled receipt,
the approved deployment qualification and one final suite/type log pair are
kept. Duplicate frames, full repeated UIA trees, unused payload hashes,
one-off controllers, debug/preparation attempts, superseded manifests and
repeated test/build output are omitted from the current tree. Rejected attempts
remain explicitly excluded in the summaries, not reclassified as passes.
The #12 baseline and reusable test/firmware sources are unchanged.

## Recover historical detail

The complete pre-compaction records/controllers are available in the original
development history at the fixed revision above. These commands require that
local history or an explicitly supplied archive; they do not work in a fresh
clone containing only the squashed master history:

```powershell
git ls-tree -r --name-only 06e2c1911a79d1b2eab85842e7bd7f99277acce3 -- docs/evidence
git show 06e2c1911a79d1b2eab85842e7bd7f99277acce3:docs/evidence/issue13-h09-2026-11-04/source-starting-final.json
git archive --format=zip --output=build/issue13-original-evidence.zip 06e2c1911a79d1b2eab85842e7bd7f99277acce3 docs/evidence
```

A local backup also exists at ignored
`build/issue13-evidence-before-compaction.zip`; it is not a repository dependency
or a distributed artifact. For replay, recover the original controllers into a
fresh isolated build directory and follow their recorded firmware, ownership,
fresh-path and rollback prerequisites. Do not run them over saved evidence.
On 2026-11-05 the maintainer requested squash integration of the 59 development
commits into master. The original local development branch and the verified
ignored bundle `build/issue7-closeout/issue7-development-before-squash.bundle`
retain the old history. That history is not pushed with the squash commit.
Fresh master clones contain the compact evidence here, not the removed raw
attempts/controllers or their original commit objects. Historical revision
strings and captured paths are provenance, not promises of remote availability.
Ask for the optional local archive only when that detail is needed. No existing
published master history is rewritten and no force push is required.

## Future changes

Start with one dated summary/result record per tested configuration; add a raw
file only if a specific conclusion needs independent inspection of it. Prefer
the final accepted run. Keep debug/raw attempts in ignored `build/` during work;
record unresolved failures and limitations in the summary. Do not commit whole
temporary directories or a copy of the same test log for every minor change.
Use a bounded screenshot set only where visual state adds evidence beyond
measured data. Store reusable test logic in tests/scripts, not copied per run.

[issue13-artifacts.json](./issue13-artifacts.json) is the sole current #13
inventory: repository-relative paths, byte counts and SHA256 of canonical Git
file bytes, with attributes preserving those bytes on checkout. It
excludes itself to avoid recursive hashes. Rebuild/check it whenever retained
evidence changes, and verify both exact file-set equality and all digests.
Never leave a current Markdown link pointing to a removed raw file.
