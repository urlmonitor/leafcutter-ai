---
title: "Reference: /plan-feature Layout and Startup Checks"
description: "Which copy of each /plan-feature support file runs depending on where the route is started, which directory a repair to that file has to land in for an install to carry it, and the complete set of startup checks that can halt the route before its first question to the user."
type: reference
status: active
created: 2026-09-08
last_updated: 2026-09-08
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/build-drift-hook.md
  - docs/build-pipeline.md
  - docs/architecture/components/ac-driven-dev.md
---

# /plan-feature: Layout and Startup Checks

You are reading this because a `/plan-feature` run stopped before it asked you
anything, with a message about a file the route could not find or a directory
that is not a repository. This page states the delivered fact that resolves
that surprise: which copy of each support file the route actually reads,
where a fix to one of those files has to land, and the complete, closed set of
checks that can stop the route before its first question — with each check's
own report quoted exactly as it appears on your screen.

This page does not tell you how to fix your situation step by step. For a
step-by-step remedy, follow the "Fix"/"Remedy" text quoted below, or read the
matching entry in
[`docs/known-issues/ac-driven-dev.md`](../known-issues/ac-driven-dev.md) —
`KI-ACD-004` and `KI-ACD-009` are the two reports most readers of this page
arrive holding.

---

## 1. Which copy of each support file runs

`/plan-feature` is not a single file: the workflow body
(`templates/workflows-js/plan-feature.js`, deployed to
`.leafcutter/workflows/plan-feature.js`) dispatches or reads several other
files while it is starting up — the agent registry
(`config/agent_registry.json`), the workspace-setup permission pre-flight
(`scripts/worktree/check_workspace_setup_permission.py`), the worktree-setup
script (`scripts/setup_ticket_worktree.py`), and the pause store
(`scripts/pause_store.py`). Every one of these is resolved by the **same
shared mechanism** — `_buildRepoRootResolutionSnippet()` on the workflow side
and `resolve_repo_root()` on the Python pre-flight side, which are
deliberately kept in step with each other — never by a path relative to
whatever directory the session happens to be sitting in. This matters because
the three situations below are exactly the three situations that mechanism
was built to tell apart (`ACD-2100a-5`), after two real incidents
(`KI-ACD-004`, `KI-ACD-009` cause 1) in which the wrong copy — or no copy —
was found.

Resolution is tried in this fixed order and stops at the first hit:

1. **`git rev-parse --git-common-dir`, run in the starting directory itself.**
   All linked worktrees of a repository share one `.git` directory, so this
   answer is the same whether the starting directory is the main checkout or
   one of its worktrees — unlike `git rev-parse --show-toplevel`, which
   reports whichever worktree is current.
2. **Otherwise, the immediate (non-hidden) child directories of the starting
   directory, each probed the same way.** This is the ADR-001 self-hosting
   layout: the starting directory is the untracked workspace parent, and the
   repository is one level down as one of its own children.
3. **Otherwise, the immediate (non-hidden) child directories of the starting
   directory's own *parent* — i.e. the starting directory's siblings —
   probed the same way.** This covers a starting directory that has no
   filesystem relationship to the repository at all, but shares a workspace
   parent with it.

If none of the three resolves, the check fails closed and names the location
it could not find — it never falls back to a directory-relative guess that
could silently select the wrong physical copy.

### Started from the project root

Step 1 resolves directly: `git rev-parse --git-common-dir`'s parent is the
project root itself. Every support file listed above is read from inside that
same repository. This is the case every fixture historically tested, and the
one case that was never broken.

### Started from a git worktree of the project

Step 1 still resolves, and resolves to the **same** repository root as the
main checkout — a linked worktree shares its one `.git` directory with the
checkout it was created from, so `--git-common-dir`'s parent is identical
regardless of which worktree the route is started from. This is what closed
`KI-ACD-009` cause 1: reading `config/agent_registry.json` from a worktree
used to fail outright, because the file exists only at the workspace root's
`.leafcutter/config/`, not inside a worktree's own (worktree-local)
`.leafcutter/` — `git worktree add` only ever checks out tracked content, and
`.leafcutter/` is untracked build output. Resolving through the shared
git-common-dir step rather than the worktree's own directory is what makes
the registry reachable from a worktree at all.

