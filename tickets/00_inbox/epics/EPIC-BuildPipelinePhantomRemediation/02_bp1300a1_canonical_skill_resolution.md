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
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
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
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
