---
title: "Being looked at leaves your work untouched, and only an objection stops you"
date: "2026-09-09"
time: "11:20"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "Every check the commit runner delegates to is now wrapped so that a check whose job is to judge cannot leave anything behind in your working copy, while a check whose job is to fix has its corrections folded into the same commit instead of tripping a generic refusal; the rule binds by the role a check declares, an unlisted check is judging by default and can never be excused, and the test proving no exemption can excuse it now exercises that by shipping one and watching it be ignored."
description: "run_hook.py wraps every delegated check in _run_delegated_check(), snapshotting git status --porcelain immediately before and after that check's own subprocess run so it isolates what the check changed rather than the commit's already-staged diff. Role resolution via _is_fixing_role() treats commit_guardian.json's tier field as authoritative, falls back to the transform_ naming convention, and defaults to judging so an unlisted check is never exempt. Judging-check side effects are reverted (git checkout for an altered tracked path, delete for a new untracked one); fixing-check alterations are staged. Implemented entirely in run_hook.py because the frozen fixtures copy only that file. Also rewrites one GE-120g-1-i descriptor that could never have passed: it scanned filenames for 'exempt'/'waiver' and matched _drift_exemptions.py, present since PR #621 for an unrelated drift-hash concern. Replaced with a behavioural test that ships an exemption-shaped manifest entry and asserts it is ignored, checking both git status AND the audit log's absence from HEAD — because a wrongly-honoured exemption gets staged into the commit and leaves status clean."
commits:
  - f40221fa0
breaking: false
---

## Entry

### The gap: a check that changes your files while deciding whether to allow them

`GE-120` has always been about whether a check's *answer* is right. This is the
first criterion in that tree about a check whose answer was right and did not decide
the outcome — the gate printed `PASSED` and the commit was refused anyway, because
the act of checking had altered the tree and pre-commit's own generic "files were
modified by this hook" rule fired.

`run_hook.py` now wraps every delegated check. It snapshots `git status --porcelain`
immediately before and after that check's own subprocess run, so it sees exactly what
the check changed and never mistakes the commit's already-staged diff for a side
effect. Then it acts on the check's **declared role**: a judging check's alterations
are undone, a fixing check's are staged so they land in the same ordinary commit.

The default matters more than the mechanism. Role comes from `commit_guardian.json`'s
`tier` field when the check is registered, falls back to the `transform_` naming
convention, and otherwise **defaults to judging** — so a brand-new check nobody has
listed anywhere is bound from its first run rather than silently exempt.

### A test that could never have passed

The build halted on `test_ge_120g_1_i_no_exemption_mechanism_lets_a_judging_check_off`.
It asserted, by scanning filenames, that nothing under
`templates/scripts/commit_guardian/` has "exempt" or "waiver" in its name.
`_drift_exemptions.py` matches — and has since PR #621, where it was added for
exempting an artifact from a *drift-hash comparison*, an unrelated and older concern.
The assertion was false the day it was written. Its own comment said the directory had
been verified; it had not been.

Narrowing the scan was the obvious fix and the wrong one: a filename substring match
cannot tell "no exemption mechanism exists" from "one exists in a file called
`config.py`". That is the grep-shaped test this repo's own conventions forbid as
coverage.

### What replaced it, and why it is not vacuous

The descriptor now builds a real temporary repository, writes a `commit_guardian.json`
carrying a plausible exemption-shaped entry naming a judging check, has that check
write a tracked audit log, performs an ordinary commit, and asserts the alteration is
still undone.

It checks that two ways, and the second is the interesting one. A first draft asserted
only on `git status` — insufficient, because an exemption that **is** wrongly honoured
causes the check's alteration to be *staged into the commit*, which also leaves status
clean and is indistinguishable from a correct revert. So the test also asserts the
audit log is absent from disk and from `HEAD`.

Non-vacuity was proven by executing it rather than argued: `_load_manifest_tiers` was
temporarily patched to honour an `"exempt": true` field, the test went red — the log
survived and appeared in `HEAD` — and the patch was reverted and confirmed gone.

`_drift_exemptions.py` is untouched. It has four production consumers, and renaming it
to satisfy a test would have been scope creep with real regression risk.

### Verification

All under `AC_ENFORCE_STRICT=1`, without which a failing test on a not-yet-done AC is
downgraded to `xfail` and shows a false green:

- `test_ge_120g_1.py` + `test_ge_120g_1_i.py` — 5 passed
- `fast_lane verify_green_and_coverage` — `{"green": true, "coverage_ok": true, "uncovered_ac_ids": [], "failing_tests": []}`
- AC store — `OK: all 469 AC YAML files are valid.`

Size was checked against the gate's own rule rather than raw line count:
`count_content_lines` measures `run_hook.py` at 231 against the 400 limit, where
`wc -l` reports 418 — the ratchet strips docstrings and comments, so the raw figure is
not the binding one.