### Started from a directory outside the project

If the starting directory is not a repository and has no repository among its
own children, step 3 probes its **siblings** instead — the case of a
scratch, notes, or otherwise unrelated directory that merely happens to sit
next to the project under the same workspace parent. This is a single
bounded directory listing one level up and one level down, never an unbounded
filesystem search, so it stays inside the route's own startup-time budget
(`ACD-2100a-5`).

### The installed copy behaves identically to the source copy

`ACD-2100d-1` established, by actually starting both a run against a fresh
installed copy and a run against the source checkout under the same starting
directory and comparing what each run *did* (never a file diff or a checksum
comparison), that both reach the first user question and that neither halts
at a check the other passes. As confirmed at that record's sign-off
(2026-09-08), no separate deploy-manifest gap or harness gap causes the
installed copy to behave differently on this path — the three situations
above hold the same way for an installed project as for the source checkout.

---

## 2. Where a repair has to land

Per [ADR-001](../architecture/adrs/ADR-001-self-hosting-boundary.md): everything
under `leafcutter-ai/` — including `templates/` and `scripts/` — **is source**.
Everything the installer (`build.py`) writes elsewhere in a project (`.claude/`,
`.leafcutter/`, `.agents/`, and the other output directories) **is regenerated
build output**. A repair made only to a regenerated file is invisible to the
next install: `build.py` overwrites it from source, and the repair evaporates.
This is precisely how the 2026-08-18 workaround for `KI-ACD-004` was lost —
patched into the deployed copy, then silently erased by the next build.

