---
title: "KI-DS-20261021-architecture-docs-with-broken-parent-links — 19 architecture docs and 6 Python files fail the parent-link check now that it really runs; a commit that stages one of them is refused until its links are fixed"
description: "low — GE-113c-4 made check-mermaid-parent-link read the staged docs from the real project root; before, it checked nothing. A sweep on 2026-10-21 found 26 architecture docs it refuses plus 6 Python files (one real, five likely false positives). GE-113c-4-i fixes c1-001 and c2-001…c2-006. This record lists the other 19 docs and the 6 files, so that whoever next edits one fixes it in the same change."
type: reference
category: reference
status: active
created: '2026-10-21'
last_updated: '2026-10-21'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20261016-mermaid-parent-link-root-inside-package.md
---

# KI-DS-20261021-architecture-docs-with-broken-parent-links — 19 docs and 6 Python files fail the repaired parent-link check

> Filed 2026-10-21 during EPIC-RightJobRightAgentFollowUps (GE-113c-4). Index: [documentation-system.md](../documentation-system.md).

- **Severity:** low. Nothing is broken at run time. A commit that stages one of these docs is
  refused by check-mermaid-parent-link until its links are fixed. That is the intended behaviour,
  which these docs were never held to before.
- **Status:** open. Fix each doc when it is next edited, or in a dedicated sweep.
- **Occurrences:** 1 · **First seen:** 2026-10-21 · **Last seen:** 2026-10-21

## The docs (found by running the repaired `_check_arch_doc` over `docs/architecture/**/*.md`)

**ARCH-PARENT-NOTFOUND** — the bare `parent: agent_delivery_workflows.md` does not resolve; the
file is `docs/architecture/agent_delivery_workflows.md`:
- `diagrams/c2-fast-lane-build-path-components.md`
- `diagrams/c2-fast-vs-heavy-lane-phases.md`

**ARCH-PARENT-MISSING** — a mermaid block with neither `parent:` nor `root: true`:
- `diagrams/c3-011-done-proof-reachability-gates-sequence.md`, `diagrams/c3-done-proof-evaluation-sequence.md`
- `agent_delivery_workflows.md`, `agent_knowledge_plane.md`, `agent_knowledge_system.md`, `feedback-lifecycle.md`
- `components/build-orchestration.md`, `components/knowledge-management.md`, `components/knowledge-retrieval.md`,
  `components/knowledge-system.md`, `components/supervisor-spawn-topology.md`, `components/ux-prototyping.md`

**ARCH-LEVEL-ORDER** — the L3 diagram's parent `components/build-orchestration.md` is not at a higher level:
- `diagrams/c3-012-ticket-close-paths-sequence.md`, `diagrams/c3-fast-lane-build-loop-sequence.md`

**ARCH-BIDIRECTIONAL** — the parent does not list the child in `children:`:
- `diagrams/df-001-dual-engine-workflow-build-transform.md` (parent ADR-030)
- `components/build-epic-workflow-dispatch.md`, `components/build-ticket-workflow-dispatch.md`
  (parent `supervisor-spawn-topology.md`)

All paths are under `docs/architecture/`.

## Fix direction

Give each doc a resolvable repo-path parent at a higher flight level, or `root: true` for a true
top-level doc, and list each child in its parent's `children:`. Check with the hook's
`_check_arch_doc(<path>)`. It must return `[]`.

## Python and SQL files refused (PY-PARENT-DIAGRAM)

Found by running `_check_staged_file` over all 2860 tracked `.py` and `.sql` files on 2026-10-21.
Six are refused, all `PY-PARENT-DIAGRAM` (a mermaid fence with no `PARENT_DIAGRAM:` declaration).
The check's rule is a plain text match for a mermaid fence anywhere in the file, so a fence
inside a string literal or a regex counts. The check is not narrowed here; each file needs either
a `PARENT_DIAGRAM:` line in its header or a decision about the rule.

Likely **true positive** (a real diagram in the module docstring):
- `templates/scripts/sync_platforms/sync_platforms.py` — line 9, inside the module docstring.
  Add `PARENT_DIAGRAM: docs/architecture/<parent>.md` to the docstring.

Likely **false positives** (the fence is code that emits or parses a diagram, not a diagram in the file):
- `scripts/generate_agent_cards.py` — line 330, `lines += ["```mermaid", "flowchart TD"]`: a string literal in generated card text.
- `scripts/generate_agent_diagram.py` — lines 280 and 384: an f-string and a `print("```mermaid")` that emit a diagram.
- `templates/scripts/commit_guardian/card_mermaid_parser.py` — line 93, `if stripped == "```mermaid":`: parser code comparing against the fence.
- `templates/scripts/commit_guardian/check_mermaid_complexity.py` — line 164, `re.match(r"^\s*```mermaid", line)`: a regex that finds fences.
- `tests/test_check_mermaid_complexity.py` — lines 53, 60, 166, 172: fixture strings. (The hook skips paths containing `unit_tests`, but not `tests/`.)

Fix direction for the false positives: a separate decision. Either add a `PARENT_DIAGRAM:` line anyway,
or teach the rule to ignore fences inside string literals and regexes, which is a change to the check
and needs its own ticket and tests.
