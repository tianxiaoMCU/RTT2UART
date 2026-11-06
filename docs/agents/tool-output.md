# Tool and document output

## Tool discovery

- Call a tool directly when its current schema is already available.
- When discovery is needed, filter by the task's capability or namespace and
  emit matching names first. For `ALL_TOOLS`, print the filtered `.map(tool =>
  tool.name)` rather than full metadata objects.
- Read the complete description/schema only for the tools selected for the next
  step. Narrow or page a long name list before expanding metadata.

## Document reads

- Read applicable `AGENTS.md` and invoked `SKILL.md` instructions completely;
  paginate long instructions and follow required references before acting.
- For other reference documents, use the supplied heading or locate headings
  first, then read the relevant sections with line ranges. Expand to adjacent
  sections or linked references when they are needed to resolve the task.
  Preserve the repository's graph-first code discovery workflow.
- For an unfamiliar file, inspect a small byte prefix before emitting text.
  Bound characters/bytes as well as lines: a single binary or generated line
  can defeat a line limit. If a reader returns a binary header or cannot decode
  the file, stop that text dump and use an available reader that can decode it;
  treat it as unreadable if no such reader is available, not as proof of damage.
- If output is truncated, narrow the query or read successive ranges until the
  required content is complete. Use compact result fields and existing log
  files for large outputs, displaying the status and relevant diagnostics.
