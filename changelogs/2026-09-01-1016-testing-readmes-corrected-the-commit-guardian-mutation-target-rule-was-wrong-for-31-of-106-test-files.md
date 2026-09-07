---
title: "Testing READMEs corrected — the commit-guardian mutation-target rule was wrong for 31 of 106 test files"
date: "2026-09-01"
time: "10:16"
type: manual
components:
  - testing_quality
  - security_scanner
summary: "Fixed four inaccurate claims in the two documents that teach engineers how to test this repository — no test or production code changed — including one rule that, if followed as written, silently injects a fix into a copy of the code the test never actually runs."
description: "Single commit 55c79b985 corrects tests/README.md and unit_tests/README.md. (1) unit_tests/README.md section 1a stated an absolute rule (\"mutate scripts/commit_guardian\") that is wrong for 31 of the 106 files in unit_tests/commit_guardian/: 28 root their hook path at scripts/commit_guardian only, 31 at templates/scripts/commit_guardian only, and 14 reference both; the absolute rule is replaced with a grep-the-anchor-then-branch procedure, and the same wrong claim in tests/README.md is corrected too. (2) tests/README.md labelled a plain pytest invocation \"everything CI runs\"; corrected to include AC_ENFORCE_STRICT=1, matching ci.yml. (3) both READMEs gain the previously-missing \"python scripts/build.py --target-dir .\" step, without which scripts/commit_guardian imports fail at collection and --continue-on-collection-errors hides it. (4) the tests/ inventory is rewritten to name tests/testing_quality/ and the top-level test modules it previously omitted. A .security-allowlist glob suppression was added for the date-and-slug known-issue ids these READMEs cite."
commits:
  - 55c79b985
breaking: false
---

## Entry

`tests/README.md` and `unit_tests/README.md` are guidance on how to test in this
repository — documents whose entire purpose is preventing false greens. A code review
verified their claims against the repo and found four that do not hold; two of them would
actively cause the failure mode the documents warn about. This commit corrects all four.
It changes no test and no production code.

### The mutation-target rule was wrong for a third of the suite

`unit_tests/README.md` §1a asserted "Tests import the build output" and gave an absolute
rule: mutate `scripts/commit_guardian/…`. Measured across all 106 files in
`unit_tests/commit_guardian/`:

| root | file count |
|---|---|
| `templates/scripts/commit_guardian/` only | 31 |
| `scripts/commit_guardian/` only | 28 |
| both (drift/parity tests) | 14 |

For the 31 that only load the template copy, following the stated rule injects a mutation
into a copy the test never loads — a green run that reads as a dead negative control, the
same inverted false green §1a exists to prevent. The absolute rule is replaced with a
procedure: grep the file's own `_HOOK_SCRIPT` / `_HOOK_DIR` / `_COMMIT_GUARDIAN_DIR` anchor,
branch on which literal it uses, then confirm the injection actually landed. The same wrong
claim, repeated in `tests/README.md`'s short-version bullet, now points at the corrected
§1a instead.

### "Everything CI runs" was not what CI runs

`tests/README.md` labelled a plain `python -m pytest unit_tests/ tests/ -q` as "everything
CI runs". `ci.yml` sets `AC_ENFORCE_STRICT: "1"` first, so the label handed a developer an
xfail-masked local run and implied CI's green is the masked one when CI's is the strict one.
Command and label are both corrected.

### The build step was missing from both Running sections

Neither Running section mentioned `python scripts/build.py --target-dir .`.
`scripts/commit_guardian` is untracked, build-created output (ADR-016), so on a fresh clone
or worktree the documented commands fail at import — and
`--continue-on-collection-errors` turns that into a green-looking but silently truncated
run. Added to both files with the rationale.

### The `tests/` inventory misrouted the tests it is about

The inventory listed four subdirectories and omitted `tests/testing_quality/` and the
top-level test modules, so its own "put yours beside the existing ones" advice sent authors
to the wrong place. Rewritten to name `testing_quality/` and describe the top-level modules
structurally rather than enumerate them, so it does not rot as files are added.

### One suppression, added as a glob

`check-secrets` flagged the date-and-slug known-issue ids these READMEs cite (e.g.
`KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy`) as `ENTROPY_HIGH`. A false
positive this convention will keep producing. Suppressed in `.security-allowlist` by glob
(`unit_tests/README.md:*`, `tests/README.md:*`) rather than by line number, since these are
prose files that grow and a pinned line would silently stop suppressing the finding it was
added for.

### Why this entry exists

`tests/README.md`, `unit_tests/README.md`, and `.security-allowlist` are all releasable
paths not exempted by `scripts/release/check_changelog_presence.py`, so the `Changelog
entry present` required check would otherwise block this PR.
