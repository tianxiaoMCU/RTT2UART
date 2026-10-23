# Domain docs

## Layout and reading rules

This repo uses a single-context layout:

- `GLOSSARY.md` at the repo root: read before exploring domain concepts.
- `docs/adr/`: read decisions relevant to the area being explored.

When these files are absent, proceed silently. Create them lazily
through domain modeling when terminology or decisions are resolved.

## Vocabulary

Use terms defined in `GLOSSARY.md` in issue titles, proposals,
hypotheses, and tests. Note unresolved terminology for domain modeling.

## Decision conflicts

When a proposal contradicts an existing ADR, explicitly identify
the ADR and explain why the decision should be reconsidered.
