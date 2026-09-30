---
title: "Labelled frontmatter path entries resolve instead of crashing the guard (GE-118d) — KI-CG-008 fixed"
date: "2026-09-28"
time: "19:05"
type: manual
components:
  - commit_guardian
summary: "Fixed a crash that was blocking adopter DIAGraph from committing dozens of its documents, and closed the workaround that had been switching a working commit gate off entirely."
description: "Fourth entry in the GE-118d/KM-KGS-100d-3 sequence (after the two 2026-09-21 spec entries, cbdbfb99 and de442295, and the 2026-09-28 approval/ticketing entry, 83c664a2 — all three explicitly spec-only). This commit lands the fix: check-doc-frontmatter's validate_paths() now resolves each related_docs/related_code/architecture_diagrams entry through a new shared classifier, scripts/frontmatter_path_resolver.py, instead of crashing on a labelled (single-key mapping) entry. A multi-key mapping is refused by name rather than resolved by guesswork. KI-CG-008 moves to resolved/ in this same commit. GE-118d itself stays work_status: in_progress (not done) — its children GE-118d-1 and GE-118d-2 are untested and still todo — and the sibling defect in knowledge_query.py (KM-KGS-100d-3) is untouched."
commits:
  - 2fd3d784
breaking: false
---

## Entry

### What this is

The payoff of the sequence that started with the two 2026-09-21 spec entries and the
2026-09-28 approval/ticketing entry (`cbdbfb99`, `de442295`, `83c664a2`) — all three said,
explicitly, that the defect was still live. As of this commit that stops being true for the
crash half.

`KI-CG-008` was a blocker reported by adopter DIAGraph: a document whose `related_docs` entry
used the labelled form (`- explanation: docs/foo.md`) crashed `check-doc-frontmatter` with
`TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'`, because
`validate_paths()` checked that the *field* was a list and never checked that its *elements*
were strings. At least 33 of that adopter's 50 such documents used the labelled shape, and
because the guard raised instead of refusing, the workaround in place was
`SKIP=check-doc-frontmatter` — a working gate switched off for every commit.

### What's accepted, what's refused, and why

A bare path string and a single-key labelled mapping (`{field_name: path_string}`) both now
resolve to the path they name. A **multi-key** mapping is refused by name, with a message
naming the field and the accepted shapes — never the parsed element's `repr()`.

That refusal is deliberate, not an omission: the known-issue's own suggested fix would have
resolved *all* values of a mapping, and both readings of "which value is the path?" fail
invisibly — taking the first silently drops a relationship, taking all makes this guard and
the knowledge graph disagree about how many relationships a document declares. Refusing is
the only outcome that can't be wrong quietly.

### Where the resolver lives, and why

`scripts/frontmatter_path_resolver.py` is new, and it is deliberately **not** under
`templates/scripts/commit_guardian/`. That tree is the compiled tier — its `.py` files get
config placeholders injected at build time — while top-level `scripts/` is copied verbatim.
The resolver has no config-dependent behaviour, so running it through `inject_config()` would
risk silently rewriting any `{...}`-shaped text in a refusal message; this repository has
already been bitten by exactly that. A new bridge module,
`templates/scripts/commit_guardian/_frontmatter_path_resolver_locator.py`, lets the deployed
hook reach the resolver by resolving through `__file__` rather than assuming a layout — the
deployed `commit_guardian` directory is a symlink, so a naive relative import lands in the
wrong tree.

The new module is registered in **both** deploy-manifest locations
(`build_workflow_tools()` in `scripts/build_phases_workflows.py`, and
`_manifest_workflow_tool_scripts()` in `scripts/build_phases_knowledge.py`) — a two-place cost
the repository accepts deliberately, because
`test_guard_source_paths_match_deployable_set` fails loudly if the two ever drift.

### The register moves with the fix

`docs/known-issues/commit-guardian.md` and `KI-CG-008` move to `resolved/` in this same
commit, so the "resolved" claim lands at the moment the code does rather than ahead of it.

### What this does NOT fix

`GE-118d` stays `work_status: in_progress`, not `done` — its children `GE-118d-1` (an
unaccepted shape is refused by name, with no traceback) and `GE-118d-2` (a multi-key mapping
is refused) are separate records with their own criteria, still `todo`, and untested by this
ticket's test_spec. And the other half of the original defect — the silent edge-drop in
`scripts/knowledge_query.py`'s `extract_edges()`, tracked as `KM-KGS-100d-3` — is untouched
and still live: a labelled entry still vanishes from the knowledge graph with no error.
