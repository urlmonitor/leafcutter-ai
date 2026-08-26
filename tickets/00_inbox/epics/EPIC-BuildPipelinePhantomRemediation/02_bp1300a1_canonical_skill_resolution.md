---
title: "Skill-pointer check must resolve against canonical source only, not the deployed .claude/skills tree"
status: todo
components:
  - build_pipeline
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
source_ac: BP-1300a-1
ac_coverage:
  - BP-1300a-1
  - BP-1300a-1-i
  - BP-1300a-1-ii
files_touched:
  - scripts/build_phases.py
  - unit_tests/build_guards/test_self_description_descriptive_only.py
agents:
  architect-review: needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 02: Dangling skill pointer must fail the build against canonical source

## Actor / Goal

As the build's skill-pointer check, I want each `skills_invoked` `skill_id` resolved
**only** against the canonical source (`templates/skills/` + the registry) and never
against the deployed `.claude/skills/` tree, so a dangling pointer fails the build
deterministically (BP-1300a-1) and a stale deploy can no longer mask it (BP-1300a-1-i,
BP-1300a-1-ii).

## Remediation Context (audit 2026-07-14)

**Opposite behaviour (wrong resolution tree).** In `scripts/build_phases.py` (around
line 1867) the registry validator computes:

```python
in_package = (package_skills_dir / skill_id).exists()
in_project = (project_skills_dir / skill_id).exists()   # <- resolves against DEPLOYED .claude/skills
if not in_package and not in_project:
    problems.append(...)
```

The `in_project` check resolves `skill_id`s against the **deployed** `.claude/skills`
tree. The "unmaskable guardrail" AC (BP-1300a-1) requires resolution against the
**canonical** source only (`templates/skills` + the registry). A stale local deploy that
still contains a since-removed skill will resolve `in_project = True` and hide a dangling
pointer — so the verdict differs between a stale local checkout and a fresh CI clone,
violating the environment-independence clause. The real finding it reproduces:
`documentation-expert -> direct-write` and `python-coder -> run-tests` fail in CI but pass
on a stale local deployment.

**Do: correct the resolution source, don't rewrite the validator.** Drop the deployed
`.claude/skills` (`in_project`) leg for skill-pointer resolution and resolve solely against
`templates/skills/` (plus the registry), keeping a single source of truth (the AC forbids a
parallel checker). Preserve the existing message that names the dangling `skill_id` and the
referencing registry entry, and report **all** dangling pointers (not just the first). Then
rewrite the tests in `test_self_description_descriptive_only.py` that currently lock in the
`in_project`-based behaviour (they assert resolution via the deployed tree) so they assert
the canonical-only verdict and its invariance to the deployed tree.

## Acceptance Criteria

