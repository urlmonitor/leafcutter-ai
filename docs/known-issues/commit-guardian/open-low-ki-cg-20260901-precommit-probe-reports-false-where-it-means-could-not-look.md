---
title: "KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look"
description: "KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/scripts/commit_guardian/verify_precommit_active.py` — the `--json`
  payload assembled in `run_checks()`, and the `check_c_git_hook` / `check_hook_freshness`
  branches that feed it

**Symptom.** The probe that answers "are pre-commit hooks actually live in this working tree"
returns a definitive `false` when the honest answer is *"I could not look."* Run from the
workspace parent, which is **not** a git repository — the git root is `leafcutter-ai/` one
level down:

```
$ env --chdir=/home/henzeh/projects/leafcutter python3 .../verify_precommit_active.py --json
run_checks: cannot resolve hooks path from /home/henzeh/projects/leafcutter:
  .git not found at /home/henzeh/projects/leafcutter — using default fallback
check_hook_freshness: stat failed: [Errno 2] No such file or directory: '.../.git/hooks/pre-commit'
check_c_git_hook: hook file not found: [Errno 2] No such file or directory: '.../.git/hooks/pre-commit'
{"binary": true, "config": true, "git_hook": false, "canary": true, "failing_checks": ["git_hook"]}
```

**The stderr is exemplary. The JSON is not.** Three diagnostic lines say plainly that the
hooks path could not be resolved and a fallback was used. The machine-readable payload — the
entire point of `--json` — reports `git_hook: false` and lists it under `failing_checks`,
which is the same output a genuinely unprotected worktree produces. A caller parsing the JSON
cannot distinguish *"hooks are not installed"* from *"I was pointed somewhere that is not a
repository."*

**Not a cwd-resolution bug.** `resolve_hooks_path(cwd)` takes the working directory as a
parameter and resolving relative to it is correct behaviour; running the probe from the wrong
directory is operator error. The defect is what the probe *says* about that: it collapses
**indeterminate** into **false** at exactly the layer built for machines.

**Why this matters despite failing safe.** The direction is benign — a false negative provokes
investigation rather than false confidence — so this is medium, not high. But the shape is the
one this repository keeps paying for. `config/verification_flow.schema.json` already models
the remedy: *"an unrun control records state `unverified` rather than omitting the block, so
'we never fed it bad input' is visible in the artifact instead of silent."* A four-value state
exists in the vocabulary; this payload uses two.

There is also a live consumer: `verify_precommit_active.py` check D is what
`precommit_canary.py` exists to feed, and the canary's whole purpose is establishing that
hooks *can* fire in a worktree. A probe that answers `false` for two different reasons makes
that establishment ambiguous.

**Remediation.** Add an indeterminate value to the payload rather than a third boolean — the
vocabulary in `verification_flow.schema.json` already names it. `git_hook` should be able to
report `unverified` with the reason already being printed to stderr, and `failing_checks`
should not list a check that never ran. Anything parsing the payload then distinguishes the
two states without reading stderr.

**How it was found.** A `commit` agent ran the probe as a pre-flight during an unrelated
hand-drive, got `git_hook: false`, re-ran it with `env --chdir=<worktree>` and got
`failing_checks: []`. It flagged the discrepancy rather than accepting either answer. Its own
characterisation — a cwd-sensitivity gap in `resolve_hooks_path()` — was checked against the
running probe before filing and refined to the above: the resolution is fine, the reporting is
not.

**Related.** `KI-CG-034` and the AC-store bare-directory no-op (the same collapse, opposite
direction). `GE-120f` and `GE-126b-5` (the scheduled regime requiring a check to distinguish
never-attempted from attempted-and-passed). `docs/reference/false-green-mechanisms.md` → M9.

**Pattern:** a probe whose human-readable output distinguishes "could not determine" from a
verdict, and whose machine-readable output does not — so the consumer built to act on it is
the one consumer that cannot tell.

---
