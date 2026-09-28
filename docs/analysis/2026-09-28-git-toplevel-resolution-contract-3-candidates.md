---
title: "Candidates — git-toplevel resolution contract"
description: "Seven candidate resolution strategies for _git_toplevel() (cwd-first, script-dir-first, explicit-argument-only, deploy-time provenance marker, main's bounded cwd search, upward sentinel search, and install-root anchoring) measured against the dev, consumer and test-harness layouts."
type: explanation
status: active
created: 2026-09-28
last_updated: 2026-09-28
components:
  - worktree_manager
  - build_orchestration
  - build_pipeline
  - ac_driven_dev
related_docs:
  - docs/analysis/2026-09-28-git-toplevel-resolution-contract.md
---

> **Parent document:** [2026-09-28-git-toplevel-resolution-contract.md](2026-09-28-git-toplevel-resolution-contract.md)

## 3. Candidates

Four columns: **Dev** (deployed copy, agent cwd typically a worktree), **Consumer**
(deployed copy), **Harness** (the `bo2400f_13*` shape: script staged inside a temp repo,
cwd = the real checkout), and **Silent?** — whether a wrong answer is returned without
raising, which is the property that makes a defect survive.

### A. cwd-first, script-dir second — PR #866 as it stands

- **Dev:** ❌ resolves the enclosing worktree, or raises when cwd is outside any repo.
- **Consumer:** ❌ whenever cwd is not inside the adopter's project.
- **Harness:** ❌ 14 tests across `test_bo2400f_13*.py`; writes into the live repo.
- **Silent?** **Yes, both ways.** Strictly worse than `main` on this axis: `main` is
  silently wrong in zero measured cases, PR #866 in two.

Not viable. It makes the loud dev failure quieter without making it work, and converts a
correct consumer answer into a silent wrong one.

### B. script-dir-first — `main` before `ACD-2100a-2`

- **Dev:** ❌ raises, git exit 128. Loud. The original incident.
- **Consumer:** ✅ deployed copy is inside the adopter's repo, which is the right answer.
- **Harness:** ✅ this is what the harness is built on.
- **Silent?** No.

The docstring's premise — *"the script always lives physically inside the repository it
operates on"* — is false of every deployed copy, but the *behaviour* is accidentally
right in the consumer layout for a reason the docstring does not state: the deployed
copy is inside the install, and in that layout the install root and the served
repository coincide. B is only broken in the layout where they do not.

### C. Explicit argument only — require `--repo-root`

- **Dev / Consumer / Harness:** ✅ correct by construction, if every caller passes it.
- **Silent?** No — a missing argument is an immediate refusal.

The problem is the callers. `cmd_setup_ticket` already does the right thing
(`_git_toplevel(ticket_path.parent)` — it has a subject). `cmd_create_only` accepts
`--repo-root`. But `create-ac-worktree` and `create-fastlane-worktree` take **only a
slug** — there is no subject path to anchor on, and the caller
(`templates/workflows-js/fast-lane-ship.js:678`) is a workflow that would have to compute
the repository itself, relocating the same unsolved problem one layer up into JavaScript.
`BO-4100d-4`'s first `it_requirement` — *"the repository must be resolved from the
SUBJECT of the operation"* — is therefore unimplementable as written for two of the four
subcommands, which is worth noting because PR #866 does not satisfy it either: cwd is not
the subject.

Viable as a *hardening layer* on top of another option, not as the option.

### D. Provenance marker written at deploy time

Write `<install>/<output_root>/.package_origin` (or a field in `.build_manifest.json`)
naming the package repository, and read it at run time.

- **Dev:** ✅. **Consumer:** ✅ if the marker names the *install root*, ❌ if it names the
  package clone (which would send adopter worktrees into the vendored package).
- **Harness:** ❌ — no marker exists in the staged temp repo, so a fallback is required
  anyway, and that fallback is what actually decides the harness's behaviour.
- **Silent?** No, provided a missing marker refuses rather than guessing.

Two costs. First, `build_template_standalone_scripts()`
(`scripts/build_phases_script_deploy.py:424-474`) copies the script **verbatim — no
template compilation** — so this needs a new deploy step, not a placeholder in the source.
Second, this is KI-BP-011's territory: the build's provenance record has already been
moved once and re-scoped once, and the manifest at
`/home/henzeh/projects/leafcutter/.build_manifest.json` carries nothing but a flat
`path → sha256` map whose keys happen to be prefixed `leafcutter-ai/`. Depending on a new
artifact whose write-target contract is itself an open high-severity issue is a large
bet for a resolver.

### E. `main`'s bounded subdirectory search from cwd — `ACD-2100a-2`

Anchor on the script dir; on failure, search the immediate children of **cwd** for
exactly one repository.

