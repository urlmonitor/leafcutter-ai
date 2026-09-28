---
title: "KI-CG-20260923-no-gate-validates-doc-to-doc-markdown-links"
description: "No commit-guardian hook checks that a relative link between two markdown docs resolves. check_doc_links covers code-to-doc only, by design, so a doc that links to a file which does not exist passes every gate."
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260923-no-gate-validates-doc-to-doc-markdown-links — a doc can link to a file that does not exist and pass every gate

- **Severity:** medium — no wrong verdict on code, but the docs are this repo's agent knowledge plane. A dangling link sends a reader, human or agent, nowhere. Filed at medium rather than low because a single routine doc split produced three broken references in one sitting (below) and not one gate noticed.
- **Status:** open. Observed 2026-09-23 while splitting `docs/reference/ac-schema.md` under the `check-doc-length` ratchet.
- **Occurrences:** 1 (three distinct broken references in that one change)
- **First seen:** 2026-09-23 · **Last seen:** 2026-09-23
- **Where:** the gap is an absence. Nearest neighbour is `templates/scripts/commit_guardian/check_doc_links.py:286` `get_staged_files()`.

**This is NOT a defect in `check_doc_links`.** That hook is registered as *"Check Doc Links Bidirectional Traceability"* (`commit_guardian.json:1338`), its `_comment` in the same config reads *"check_doc_links.py — Code-to-doc traceability link validation"* (line 325), and its purpose is to verify that a **code** file's `DOC_LINKS` point at real docs. Its `get_staged_files()` returning only `.py` and `.sql` is correct for that job. The point of this entry is the *other* direction — doc → doc — which nothing owns.

**The evidence that nothing owns it.** Across `templates/scripts/commit_guardian/check_*.py`, exactly one file contains markdown link syntax at all (`](`), and that is `check_doc_length.py`, where it appears in the suggestion templates it prints — not in any validation. Several hooks read `.md` (`check_doc_frontmatter`, `check_doc_coverage`, `check_adr_cross_reference`, `check_architecture_scaffolds`, `check_mermaid_*`), and each checks its own narrow property — frontmatter fields, ADR presence, scaffold shape, diagram complexity. None resolves a relative link target.

**What it let through, live.** Splitting `ac-schema.md` into `ac-schema.md` + a new `ac-id-hierarchy.md` produced, in one change:

1. Two `## See Also` links in the new child pointing at `ac-store-hooks.md` and `ac-agent-integration.md` — **files that have never existed** anywhere in the repo.
2. A same-file anchor on `ac-schema.md`'s `covered_by` row, `#covered_by--scope-convention`, **orphaned by the extraction itself** — the heading it pointed at had just moved to the child doc.

The orphaned anchor is the instructive one: the split *created* the dangling reference. Any extraction that moves a heading can orphan every in-document anchor pointing at it, and that is precisely the change shape `check-doc-length`'s refusal message actively pushes authors toward (*"Use the `@documentation-expert` agent to intelligently split and cross-reference these sections"*). So the repo has a gate that prescribes an operation whose most likely failure mode no gate detects.

All three were caught only because the agent doing the split hand-wrote a throwaway link checker. `check_doc_links` ran in that same commit and **passed** — correctly, on its own terms, having inspected the staged `.py` files.

**Fix direction.** Add a doc→doc arm — either widening `check_doc_links`'s staged set to `.md` with a separate validation path, or a sibling hook. Two details worth stating up front, because the throwaway checker got the second one wrong on its first pass:

- Resolve **relative paths** against the linking file's directory, and skip absolute URLs and `mailto:`.
- For **heading anchors**, match GitHub's slug rules, which are not the obvious ones: GitHub does **not** collapse consecutive spaces, so `## covered_by — Scope Convention` becomes `#covered_by--scope-convention` with a double hyphen. A checker that collapses whitespace reports a false positive on correct links, which is worse than no checker — it trains authors to ignore it.

Start it at `severity: warn`. 654 tracked `.md` files under `docs/` have never been link-checked; the first blocking run would almost certainly refuse an unrelated commit for pre-existing breakage, which is the pattern `KI-CG-20260909-gate-*` already documents for other dormant gates.

**Related.**
- `KI-CG-20260909-gate-doc-links` — `check-doc-links` returns 0 unconditionally, so registering it adds a gate that cannot fail. Adjacent but distinct: that entry is about the code→doc arm being inert, this one is about the doc→doc arm not existing. Fixing either does not fix the other, and a fix for this one should not be folded into that entry.
- `KI-CG-20260914-ac-hooks-resolve-root-from-cwd` — same family in the broad sense: a check whose real scope is narrower than a reader assumes, so its green means less than it appears to.

**Pattern:** a gate family that covers one direction of a two-directional relationship, where the covered direction's name reads like it covers both. The absent half is invisible precisely because the present half is green.
