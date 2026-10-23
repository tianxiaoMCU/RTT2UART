# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `tianxiaoMCU/RTT2UART`.
Use the `gh` CLI. Run inside this clone or pass
`--repo tianxiaoMCU/RTT2UART`.

## Operations

- Create: `gh issue create --title "..." --body-file <file>`
- Read: `gh issue view <number> --json number,title,body,labels,comments`
- List: `gh issue list --state open --json number,title,body,labels`
- Comment: `gh issue comment <number> --body-file <file>`
- Add/remove labels: `gh issue edit <number> --add-label "..."` /
  `--remove-label "..."`
- Close: `gh issue close <number> --comment "..."`

For multiline text, use a UTF-8 file with `--body-file`.

## Skill routing

- "Publish to the issue tracker" means create a GitHub issue.
- "Fetch the relevant ticket" means read its GitHub issue.

## Pull requests as a triage surface

PRs as a request surface: no.

## Wayfinding

- Map: one issue labelled `wayfinder:map`, containing Notes,
  Decisions-so-far, and Fog.
- Child: one issue per ticket, linked as a sub-issue when supported.
  Otherwise add `Part of: #<map>` and a task list in the map.
- Type: `wayfinder:research`, `wayfinder:prototype`,
  `wayfinder:grilling`, or `wayfinder:task`.
- Blocking: use native issue dependencies when supported;
  otherwise record `Blocked by: #<number>`.
- Frontier: first open, unassigned child in map order whose blockers
  are all closed.
- Claim: assign the ticket to the driving developer before work.
- Resolve: comment with the result, close the child, then add a
  result summary and link to the map's Decisions-so-far.
