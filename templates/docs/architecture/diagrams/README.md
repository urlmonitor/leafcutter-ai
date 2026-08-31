---
title: "Architecture Diagrams"
type: reference
status: active
created: 2026-08-31
last_updated: 2026-08-31
components: []
---

# Architecture Diagrams

This folder holds one Markdown file per C4/sequence/ERD/state/dataflow diagram,
authored via the `write-c4-diagram` skill.

## Filename convention

`c{level}-{seq:03d}-{slug}.md`

| Segment | Meaning |
|---|---|
| `{level}` | C4 tier digit: `1` Context, `2` Container, `3` Component, `4` Code. |
| `{seq}` | Zero-padded 3-digit sequence, allocated by `scripts/next_diagram_seq.py`. |
| `{slug}` | Lowercase, hyphen-separated, 3-6 words. |

Two files collide when they resolve to the same `c{level}-{seq}` pair, regardless
of slug.

## Allocating the next number

Run `scripts/next_diagram_seq.py` before creating a new diagram — do not guess
the next sequence number by hand.

## Full numbering rule

The complete identifier-shape rule, free-number lookup, and never-reuse policy
live in `docs/reference/artifact-numbering.md` (once that document exists).

See also `docs/architecture/README.md` and the `write-c4-diagram` skill.
