---
title: "KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely"
description: "KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — PARTIALLY FIXED (re-verified 2026-09-23). Closed: the validator this
  entry named (old `build_phases.py:1928`, now `validate_agent_self_description` in
  `scripts/build_phases_agent_validation.py`) no longer derives its registry path from
  `target_root` at all — `target_root` is accepted for interface parity only and is
  unused in the function body; the path is hardcoded to
  `package_root / "config" / "agent_registry.json"` (see the function's own "Anchored on
  the PACKAGE, not on target_root" comment). It no longer validates the self-hosted build
  against itself. Separately, `<target_root>/config/agent_registry.json` IS now genuinely
  deployed to every consumer install, by write loops in both `build_phases_ac_store.py`
  and `build_phases_lifecycle.py` (BP-900g-8-ii / BP-900h-4) — confirmed by reading both
  call sites. And the deployed `plan-feature.js` workflow no longer reads any
  `agent_registry.json` path itself: ACD-2100b-5 moved the registry read out of the
  workflow body entirely (`templates/workflows-js/plan-feature.js:2319-2341`: "this
  workflow physically cannot read config/agent_registry.json itself"). Remains open, in a
  new and more central form: the replacement — `scripts/worktree/
  check_workspace_setup_permission.py`, which `/plan-feature` now runs as a local
  pre-flight before every workspace-setup dispatch — reads
  `<repo_root>/.leafcutter/config/agent_registry.json` (its `REGISTRY_RELATIVE_PATH`), and
  no build phase deploys anything to that path: `scripts/build_closure_guard.py`'s own
  comment says so ("a spurious `.leafcutter/config/agent_registry.json` no deploy phase
  declares"), and a full grep of every `build_phases*.py` module for a write under
  `output_root / "config"` confirms it. Ran the deployed script directly from this
  worktree (`python3 .leafcutter/scripts/worktree/check_workspace_setup_permission.py
  --agent-id worktree-agent`): it resolved `repo_root` via `git rev-parse
  --git-common-dir` to a *different* checkout
  (`/home/henzeh/projects/leafcutter/leafcutter-ai`, neither this worktree nor the shared
  `.leafcutter` symlink target) and read a registry there dated 2026-09-07 — six days
  stale against the 2026-09-14 source — present only by accident, not by any build
  guarantee. So `/plan-feature`'s workspace-setup permission gate now depends on a path
  the build never populates; where it is genuinely absent the workflow fails closed with
  `outcome: read_failure` before any authoring agent runs. New closure condition:
  `build.py` deploys `agent_registry.json` to `<output_root>/config/agent_registry.json`
  as a declared, closure-guard-checked dependency of
  `check_workspace_setup_permission.py`, not the conceptual redirect the guard applies
  today. Affects `/plan-feature`: yes, unambiguously — the entry has always been about a
  registry-read mismatch involving `plan-feature.js` specifically, and its live successor
  mechanism is invoked exclusively as `/plan-feature`'s own workspace-setup pre-flight.
  **Counter-evidence, so this is not read as harsher than the facts support (added
  2026-09-23 in review of the audit above).** The paragraph above is accurate about the
  DECLARATION, but must not be read as "a consumer install is broken today". Two
  measurements say otherwise. First, `unit_tests/portability/test_acd_2100d_1.py` and
  `test_acd_2100d_3.py` — which build a real install and assert the installed route
  reaches the same first question as the source route — pass, 7 tests, re-run
  2026-09-23. Second, CI's `Consumer install simulation (BP-900h-1)` gate is green. So
  in a genuinely built install the path does resolve. Note too that
  `build_closure_guard.py`'s comment, quoted above, says in the same breath that
  rooting this script's closure at `package_root / ".leafcutter"` makes the candidate
  resolve to `config/agent_registry.json`, "the form already declared", and calls that
  "a declaration/wiring correction". The risk is therefore LATENT rather than observed:
  the runtime read is correct only while `<repo_root>/.leafcutter` and the deploy
  output root coincide, and nothing asserts that invariant mechanically. The
  `outcome: read_failure` path is the correct fail-closed behaviour if they ever
  diverge — not a failure seen in a real install. The closure condition above stands;
  its justification is the unasserted invariant, not a consumer being broken right now.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:1928` (`registry_path` used by the self-description
  validator), `:1863` (docstring naming the same path), `:62` (`REGISTRY_PATH`, the
  source-side constant the build reads from) · `.leafcutter/workflows/plan-feature.js:1749`
  (the deployed workflow's own registry read)

**Symptom.** A consumer install has `agent_registry.json` at neither path the codebase
actually uses — and the build's own validation cannot detect that, because the only layout
it has ever run in is the one where the check is structurally incapable of failing.

**Mechanism.** `build_phases.py:1928` computes `registry_path = target_root / "config" /
"agent_registry.json"` and validates the registry there; the docstring at `:1863` describes
the same path as holding the required registry fields. Nothing in the build ever *copies*
`config/agent_registry.json` to `target_root / "config" /`. A grep of `build_phases.py` for
the filename returns only the source-side constant, the validation read, doc comments, and
error-hint strings — no write:

```text
$ grep -n "agent_registry.json" scripts/build_phases.py
10:    agent_registry.json and passes it + the skills_root to
62:REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
465:    Registry injection (ticket 29): loads ``agent_registry.json`` once and passes
1863:    in ``target_root / "config" / "agent_registry.json"`` for required registry
1928:    registry_path = target_root / "config" / "agent_registry.json"
2005:                        f"  Fix hint: Add '{field}' to the agent's entry in config/agent_registry.json."
2072:            "Set self_description_enforcement='error' in config/agent_registry.json "
2124:    registry entry from ``config/agent_registry.json``, calls
2907:#   agent_registry.json once per phase call and passes agents, registry_path,
```

In the self-hosted layout this validation passes trivially, because `target_root/config/` IS
the package's own source `config/` directory — the same file `REGISTRY_PATH` reads from. The
check has therefore never been meaningful in the one place it has ever run: it validates the
source against itself.

Meanwhile the deployed `/plan-feature` workflow reads the registry from a *different*
location. `.leafcutter/workflows/plan-feature.js:1749` runs
`"cat .leafcutter/config/agent_registry.json\n"`. So `build_phases.py` expects
`<target>/config/agent_registry.json` and the deployed workflow expects
`<target>/.leafcutter/config/agent_registry.json` — and nothing in the build populates
either path in a real consumer install (see KI-BP-003's fourth occurrence: `.leafcutter/config/`
deploys only `commit_guardian` and `feedback_categories.yaml`).

**Consequence.** A consumer install has the registry at neither path. The build's own
validation cannot catch this, because in the only layout where it runs — self-hosted — it is
reading the package's source copy, not a deployed one, so it reports success regardless of
whether either deployed path is populated.

**Relationship to other entries.** Same root-cause shape as KI-BP-003 (see that entry's
fourth occurrence): `config/` is not deployed. Both are unfixed instances of the rule
`BP-900g-8-ii` already states — "the deployed-dependency closure covers the data and
configuration files a script reads, not only the modules it imports." `KI-BO-018` (in
`docs/known-issues/build-orchestration.md`) is a related but distinct failure one layer up:
`/plan-feature`'s registry read there succeeds only *incidentally*, because the process
working directory happened to be the workspace parent that holds a populated `.leafcutter/`
— the same non-portable assumption, caught in the one case where it happens to resolve.

**Fix direction.** Anchor the validator's `registry_path` and the deployed workflow's read to
the same, actually-deployed location, and make the build copy `config/agent_registry.json`
there. Until then, do not trust a passing self-hosted validation run as evidence that a
consumer install's registry is reachable by anything that runs against deployed output.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in a validates-against-itself sub-form: the only layout
the check has ever run in is the one where target and source are the same directory, so it
has never been able to fail.

---