Measured (`/tmp/probe_installroot.py`, part a):

| | result |
|---|---|
| dev, cwd = workspace root | ✅ `<ws>/leafcutter-ai` |
| dev, cwd = inside a worktree | ❌ **refuses** — 0 candidates |
| consumer, cwd = consumer | ✅ `<consumer>` (anchor wins; search never runs) |
| consumer, cwd = unrelated repo | ✅ `<consumer>` (anchor wins) |

Against the live workspace the search is exact: from
`/home/henzeh/projects/leafcutter` it returns `[.../leafcutter-ai]` and nothing else
(`.leafcutter/` contains a stub `.git/` with only `hooks/`, which git rejects;
`leafcutter-web/` is not a repository; `worktrees/` is not a repository root).

- **Silent?** No. Zero or many candidates ⇒ raise; one candidate ⇒ a WARNING on stderr
  naming the choice. This is the best-behaved property of any current option.

Three limits. It is **cwd-dependent in the one direction that matters least but still
matters**: the agent's cwd during a drive is usually a worktree, not the workspace root,
and that is a hard refusal (row 2). It is **fragile to a second repository** appearing in
the workspace — `git init` in `leafcutter-web/` would flip the dev layout from working to
refusing. And it is **wired into `cmd_create_only()` alone**
(`templates/scripts/setup_ticket_worktree.py:1843`), so `create-fastlane-worktree` —
the subcommand of the originating incident, invoked by `fast-lane-ship.js` against
`{{config.output_root}}/scripts/setup_ticket_worktree.py` — does not benefit at all.

### F. Upward search for a package sentinel

Walk up from the script's directory looking for a file that exists only in
`leafcutter-ai` (e.g. `templates/` + `scripts/build.py`).

- **Dev:** ❌ — the deployed copy lives under `.leafcutter/`, whose ancestors are the
  workspace parent and then `/home/henzeh/projects`; `leafcutter-ai/` is a *sibling*
  branch of the tree, never an ancestor. Upward walking cannot reach it.
- **Consumer:** ❌ — finds `<consumer>/leafcutter-ai`, the vendored clone, which is the
  wrong answer for the consumer layout (§1).
- **Harness:** ❌ — no sentinel in the temp repo.
- **Silent?** Worse: in the consumer layout it returns a plausible wrong answer.

Rejected. It also re-encodes "find leafcutter's repo", which §1 argues is the wrong
question.

### G. Install-root anchoring — *not covered by the brief, and the recommendation*

Derive the install root from the deployed copy's own fixed path shape, then resolve from
it:

1. `script_dir.parent.name == output_root` (`.leafcutter`) ⇒ install root is
   `script_dir.parent.parent`; otherwise install root is `script_dir.parent` (the
   in-repo copy at `<repo>/scripts/`).
2. If the install root is inside a git repository, that repository is the answer.
3. Otherwise (dev layout: the workspace parent is deliberately untracked), run
   `ACD-2100a-2`'s bounded search over the install root's **immediate children** and
   require exactly one.
4. An explicit `--repo-root`/anchor short-circuits 1-3 and never falls through.

Measured (`/tmp/probe_installroot.py`, part b) — all seven cases correct:

| case | resolved via | correct |
|---|---|---|
| dev, deployed copy, cwd = workspace | search under install root | ✅ |
| dev, deployed copy, cwd = a worktree | search under install root | ✅ |
| dev, in-repo copy, cwd = unrelated repo | install root | ✅ |
| consumer, deployed copy, cwd = consumer | install root | ✅ |
| consumer, deployed copy, cwd = unrelated repo | install root | ✅ |
| consumer, in-repo copy (vendored clone) | install root | ✅ |
| harness: copy staged in a temp repo, cwd = real checkout | install root | ✅ |

- **Dev:** ✅ including from inside a worktree, which E cannot do.
- **Consumer:** ✅ including from an unrelated cwd, which A breaks.
- **Harness:** ✅ **unchanged** — `<tmp>/repo_root/scripts/x.py` has a parent not named
  `.leafcutter`, so the install root is `<tmp>/repo_root`, which is a repository. The
  14 `bo2400f_13*` tests keep passing with no edit to the harness.
- **Silent?** No. Step 3 refuses on 0 or ≥2 candidates, with E's WARNING preserved for
  the search path.

It is D's idea — provenance from the deploy — without D's new artifact, because
`build.py` already encodes the provenance in the path it deploys to. It is E's search
without E's cwd dependency: same algorithm, anchored at the install root instead of the
process working directory. And unlike every cwd-based option, the answer does not change
when an agent runs `os.chdir()` — which this script itself does at
`cmd_create_ac_worktree` line ~1929.