The authoritative, mechanically-checked mapping of which source template
produces which installed output — and therefore which installed directories
are regenerated and must never be hand-edited — is derived from the
installer's own manifest (`output_mappings` in `.build_manifest.json`, built by
`_compute_output_mappings()`), not restated here as a second, hand-maintained
list: a second list is exactly the kind of artifact that goes stale the first
time a directory is added, silently telling a reader the wrong place to put a
fix. See
[`docs/build-drift-hook.md`](../build-drift-hook.md) §2B ("Output directories
covered") for the current, generated table, and
[`docs/build-pipeline.md`](../build-pipeline.md) for the full compile/deploy
flow. `scripts/commit_guardian/check_output_drift.py` enforces this mapping
at commit time — a repair landed only in an output directory is reported as
undelivered, by name, before it can be mistaken for done (`ACD-2100d-2`).

The support files this page's §1 names above follow the same rule: their
source lives under `templates/workflows-js/` and `scripts/` respectively, and
what a running route reads is always resolved to the copy inside the
repository being operated on — never a copy the resolution mechanism in §1
was specifically built to avoid selecting.

---

## 3. Startup checks that can halt before the first question

The Pre-Stage-0 Workspace-Setup Permission Gate is the check that decides
whether `/plan-feature` may proceed to create its authoring worktree. It is
the mandatory gate ahead of every authoring dispatch (`BO-1500f-1`), and per
`ACD-2100b-4` it is a **closed set**: every outcome other than "granted" halts
the run before any authoring agent is dispatched, before an authoring
worktree or branch exists on disk, and reports an outcome that says the run
did not proceed — never a success outcome. There is no fifth, unenumerated
way for this gate to let a run through.

As of the fix landed for `KI-ACD-009` (`ACD-2100b-5`), the check is a local
read — `scripts/worktree/check_workspace_setup_permission.py`, run by the
`/plan-feature` skill itself before the workflow starts — rather than an
agent dispatch, so a transport failure can no longer masquerade as one of the
outcomes below. The verdict it produces carries one of six `outcome` values,
and the workflow renders a different, specific report for each. Every report
below is quoted verbatim from `templates/workflows-js/plan-feature.js`
(current as of the fixes above), with the agent id shown exactly as the source
builds it: by string concatenation of the real `workspaceSetupAgentId`
variable, which resolves to `args.workspace_setup_agent` or, when that is not
set, defaults to `worktree-agent`. The quotes below show that default value;
a run configured with a different `workspace_setup_agent` sees its own id in
the same position, since the source substitutes the variable itself, never a
literal placeholder token.

| Outcome | What it means | What it does **not** mean | Report |
|---|---|---|---|
| No verdict supplied at all | The workflow was invoked directly, bypassing the skill's own pre-flight step, so no `args.workspace_setup_permission` reached it. | Not a permission denial — the check never ran. | "No workspace-setup permission pre-flight verdict was supplied in args (args.workspace_setup_permission). This workflow no longer resolves the workspace-setup permission itself: the plan-feature skill's pre-flight (scripts/worktree/check_workspace_setup_permission.py) must run BEFORE this workflow is invoked and pass its verdict through args. This is a MISSING pre-flight, not a permission denial — halting before any authoring agent is dispatched." |
| `read_failure` | The registry file could not be obtained at all — no repository could be resolved, the file does not exist at the resolved location, or the process was denied permission to read it. | Says nothing about `worktree-agent`'s (or whichever agent id is configured) charter — it was never consulted. Do not edit the registry entry on this report alone. | "The workspace-setup permission pre-flight could not read the agent registry at '`<location>`'. `<reason>` Halting before any authoring agent is dispatched." — where `<reason>` is one of "No repository could be resolved from the current directory.", "No file exists at the resolved registry location.", "The process was denied permission to read the resolved registry location.", or "The registry could not be read." |
| `parse_failure` | The registry file was read, but its contents are not valid JSON with an `agents` array. | Says nothing about any specific agent's entry — no entry could be looked up. | "The workspace-setup permission pre-flight read the agent registry successfully but its contents could not be interpreted as valid JSON. Halting before any authoring agent is dispatched." |
| `agent_not_found` | The registry was read and parsed successfully; it simply has no entry for the configured agent id (a rename or a typo in `workspace_setup_agent` both look like this). | Not a permissions problem — nothing says the agent is denied, only that it is absent. | "The isolated-workspace setup step 'worktree-setup' was configured to dispatch to agent 'worktree-agent', but that agent was not found in the registry (config/agent_registry.json). Halting before any authoring agent is dispatched. Report this mis-assignment to the operator: step='worktree-setup', agent='worktree-agent'." |
| `no_entries_collection` | The registry parsed as JSON, but its `agents` field is not a list at all (missing key, or the wrong type). | A distinct fact from `agent_not_found` — the entries collection itself is malformed, not merely missing one entry. | "The agent registry (config/agent_registry.json) could not be used: its 'agents' field is not a list of agent entries. Halting before any authoring agent is dispatched. Fix config/agent_registry.json so that 'agents' is a list of agent entries." |
| `permission_denied` | The registry was read, the configured agent id was found, and its entry's `permits_shell` field is not `true`. This is the **only** outcome that is genuinely a permissions verdict. | — | "The isolated-workspace setup step 'worktree-setup' was configured to dispatch to agent 'worktree-agent', which is listed in the agent registry (config/agent_registry.json) but is not permitted to run repository-mutating shell commands. Halting before any authoring agent is dispatched. Fix config/agent_registry.json's permits_shell field for agent 'worktree-agent' to true, or report this mis-assignment to the operator: step='worktree-setup', agent='worktree-agent'." |

Only the `permission_denied` row directs you at the `permits_shell` field.
Every other row is deliberately silent about it — before `ACD-2100b-3` fixed
this, all four non-granted outcomes rendered the identical permissions
message, which sent an operator to audit a registry entry that was frequently
already correct (`KI-ACD-009`). If your run reported one of the other five
rows, editing `permits_shell` is not the fix; follow that row's own report
instead.

---

## See also

- [`docs/known-issues/ac-driven-dev.md`](../known-issues/ac-driven-dev.md) —
  `KI-ACD-004` (wrong-copy resolution from a worktree) and `KI-ACD-009`
  (the false permissions cause) are the full incident write-ups behind §1 and
  §3 above.
- [ADR-001 — Self-Hosting Boundary](../architecture/adrs/ADR-001-self-hosting-boundary.md)
  — the source-vs-build-output boundary behind §2.
- [`docs/build-drift-hook.md`](../build-drift-hook.md) — the generated
  source→output mapping and the commit-time check that enforces it.
- [`docs/build-pipeline.md`](../build-pipeline.md) — the full template
  compile/deploy pipeline.
- [`docs/architecture/components/ac-driven-dev.md`](../architecture/components/ac-driven-dev.md)
  — the component this page's `ac_driven_dev` frontmatter declares, alongside
  the acceptance criteria this page describes.
