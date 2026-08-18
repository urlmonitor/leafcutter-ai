---
title: "fix(ac-store): done-proof gate reads unmasked test outcomes (ACS-200f)"
date: "2026-08-18"
time: "11:20"
type: manual
components:
  - ac_store
summary: "The done-proof gate now runs its verification pytest with AC_ENFORCE_STRICT=1, so it no longer reads an outcome the enforcement plugin downgraded because of the very work_status the gate exists to decide; refusals name the real outcome instead of a generic 'non-passing'."
description: "done_proof._run_pytest_and_parse launched pytest in a subprocess that inherited the environment, and the repo's pytest.ini loads pytest_ac_enforcement into every pytest process. That plugin rewrites a failing test's outcome to XFAIL when the AC named by its '# covers:' tag is not yet work_status: done — and the AC the gate is evaluating is, by definition, still not-done at that moment. The gate therefore recorded XFAIL for a test that genuinely FAILED, naming a cause that sends the operator looking for an xfail marker that does not exist. The child now runs with AC_ENFORCE_STRICT=1, which disables only the enforcement plugin's own not-yet-done downgrade; pytest's native @pytest.mark.xfail and @pytest.mark.skip handling is untouched, so an outcome that is non-passing on its own merits still reports XFAIL or SKIPPED and is still rejected by _classify_outcomes — BO-2500a-2-i is preserved by construction rather than by an exception. Fixing the runner rather than any one call site keeps the tool, the pre-commit hook and the CI gate on one code path so their verdicts cannot drift. Separately, a new _describe_non_passing helper names the actual outcome in refusals: the leaf path had drifted to reporting 'linked test non-passing:' for failed, skipped and xfailed alike, though the three call for different operator actions; both the leaf and composite paths now share the one helper, and a nodeid with no result line reports 'not run' rather than being guessed at. Note for the record: ACS-200f's headline claim — that a genuinely covered AC can never be marked done through the normal path — did not reproduce on main and is not what was fixed. The enforcement plugin only ever rewrites a failing test, so a passing covering test was never masked; this was verified against GE-118b, the AC named in ACS-200f's own reproduction note, temporarily returned to work_status: todo. Merged via PR #468."
pr: 468
commits:
  - 5e16e50f4
---

## Entry

The gate that decides whether an acceptance criterion may be marked done was
reading a verdict that had already been rewritten on the basis of the status it
was about to change.

`pytest_ac_enforcement` downgrades a failing test to XFAIL when the AC its
`# covers:` tag names is not yet done. The gate runs pytest in a child process
that inherits the environment, and the AC under evaluation is always still
`todo` at that instant — so a genuinely **failed** covering test was recorded as
an **xfail**. The refusal was right; the reason given was not.

The child now runs with `AC_ENFORCE_STRICT=1`. That switch turns off only the
plugin's own not-yet-done masking, so an author's `@pytest.mark.xfail` or
`@pytest.mark.skip` still reports XFAIL or SKIPPED and is still refused —
BO-2500a-2-i holds by construction, not by a carve-out.

Refusals also stopped collapsing three different problems into one sentence.
`linked test non-passing:` covered failed, skipped and xfailed alike; fix the
code, un-skip the test, and write a test are not the same instruction.

Worth recording: the symptom ACS-200f describes — that a genuinely covered AC
can never be marked done — **did not reproduce**. The plugin only rewrites
failing tests, so a passing one was never masked. `GE-118b`, the AC named in the
criterion's own reproduction note, marks done cleanly when returned to `todo`.
The defect was real; its stated shape was not.
