---
title: "A kind of file the size gate never looked at is no longer reported the same as one that passed"
date: "2026-09-14"
time: "13:40"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "The file-size gate covered Python and SQL and said nothing about anything else, so a commit full of TypeScript passed in a way indistinguishable from having been checked. Every run now states which kinds of file it measured and which staged kinds it did not, derived from the configured scope rather than written into the code, and the scope itself widens to cover JavaScript, TypeScript, TSX, ESM and shell."
description: "check_file_size.py gains _classify_staged_extensions() and _print_scope_declaration(), both deriving the answer from CHECKED_EXTENSIONS so the declaration cannot drift from the enforcement. Scope widened to the set GE-127c-1's it_requirements pin: .py 400, .sql 600, .js 1000, .mjs 1000, .ts 400, .tsx 400, .sh 400, each with an explicit limit so none silently inherits the default. .md stays out, governed by check-doc-length, and the now-unreachable .md branch of the dividing advice is deleted rather than left as dead code that reads like coverage. One test descriptor was rewritten: its before/after demonstration read the real production config for the before arm, which this AC changes — both arms are now pinned by the test. The widened gate then refused this AC's own 579-line test file, which was split into four rather than exempted."
commits:
  - 5884dd778
breaking: false
---

## Entry

### Silence meant two different things

The size gate covered `.py` and `.sql`. For every other kind of file it said nothing at
all — and nothing is exactly what it says about a covered file that is within its limit.
So a commit full of `.tsx` passed, and that pass was indistinguishable from having been
checked.

Every run now states both: the kinds it measured, and the staged kinds it did not. A kind
outside scope is **named as not measured** rather than omitted. Both sets are derived from
`CHECKED_EXTENSIONS`, so the declaration cannot drift away from the enforcement — which is
the whole reason the declaration is worth having.

Scope widens at the same time, to `.py` 400, `.sql` 600, `.js` 1000, `.mjs` 1000, `.ts`
400, `.tsx` 400, `.sh` 400. Every entry carries an explicit limit so none silently
inherits the default. `.md` stays out — it is `check-doc-length`'s subject — and the
now-unreachable `.md` branch of the dividing advice is deleted rather than left as dead
code that reads like coverage.

### The test that could not be satisfied

The build halted on the descriptor demonstrating that scope is config-driven. Its
before/after pair ran the "before" arm against the **real production config**, asserting
that config does not carry `.sh` — while this same AC pins `.sh` into it, and a sibling
descriptor asserts it must be there. Two descriptors, mutually exclusive demands on one
file.

The obvious fix was to swap `.sh` for an extension permanently out of scope. That was
rejected: it preserves the actual defect, because the before arm would still inherit
whatever production says and would break again the day that extension is pinned in. **The
coupling was the bug, not the choice of extension.** Both arms are now pinned by the test,
so it demonstrates exactly what it claims — same repo, same staged files, two
configurations differing in one entry — and is immune to the real scope moving either way.

Pinning it exposed a second defect in the same descriptor. The before assertion used a
helper that only looks for the word-stem "measur" near the extension, so it could not
distinguish *measured* from *explicitly not measured* — and returned true on the correct
production line. Switched to the negative helper a sibling descriptor had already
established for that exact claim.

Non-vacuity was proven by execution: making the classifier use a hardcoded extension set —
precisely the defect the descriptor exists to catch — drove it red, and the production file
was restored byte-identical.

### The gate refused its own test file

`test_ge_127c_1.py` came to 579 counted lines against the 400 limit, so the commit landing
the widened scope was blocked by the widened scope.

Split into four files grouped by what each descriptor proves, plus a shared fixture module
— 174 / 96 / 152 / 53 / 193 counted. Not exempted: an exemption here would have been the
gate's first client arguing itself out of it.

### Verification

All under `AC_ENFORCE_STRICT=1`, without which a failure on a not-yet-done AC is downgraded
to `xfail`:

- seven `GE-127c-1` descriptors — passed, confirmed by name
- `unit_tests/commit_guardian/` — 1452 passed, 4 skipped, 1 xfailed, run twice, matching
  the pre-split baseline exactly
- AC store — `OK: all 470 AC YAML files are valid.`
