---
title: "The commit-time numbering check is wired into the live registry and fires on a real commit"
date: "2026-08-31"
time: "08:41"
type: manual
components:
  - build_pipeline
  - commit_guardian
  - precommit_hooks
  - ticket_lifecycle
  - ac_store
summary: "Registers the GE-122 whole-collection numbering pass, which had shipped complete and unreachable, and lands the install-path scaffolding it depends on."
description: "Registers check_identifier_uniqueness into the operative commit_guardian.json so the pass runs on a real commit, after landing the namespace scaffolding a fresh install needs first. Touches scripts/build.py, scripts/build_precommit.py, scripts/build_architecture_scaffold.py, scripts/ci/check_consumer_install.py, scripts/ci/_use_install_step.py, templates/scripts/commit_guardian/commit_guardian.json, templates/hooks/check_identifier_uniqueness_authoring.py and templates/docs/architecture/diagrams/README.md. Two of the seven acceptance criteria in scope are deliberately NOT claimed here."
breaking: false
---

## Entry

**A guard that had never run.** `check_identifier_uniqueness.py` landed in PR #495 complete
— five helper modules, eight test files, ADR-037, a C3 diagram — and registered nowhere.
Measured before this change: zero references in the deployed 55-entry
`templates/scripts/commit_guardian/commit_guardian.json`, zero in the non-deployed 3-entry
`templates/commit-guardian/commit_guardian.json`, zero in `.github/`. For comparison,
`check_presence_only_assertions`, shipped the same week, carried three registrations.

It runs now. On this branch's own implementation commit, the ordinary commit path produced:

```text
[check_identifier_uniqueness] acceptance-criteria: OK (3664 inspected)
[check_identifier_uniqueness] decisions:           OK (38 inspected)
[check_identifier_uniqueness] diagrams:            OK (24 inspected)
[check_identifier_uniqueness] work-items:          OK (298 inspected)
```

4024 artifacts across four namespaces, on a real commit — not a test invocation. The entry
carries `verbose: true` so that per-namespace count survives pre-commit's success-output
suppression, which is what makes a pass distinguishable from a pass produced by inspecting
nothing, and `always_run: true` because the pass reads the whole collection regardless of
what is staged.

**Registration had to come last, not first.** Measured on both documented install paths
including `--seed-docs`, the build created neither `docs/architecture/adrs/` nor
`docs/architecture/diagrams/`. Under the fail-closed contract those are unresolvable roots,
so registering the pass ahead of the scaffolding would have blocked every commit in every
fresh install — the guard would have shipped as a denial of service on new adopters. So the
order is scaffold, register, re-run: a new `build_architecture_namespace_scaffolds` phase
creates the roots, the collection is confirmed to pass with nothing excused, and only then
is the hook wired in.

**What this entry does not claim.** Two criteria in scope were reverted to `work_status:
todo` after an adversarial review, and are recorded as such in the store:

- `GE-122d-1` — the authoring-stage check is absent from the hooks wired in
  `settings.json`, so nothing invokes it. Its stage-disagreement defect is fixed here (the
  authoring stage no longer reports clean where the commit stage fail-closes), but a fixed
  behaviour nothing calls is not a satisfied criterion.
- `BP-900h-6` — the use-the-install step is not reachable from CI.

Both were briefly marked done on the strength of passing covers-tagged tests. Those tests
established that the modules work when called; neither established that anything calls
them. That is the copy tier standing in for the reachability tier, and it is the reason two
new criteria — `BP-900h-6-i` and `BP-900h-6-ii` — now carry explicit reachability clauses
asserted against the command in the on-disk workflow file rather than against a module.

**Also here.** The authoring hook resolves its shared module by walking ancestors rather
than a fixed two-level hop, so all three deployed copies import correctly — the
`gemini/hooks/` copy previously raised `ModuleNotFoundError`. A failed module load no
longer strands a half-initialised entry in `sys.modules`. And the `subprocess.run` at
`scripts/ci/_use_install_step.py` is wrapped per the repository error-handling policy.