Resolves BP-1300a-1, BP-1300a-1-i, BP-1300a-1-ii (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/BP-1300-unmaskable-guardrails/`). Definition of
done: an unresolvable `skill_id` fails the build (non-zero exit) naming the id + referencing
entry; the verdict is identical whether a stale `.claude/skills` artifact is present or
absent; both real dangling pointers are reported.

## Test Requirements

```yaml
tests:
  - name: test_ac_bp1300a_1_dangling_pointer_fails_against_canonical
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    covers: [BP-1300a-1]
    asserts: a skill_id absent from templates/skills + registry fails the build naming the id and the referencing entry.
  - name: test_ac_bp1300a_1i_stale_deploy_does_not_mask_real_dangling_pointers
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    covers: [BP-1300a-1-i]
    asserts: documentation-expert->direct-write and python-coder->run-tests both fail even when a stale deployed .claude/skills tree resolves them; both are named.
  - name: test_ac_bp1300a_1ii_verdict_invariant_to_deployed_artifacts
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    covers: [BP-1300a-1-ii]
    asserts: adding or removing the deployed .claude/skills artifact does not change the unresolved verdict.
```

## Sign-offs

- [ ] architect-review
- [x] test-writer — 2026-08-18 14:09
- [x] python-coder — 2026-08-18 15:05
- [ ] test-runner
- [x] pr-reviewer — 2026-08-18 15:29
- [x] commit — 2026-08-18 15:33
- [ ] pull-request

## Comments

### 2026-08-18 14:09 — test-writer (status: ok)
feedback-id: fb_2026-08-18_ec7db59c
completion_manifest:
  test_ac_bp1300a_1_written: true
  test_ac_bp1300a_1i_written: true
  test_ac_bp1300a_1ii_written: true
  red_baseline_confirmed: true
Added `TestCanonicalSourceOnlyResolution` (3 new tests) to
`unit_tests/build_guards/test_self_description_descriptive_only.py`, one per AC
(BP-1300a-1, BP-1300a-1-i, BP-1300a-1-ii), tagged `# covers: <AC-ID>`. All 3 exercise
`validate_agent_self_description` against a synthetic `tmp_path` registry/agent
fixture and fail today: `test_ac_bp1300a_1_dangling_pointer_fails_against_canonical`
asserts the failure message must not reference the deployed `.claude/skills` path;
`test_ac_bp1300a_1i_stale_deploy_does_not_mask_real_dangling_pointers` reproduces the
documentation-expert->direct-write / python-coder->run-tests audit finding with a
synthetic (non-descriptive_only) registry and a stale deployed `.claude/skills` dir
that currently masks both; `test_ac_bp1300a_1ii_verdict_invariant_to_deployed_artifacts`
asserts error_count is identical with/without a stale deployed artifact for a
canonical-source-absent skill_id.

Note on red-baseline verification: the default `pytest` run (no env var) reports
these as `xfail` (12 passed, 3 xfailed, exit 0) because `pytest_ac_enforcement`
downgrades AC-tagged failures to xfail while the AC's `work_status` is `todo` — per
existing project convention (`project_red_baseline_one_red_rule` /
`project_pytest_ac_enforcement_xfail_mask`), this masked xfail IS the correct red
signal, and I confirmed the true failure with `AC_ENFORCE_STRICT=1 pytest
unit_tests/build_guards/test_self_description_descriptive_only.py -k
TestCanonicalSourceOnlyResolution -v` (3 failed). python-coder / test-runner should
use `AC_ENFORCE_STRICT=1` (or wait for `work_status: done` after implementation) to
see the real pass/fail state, not the default masked run.

red_baseline:
  - test_name: test_ac_bp1300a_1_dangling_pointer_fails_against_canonical
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    error: "AssertionError: The failure message still references the DEPLOYED .claude/skills/ path... assert '.claude/skills' not in '  [ERROR] R...the build.\\n'"
  - test_name: test_ac_bp1300a_1i_stale_deploy_does_not_mask_real_dangling_pointers
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    error: "AssertionError: Expected the build to fail for documentation-expert->direct-write and python-coder->run-tests even with a stale deployed .claude/skills tree present, but got error_count=0. ... assert 0 > 0"
  - test_name: test_ac_bp1300a_1ii_verdict_invariant_to_deployed_artifacts
    file: unit_tests/build_guards/test_self_description_descriptive_only.py
    error: "AssertionError: Expected error_count > 0 even WITH a stale deployed .claude/skills/invariant-check-dangling-xyz/ artifact present ... but got error_count=0. ... assert 0 > 0"
    note: "Verified via 'AC_ENFORCE_STRICT=1 pytest ... -k TestCanonicalSourceOnlyResolution -v'; default (non-strict) run downgrades these to xfail per pytest_ac_enforcement (AC work_status: todo) — that xfail is the correct masked-red signal, not a pass."

### 2026-08-18 15:05 — python-coder (status: ok)
feedback-id: fb_2026-08-18_fac819ba
completion_manifest:
  in_project_leg_dropped: true
  canonical_only_resolution_implemented: true
  message_no_longer_names_deployed_path: true
  all_dangling_pointers_reported: true
  red_baseline_tests_green: true
  real_registry_spot_check_clean: true
On arrival, `scripts/build_phases.py`'s `validate_agent_self_description` already had
the `in_project` (deployed `.claude/skills/`) resolution leg dropped and resolution
narrowed to canonical source only (`templates/skills/`), matching this ticket's spec —
the error message no longer names the deployed path, and the aggregation loop still
reports every dangling `skill_id` (not just the first). I verified rather than
re-implemented: ran the 3 red_baseline tests from test-writer's sign-off with
`AC_ENFORCE_STRICT=1 pytest unit_tests/build_guards/test_self_description_descriptive_only.py
-k TestCanonicalSourceOnlyResolution -v` — all 3 green
(test_ac_bp1300a_1_dangling_pointer_fails_against_canonical,
test_ac_bp1300a_1i_stale_deploy_does_not_mask_real_dangling_pointers,
test_ac_bp1300a_1ii_verdict_invariant_to_deployed_artifacts) — and the full
15-test file (no regressions, including the pre-existing descriptive_only /
mistyped-marker tests that are out of this AC's scope). Ran a real-artifact
behavioral spot-check by invoking the validator directly against this repo's
actual `config/agent_registry.json` + `templates/agents/`: `error_count=0,
warning_count=0`, confirming `documentation-expert -> direct-write` and
`python-coder -> run-tests` (already marked `descriptive_only: true` from prior
remediation) resolve cleanly under canonical-only resolution with no dependency
on `.claude/skills/` state. No functional code edit was needed from me; the
docstring's decision-history log already carries a 2026-08-18 entry documenting
the change and its rationale. Anomaly: the ticket's own frontmatter is missing
`change_target` and `risk_surface` (required by `ticket_frontmatter_guard.py`,
present on sibling tickets 01/04/05/07/08/09 in this epic) — pre-existing gap,
out of scope for python-coder to fix; flagging for architect-review /
ticket-supervisor.

### 2026-08-18 15:29 — pr-reviewer (status: ok)
feedback-id: fb_2026-08-18_923695bf
completion_manifest:
  in_project_leg_confirmed_dropped: true
  message_confirmed_canonical_only: true
  all_dangling_pointers_still_reported: true
  full_test_file_green_no_regressions: true
  real_registry_spot_check_confirmed_clean: true
  high_confidence_findings: true
Reviewed the diff manually (no Agent/Task tool available in this dispatch to fan
out the pr-review-toolkit sub-skills, so code-reviewer / silent-failure-hunter /
pr-test-analyzer lenses were applied directly by hand). scripts/build_phases.py:
the `in_project` (deployed `.claude/skills/`) leg and its `project_skills_dir`
variable are fully removed; resolution is now `in_package` only against
`templates/skills/`; the error message no longer names the deployed path; the
aggregation loop still appends every unresolvable `skill_id` inside the same
`for inv in skills_invoked` loop with no early break, so all dangling pointers
are still reported, not just the first. No high- or medium-confidence findings.
Ran the full `test_self_description_descriptive_only.py` file: 15 passed, no
regressions, and confirmed all 3 target AC tests green under both default and
`AC_ENFORCE_STRICT=1` pytest invocations. Independently re-ran the validator
against this repo's real `config/agent_registry.json` + `templates/agents/`:
`error_count=0, warning_count=0`, matching python-coder's claim.

Two informational notes, neither blocking: (1) One transient run during my own
verification showed a false RED with the pre-fix error message text
(`AC_ENFORCE_STRICT=1 pytest ... -k TestCanonicalSourceOnlyResolution -v`, 3
failed, 45s) that did not reproduce on 4 subsequent identical invocations
(with/without STRICT, with `-B`) once `scripts/__pycache__/build_phases.*.pyc`
settled — consistent with this being a heavily-shared, concurrently-active
worktree (multiple other tickets' uncommitted changes are present in
`git status` right now) racing the bytecode cache rather than a real code
defect; the source file itself was confirmed stable (unchanged mtime) across
the flakiness window. Any agent verifying "green" in this worktree should treat
a single run as insufficient and re-run once before trusting a red result. (2)
`config/skill_registry.json` is a second listing of skill ids the ticket body
mentions ("templates/skills/ + the registry") — the implementation checks only
the `templates/skills/<id>/` directory, not this file directly, but
`scripts/registry_validator.py::validate_skill_registry` already enforces
bidirectional 1:1 parity between the two (verified: 41/41 match with zero
drift today), so this is not a functional gap, just worth architect-review's
awareness given `architect-review` and `test-runner` are still `needed` on
this ticket ahead of my sign-off in the listed order — I did not block on that
since I independently reproduced the green test/behavioral result they would
otherwise confirm.

### 2026-08-18 15:33 — commit (status: ok)
feedback-id: fb_2026-08-18_36aa2e7b
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed the `scripts/build_phases.py` change alone (commit `6f66ed45`,
"fix(build-pipeline): skill-pointer resolution uses canonical source only
(BP-1300a-1)") — pre-commit hooks ran clean, no autofix needed. Confirmed
staged content matched the reviewed diff (in_project leg + `project_skills_dir`
removed, canonical-only error message, all dangling pointers still reported)
before committing; excluded unrelated in-flight changes present in this shared
worktree (`scripts/build_helpers.py`, ticket 07, two untracked
`test_bp_100k_*.py` files belonging to other tickets) by staging
`scripts/build_phases.py` by name rather than via a bulk add.
`test_self_description_descriptive_only.py` required no new commit here — its
`TestCanonicalSourceOnlyResolution` additions were already present on this
branch from an earlier (unrelated-subject) commit `5e556a17`. While signing off
I also backfilled this ticket's missing `change_target: pipeline` /
`risk_surface: contract_boundary` frontmatter fields (flagged as a pre-existing
gap by python-coder) since `ticket_frontmatter_guard.py` was rejecting every
edit to this file without them. Anomaly: `architect-review` and `test-runner`
remain `needed` while `commit` is now `signed_off`, out of the frontmatter's
listed agent order — I proceeded per this dispatch's explicit instruction and
did not treat that as blocking, but flagging it for `ticket-supervisor`/
`pull-request` awareness.

### 2026-08-25 12:42 — python-coder (status: ok)
feedback-id: fb_2026-08-25_d3909244
completion_manifest:
  registry_leg_added_to_validate_agent_self_description: true
  literal_ac_wording_matched: true
  regression_tests_added: true
  full_scoped_test_run_green: true
  ruff_clean: true
Follow-up round on this same ticket, closing the gap pr-reviewer's 2026-08-18
15:29 comment flagged as informational-only. My own earlier sign-off (and
pr-reviewer's) left `validate_agent_self_description` resolving
`skills_invoked` `skill_id`s against `templates/skills/<id>/` ONLY, never
`config/skill_registry.json` — even though BP-1300a-1's criteria define the
canonical source as "templates/skills plus the registry", and
`skill_registry.schema.json` explicitly permits a `portable: false` skill
with no `template_path` (a domain-specific skill with no
`templates/skills/<id>/` dir by design). An adversarial review surfaced a
concrete case (`skills_invoked` naming a registry-declared, template-less
skill) that this narrower check would falsely flag as dangling. I chose
**Option A** — implement the criterion literally: resolve against
`templates/skills/<id>/` OR a matching `id` in `config/skill_registry.json`
— over Option B (document + pin the templates-only behavior), because the
schema explicitly invites the shape the old check rejected and the AC text
is unambiguous; narrowing further would just re-hide the same gap behind a
comment. Added `skill_registry_ids` loading (wrapped in
`try/except (OSError, json.JSONDecodeError)`, WARNING-logged, non-fatal) and
changed the resolution to `in_package or in_skill_registry` in
`scripts/build_phases.py`'s `validate_agent_self_description` only —
`check_command_reachability` and all other functions in that shared file
are untouched (verified via `git diff` hunk boundaries against the other
in-flight sibling edits in this worktree). Added three tests to
`unit_tests/build_guards/test_self_description_descriptive_only.py` under
`TestRegistryDeclaredWithoutTemplateResolves`:
`test_registry_declared_skill_without_template_resolves` (the literal gap:
`error_count == 0` for a `portable: false`/no-`template_path` registry
entry with no template dir), `test_skill_absent_from_both_templates_and_registry_still_fails`
(regression guard against an over-broad OR), and
`test_missing_skill_registry_file_does_not_crash_and_still_flags` (absent
`skill_registry.json` must not fail open). Ran
`AC_ENFORCE_STRICT=1 python -m pytest unit_tests/build_guards/ -q`: 104
passed, 4 subtests passed, no regressions in the pre-existing
`descriptive_only` / mistyped-marker / canonical-source-only test classes.
`ruff check` on both touched files: clean. I did not personally re-run the
full 4447-test suite the coordinator reported green, but independently
verified the real `scripts/build.py` call site (line ~1648) still calls
`validate_agent_self_description` correctly with the new `package_root`
parameter left at its default, and re-read `BP-1300a-1.yaml` directly to
confirm `covered_by` now lists my `TestRegistryDeclaredWithoutTemplateResolves`
class before signing off. One thing flagged but NOT fixed: `check_skills_invoked_xref`
in `scripts/registry_validator.py` (the advisory, non-build-failing
cross-reference checker) still resolves only against template-body text and
`descriptive_only` markers — it may need the same registry-only special-case
so it doesn't emit a spurious "declared but no reference found" advisory for
a registry-declared, template-less skill. Advisory-only, so I left it for a
follow-up ticket rather than expanding this one's scope.
