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

[issue13-artifacts.json](./issue13-artifacts.json) is the single retained-evidence
inventory. Its historical filename is kept for existing links; its scope now
covers all files under `docs/evidence/`, including #12 and future records.
It lists repository-relative paths, byte counts and SHA256 of canonical Git
file bytes, and excludes itself to avoid recursive hashes. Refresh reviewed
entries whenever retained evidence changes; temporary output belongs in ignored
`build/`, not in this directory.

## Automated checks

The [shared check entry point](../../scripts/check.py) runs
[check_evidence.py](../../scripts/check_evidence.py) before types/compilation/tests.
It rejects missing/unlisted files, invalid or repeated manifest paths, incorrect
byte counts/SHA256 and byte-identical evidence copies. Git's own clean conversion
supplies canonical bytes, including its text/binary detection and attributes;
temporary objects are isolated from the repository's object store and index.
This checks content consistency, not whether a claimed hardware result is true.
Whether each retained file is necessary remains a review decision.

Git-tracked Markdown and all evidence Markdown are checked for local inline
links/images and reference-link destinations, including inbound links from
outside this directory. Fenced/inline code examples are excluded. Heading
fragments and remote URLs are not checked; captured JSON paths remain historical
provenance, not live links. These checks never rewrite evidence or its manifest.

Each run reports current evidence file/byte totals, added and removed files/bytes,
and net byte change. Local runs compare with `HEAD` by default; use
`python scripts/check_evidence.py --base master` to compare against a branch or
commit. Windows CI supplies `EVIDENCE_BASE`: the PR base SHA, the previous push
SHA, or the current SHA for manual runs. An initial push's all-zero SHA means
an empty baseline. Invalid/unavailable baselines fail instead of reporting zero
growth. CI fetches history so those comparisons are available.

The shared runner saves the report in ignored `build/checks/run-*/evidence.log`;
CI keeps that directory as a temporary seven-day artifact. No report is committed
automatically and no arbitrary growth limit is imposed. Reviewers use the totals
alongside the retention rules above.
