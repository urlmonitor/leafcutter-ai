---
title: "Blast radius — cwd-sensitive resolution across the codebase"
description: "Search of scripts/ and templates/scripts/ for Path.cwd(), os.getcwd(), and bare git rev-parse --show-toplevel. Only the two setup_ticket_worktree.py copies consult cwd to decide which repository gets WRITTEN to; a larger read-only-guard family and an invisible ~25-site git-rev-parse surface are cwd-sensitive but lower consequence."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/analysis/2026-09-28-why-the-cwd-regression-escaped-verification.md
---

> **Parent document:** [2026-09-28-why-the-cwd-regression-escaped-verification.md](2026-09-28-why-the-cwd-regression-escaped-verification.md)

## 4. Blast radius

Searched `scripts/` and `templates/scripts/` for `Path.cwd()`, `os.getcwd()`, and
`git rev-parse --show-toplevel` without an anchor. Grouped by whether the shape is the
one that broke.

### Same shape — cwd consulted in resolution, and the module mutates the repository

Only the two files of the incident:

- `scripts/setup_ticket_worktree.py:171` — the regression.
- `templates/scripts/setup_ticket_worktree.py:169` — the twin.

**But the twin behaves differently from its sibling, and the change made them diverge
further.** `templates/scripts/setup_ticket_worktree.py:242-292` carries
`_resolve_repository_with_search_fallback()` (AC ACD-2100a-2, commit `2b06a149`), which
`scripts/` does not have — verified: `git grep` for that symbol returns hits only under
`templates/`. In the template, `cmd_create_only` calls it
(`templates/scripts/setup_ticket_worktree.py:1843`); it defaults `anchor` to the
script's own directory (`:273-274`) and passes it *explicitly* to `_git_toplevel`,
which under the new order makes it **authoritative and never falls through to cwd**. In
`scripts/`, `cmd_create_only` calls bare `_git_toplevel()` (`scripts/setup_ticket_worktree.py:1801`)
and therefore goes cwd-first. After BO-4100d-4 the two copies resolve `create-only`
by opposite rules. This is pre-existing structural drift (deliberate, per the commit
message and the AC's it_requirement #5) that the change turned behavioural. It is
evidence about the change's unmapped reach; the contract question it raises belongs to
whoever is designing the resolution order.

Note also `templates/scripts/setup_ticket_worktree.py:278`: the search fallback searches
the immediate subdirectories of `Path.cwd()`. Cwd-rooted, but bounded, symlink-safe,
refuses on 0 or >1 candidates, and announces a search-based selection on stderr. That
is a cwd dependency built with the hazard in mind.

### Different shape, same sensitivity — read-only guards resolving a project root from cwd

These mis-*report* rather than mis-*mutate*; the direction is benign (a wrong answer
provokes investigation), which is why KI-CG-20260901 is graded medium. They are
nonetheless cwd-sensitive in the same mechanical way:

- `templates/scripts/commit_guardian/check_ac_schema.py:99-113` — `_find_project_root()`:
  `HOOK_ROOT` env, else walk ancestors of `Path.cwd()`. Cwd-first in practice.
- The identical ancestor-walk literal appears in
  `check_ac_circular_deps.py:89`, `check_ac_governance.py:273`, `check_ac_limits.py:288`,
  `check_ac_parent_covered_by.py:144` and `:497`, `check_ac_pattern_refs.py:191`,
  `check_surface_components_e2.py:83`, `check_surface_components_e3.py:66` — all under
  `templates/scripts/commit_guardian/`.
- `templates/scripts/commit_guardian/verify_precommit_active.py:111`, `:207`, `:597` —
  the KI-CG-20260901 subject.
- `templates/scripts/commit_guardian/check_hook_parity.py:478`,
  `check_hook_trigger_reachability.py:240`, `check_identifier_uniqueness.py:341`,
  `check_package_surface_declaration.py:130-133`, `check_paths_integrity.py:44`,
  `check_architecture_scaffolds.py:55`, `ensure_precommit_config.py:276`,
  `run_hook.py:74`, `transform_doc_index.py:143`,
  `transform_component_vocab.py:211`, `check_ac_coverage.py:204`,
  `check_v2_ac_store_alignment.py:308`, `_file_size_ratchet.py:424`.
- `scripts/worktree/check_workspace_setup_permission.py:374` —
  `resolve_repo_root(Path.cwd())` in `main()`, no CLI override.

These have a defensible contract (pre-commit runs hooks from the worktree root), and
`HOOK_ROOT` is a real escape hatch. KI-CG-20260901 is the record of that contract being
violated in practice.

### The surface a `Path.cwd()` grep cannot see

About 25 call sites run `subprocess.run(["git", "rev-parse", "--show-toplevel"], …)`
with neither `-C` nor `cwd=` — implicitly cwd-resolved, with no cwd token in the source.
Confirmed examples:

- `scripts/path_resolver.py:107-120` — `_git_root()`: bare `rev-parse`, then
  `return Path.cwd()` on failure. Feeds `resolve_path()`, the repository's dotted
  path-key resolver. Cwd-sensitive twice over.
- `scripts/pause_store.py:56-72` — `_resolve_project_root()`: bare `rev-parse`, warns,
  falls back to `Path.cwd().resolve()`; `_resolve_store_dir()` builds the store path
  from it.
- `scripts/ac_store/_gtfa_paths.py:191`.
- `templates/scripts/commit_guardian/_resolve_root.py:37` and ~20 individual checkers
  (`check_agent_diagrams.py:99`, `check_agent_registry.py:73`,
  `check_components_integrity.py:157`, `check_doc_frontmatter.py:99`,
  `check_glossary_coverage.py:497`, `check_mermaid_drift.py:232`,
  `check_placeholder_defaults.py:479`, `check_roadmap_schema.py:54`,
  `install_pre_commit_shims.py:248`, and others).

This is the single most important finding for guard design: **the cwd-sensitive surface
is materially larger than the `Path.cwd()` grep suggests, and the invisible part is
invisible to any token-based lint.** It is the reason G5 must be keyed on the `git
rev-parse` call shape, not on the `Path.cwd()` identifier.

### Consults cwd, correctly

- `scripts/build.py:1878`, `scripts/bootstrap_install.py:316`,
  `scripts/roadmap_query.py:489`, `scripts/knowledge_query.py:1479`,
  `scripts/seed_project_docs.py:150`, `scripts/seed_example_product.py:223` — cwd only
  as the default for an explicit `--target-dir` / `--project-root` flag. Caller-visible,
  overridable, conventional. Not the shape that broke.
- `scripts/project_context_discovery.py:48`, `:84` — cwd as the documented default of an
  optional `project_root` parameter.
- `scripts/ac_store/scan_ac_orphans.py:245-265` — a three-strategy module locator:
  package import, then script-relative, then a cwd ancestor walk **last**. This is the
  safe ordering, and it is the prevailing convention in this repository for locating
  helper modules.
- `templates/scripts/commit_guardian/_ac_store_locator.py:30-53` — explicitly refuses
  `Path.cwd()` and documents the test-scratch-repo hazard. The exemplar.
- `scripts/port_registry.py:356`, `:395`; `scripts/ac_store/done_proof.py:696`;
  `scripts/live_surface_startup.py:96`, `:150` — cwd as a last-resort default for
  config discovery or a JS/TS project root. Low consequence; not worth listing as risk.

**Honest summary: in the "cwd decides which repository gets written to" sense, it is
only the two `setup_ticket_worktree.py` copies.** Everything else is either
caller-overridable, read-only, correctly ordered, or an already-filed known issue.
