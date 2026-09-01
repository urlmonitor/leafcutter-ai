---
title: "The GE-120 records now say what actually shipped, and a documented bypass that reads the wrong commit"
date: "2026-09-01"
time: "09:40"
type: manual
components:
  - ac_store
  - commit_guardian
  - testing_quality
summary: "Reconciles the GE-120 acceptance-criteria store and ticket records with the work merged in PR #630, tags a reachability proof that existed but was never machine-claimable, and files a check-feedback-id defect whose escape hatch reads the previous commit's message."
description: "Bookkeeping with evidence, plus two defects found while doing it. GE-120e-1 and GE-120e-2 shipped in PR #630 (squash 28f0ce590) but were left work_status: todo, so the acceptance-criteria store — the surface tests, test-writer, ac-validator and the xfail plugin all read — said unbuilt for code that is on main. Both are now done, with implemented_by extended to the real modules and test files. The evidence is stated rather than asserted: test_ge_120e_1.py carries six covers-tagged tests and test_ge_120e_2.py carries ten, all passing, and validate_ac_schema.py reports all 457 guardrail-engine records valid. Ticket 12 (GE-120c-1) closes, its only outstanding phase having been commit, which is fa539b931 and merged. Tickets 01, 28 and 30 are deliberately NOT closed and each records why in its own body: their code is merged and their acceptance criteria are done, but phases remain unrun — ticket 01's documentation-verifier is still failed, its parse blocker fixed but never re-run, so nothing has actually verified the doc; tickets 28 and 30 had ac-validator and ac-fulfillment-gate skipped by the cross-agent protocol when pr-reviewer blocked, so no AC-coverage gate has ever passed on them. Flipping those three because the blocker is resolved would assert a verification that never happened, which is the phantom-done shape this epic exists to prevent, committed in the epic's own bookkeeping. Each note names the exact re-dispatch that would close it truthfully. Two guardrails then caught things during the commit itself. check-proof-promise-claim refused the change because GE-120a-1 promised a reachability proof that no test claimed; the proof turned out to exist — test_ge_120a_1_reachable_from_entry_point runs the real entry point as a subprocess against a genuinely corrupted prerequisite — but carried no '# angle: reachability' tag, so a real piece of work was invisible to the machine that was supposed to confirm it. The tag is added to the existing test rather than a new test being written or the promise relaxed. Separately, check-feedback-id refused the change and advertised its own [NO-FEEDBACK-CHECK] escape hatch, which then did nothing in either the commit body or the subject line. The cause is filed as KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message: the hook's fourth input source reads COMMIT_EDITMSG at the pre-commit stage, but git does not write that file until the commit-msg stage when invoked with -m, so it holds the PREVIOUS successful commit's message — confirmed directly by inspecting the file mid-refusal, where it showed the subject of the commit that had landed before it. The hook's own comment states the opposite as its operating assumption. The unusable bypass is the lesser half: because the file holds the previous message, a commit whose predecessor legitimately used the token is silently skipped although its own message never asked for one, so the control is off by exactly one commit in both directions, and a spurious skip of a feedback-traceability gate is a silent hole rather than a visible annoyance. The four new ticket comments are consequently written outside the sign-off heading grammar rather than carrying invented feedback-ids — the honest form regardless of the hook, since no agent ran and no feedback was submitted for them. One skip is recorded and auditable: check-predone-scope, the documented case in KI-CG-20260831-1933 which main merged the same day, where the hook compares the whole branch diff against the single ticket transitioning to done and so refuses ticket 12's closure over a file belonging to ticket 01."
breaking: false
---

## Entry

### Store reconciled to reality

| Record | Before | After | Evidence |
|---|---|---|---|
| `GE-120e-1` | `todo` | `done` | 6 covers-tagged tests passing; merged in `28f0ce590` |
| `GE-120e-2` | `todo` | `done` | 10 covers-tagged tests passing; merged in `28f0ce590` |
| Ticket 12 | `todo` | `done` | only phase outstanding was `commit` — `fa539b931`, merged |

`validate_ac_schema.py`: OK, all 457 guardrail-engine records valid.

### Deliberately left open

Tickets **01**, **28** and **30**. Merged and their ACs are done, but `documentation-verifier`
(01) and `ac-validator` / `ac-fulfillment-gate` (28, 30) **never ran** — the latter pair
skipped by the cross-agent protocol when `pr-reviewer` blocked. "The blocker is resolved" is
not "the coverage gate passed", and only the second justifies `status: done`.

### Caught by the guardrails, mid-commit

- **`check-proof-promise-claim`** — `GE-120a-1`'s promised reachability proof existed but was
  untagged, so it could not be claimed. Tagged the real test.
- **`check-feedback-id`** — filed
  `KI-CG-20260901-feedback-id-escape-hatch-reads-the-previous-commit-message`.
