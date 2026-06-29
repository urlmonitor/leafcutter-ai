---
title: "Consolidate AC-store parsing in guardrail hooks behind one mtime-cached index"
status: todo
components:
  - build_pipeline
created: 2026-06-29
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
origin_agent: BrainCandy
files_touched:
  - templates/scripts/commit_guardian/_ac_store_index.py
  - templates/scripts/commit_guardian/check_ac_schema.py
  - templates/scripts/commit_guardian/check_ac_circular_deps.py
  - templates/scripts/commit_guardian/check_ac_parent_covered_by.py
  - templates/scripts/commit_guardian/check_ac_pattern_refs.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Consolidate AC-store parsing in guardrail hooks behind one mtime-cached index

## Goal

In order to keep pre-commit fast as the AC store grows, the four AC guardrail
hooks must parse the AC store **once** per commit (not once per hook), by sharing
a single mtime-cached `id -> parsed-AC` index module instead of each hook
independently walking and YAML-parsing every file under
`docs/acceptance-criteria/`.

## Context

Discovered during the EPIC-SafeAcAuthoring finalize (2026-06-29), where four AC
hooks timed out (>5 min, hit the cap) on a merge that staged ~200 AC files. A
follow-up investigation found the AC store has grown to ~1,790 YAML files, and a
single full-store parse measures ~10.4 s on this machine.

Two of the four hooks have already been fixed individually:

- **check-ac-parent-covered-by** (PR #183) — was O(staged × store); now builds an
  `id->file` index once per invocation.
- **check-ac-schema** (PR #185) — was one `git show HEAD:<path>` subprocess per
  staged file; now batches HEAD fetches into one `git cat-file --batch`.

The remaining two each still pay one full-store parse (~10 s) per run, and the
two fixed hooks each build their own index/cache independently:

- **check-ac-circular-deps** — builds the full depends_on graph once
  (`_build_depends_graph`) by parsing every AC file.
- **check-ac-pattern-refs** — builds its pattern/ref index once by parsing every
  AC file.

Because each hook parses the whole store separately, a single commit that runs
all four hooks pays the ~10 s parse up to four times. The structural fix is a
**shared, mtime-keyed cached index** module imported by all four hooks, so the
store is parsed exactly once per commit and reused.

### Notes / related

- Sibling follow-up already tracked: `TICKET-20260617-Worktree_Precommit_Bootstrap.md`
  (worktrees lack `.pre-commit-config.yaml` so local hooks are skipped — out of
  scope here).
- The canonical hook copies live under `templates/scripts/commit_guardian/`; the
  `scripts/commit_guardian/` copies are gitignored build outputs (do not edit).
- `check-ac-circular-deps` must keep the FULL graph for correctness — cycles can
  route through unstaged nodes. Optimize the parse/index, never the graph scope.

## Acceptance Criteria

```gherkin
Scenario: AC store is parsed once per commit across all four hooks
  Given a commit that stages one or more AC YAML files
  And check-ac-schema, check-ac-circular-deps, check-ac-pattern-refs, and
    check-ac-parent-covered-by all run in the pre-commit chain
  When the hooks execute
  Then the AC store under docs/acceptance-criteria/ is fully walked and
    YAML-parsed at most once across all four hooks (a shared cached index)
  And re-running a hook within the same process/commit reuses the cached parse
    rather than re-walking the store.

Scenario: cache is invalidated when the store changes
  Given the shared AC index has been built and cached
  When an AC YAML file under docs/acceptance-criteria/ is added, modified, or
    removed
  Then the next index access reflects the change (the cache key incorporates
    store mtime/content), so hooks never validate against a stale snapshot.

Scenario: correctness of all four hooks is unchanged
  Given the shared-index refactor is applied
  When the existing unit test suites for all four hooks run
  Then every existing assertion passes unchanged (schema validation, circular-dep
    detection across unstaged nodes, parent covered_by enforcement, and pattern
    reference checks all produce identical verdicts to before the refactor).

Scenario: large-store performance no longer scales per hook
  Given an AC store of ~1,790+ files
  When a commit staging a large batch of AC files runs the four hooks
  Then total AC-store parse time is bounded by a single full-store parse (plus
    O(staged) work), not one full parse per hook
  And the hooks complete well within the pre-commit timeout.
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
