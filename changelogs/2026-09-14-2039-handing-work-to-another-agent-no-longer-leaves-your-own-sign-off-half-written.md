---
title: "Handing work to another agent no longer leaves your own sign-off half-written"
date: "2026-09-14"
time: "20:39"
type: manual
components:
  - agent_registry
summary: "An agent that hands work to a colleague was told only to change one word in its status comment, so it changed that word, updated half its record, and moved on — leaving the other half saying the opposite. A drive stopped dead on the contradiction and four queued pieces of work sat behind it until someone repaired the record by hand. The instructions that produce that half-written record now spell out, in each place they appear, exactly what a handoff does and does not excuse you from."
description: "Four sections across two agent templates instructed a handoff purely as substituting (status: handoff) for (status: ok) plus a handoff_target field, never restating the signoff skill's Three-Place Parity Rule. python-coder consequently set agents.python-coder: signed_off in frontmatter and wrote a correct handoff comment while leaving '- [ ] python-coder' unchecked in ## Sign-offs. Amended templates/agents/python-coder.md (## Test Delegation, ## Contract-Shrinkage Guard) and templates/agents/test-writer.md (Rule 2, Rule 4) — additively, 12 and 19 insertions, zero deletions — so each names the three surfaces still owed and states that the sole relaxation is the RECEIVING agent's task section. Covered by unit_tests/commit_guardian/test_handoff_signoff_completeness.py, which derives both sides from templates/agents/*.md, resolves the smallest enclosing section around each handoff instruction, and asserts that same section restates the frontmatter and Sign-offs obligations; a second test guards against the scan matching nothing. Mutation-proven red/green/red/green under AC_ENFORCE_STRICT=1. New AC AR-200a-2 under AR-200a."
commits:
  - aed3781be
breaking: false
---

## Entry

### One word changed, half a record written

The `signoff` skill has always required a phase agent to record its outcome in
three places at once: the frontmatter `agents:` map, its own line in the
`## Sign-offs` checklist, and its own task checkboxes. Four sections across two
agent templates described handing work to a sibling as doing one thing —
swapping `(status: handoff)` for `(status: ok)` and adding a `handoff_target`
field. Nothing in those sections said the three-place rule still applied.

Each of those sections is read on its own, because each is the procedure for
exactly its own situation. An agent following one of them learns that a handoff
differs from an ordinary sign-off in a status tag and a JSON field, and
reasonably concludes that is the whole of it.

It is made worse by the only place the parity rule mentions handoff at all,
§1.5 step 3, which is an *exemption*: tasks in OTHER agents' sections may stay
unchecked. Generalise from that single relaxation and you arrive at "the handoff
path is lighter," which is the wrong inference and precisely the one that was
drawn.

### What it cost

On 2026-09-14, driving ticket 01 of EPIC-WorkIsOnlyEverMarkedFinishedThroughThe,
python-coder took the Test Delegation handoff path. It set
`python-coder: signed_off` in the frontmatter and wrote a correct
`(status: handoff)` comment, and left `- [ ] python-coder` unchecked. Its own
comment names the surface it updated twice — "python-coder's own **frontmatter**
status is flipped to signed_off" — and never mentions the checklist.

The completion write refused the ticket. The epic halted at batch one and its
four remaining tickets stayed blocked until the record was repaired by hand.

The refusal was correct, and worth dwelling on: the agent that refused was
applying `BO-400e-1` — a close is checked against the ticket's own record, not
against a caller's claim about it. It declined to accept "only commit is
outstanding" because the record itself still showed a phase unchecked. Nothing
downstream was broken. What was broken sat upstream, where an agent had been
told to produce a record it could not make consistent.

### The scope was four, not one

The first diagnosis said one file, from `grep -ln "## Test Delegation"
templates/agents/*.md`, which returns python-coder.md alone. That was the wrong
query. The defect is not that heading — it is any section instructing a handoff.

The rule-level test found four the first time it ran: `## Test Delegation` and
`## Contract-Shrinkage Guard` in python-coder.md, and `Rule 2 — Consumer
enumeration` and `Rule 4 — Test-repair commits` in test-writer.md. test-writer
is the agent python-coder hands off *to*, so both ends of that handoff carried
the same gap and it could have recurred travelling back the other way. The AC's
`n_location_rule` is corrected from 1 to 4, with the bad query recorded in it so
the mistake is not repeated.

This is the argument for writing the rule-level test first rather than a
phrase-match: the test found three-quarters of the problem that the human
diagnosis missed, before a line of the fix was written.

### Why the test is not a grep

A prompt has no execution path, which tempts an assertion like `"atomic sign-off"
in python_coder_md`. That passes on any wording containing the phrase and
protects only the file already fixed.

Instead the test scans every `templates/agents/*.md`, locates each section
instructing a handoff, resolves the *smallest enclosing section*, and asserts
that same section restates both the frontmatter update and the Sign-offs entry.
Both sides derive from the templates on disk, so a newly added phase agent with
the same gap fails without anyone editing the test — the shape `AR-200a-1`
established for the sibling question of whether a template *can* perform the
write.

The section scoping is load-bearing rather than tidiness: python-coder.md
already carried a correct three-place description in a different section, so a
whole-file search would have reported green against the broken templates.

A second test asserts the scan located at least one handoff section. Without it,
a scanner whose pattern matched nothing would satisfy the rule vacuously — the
silent-no-op failure this repository has hit three separate times in its own
defences.

### Verification

- Red first, naming all four offending sections; green after; red again with
  both templates stashed; green again on restore. All under
  `AC_ENFORCE_STRICT=1`, without which a failing test covering a not-yet-done AC
  is downgraded to xfail and shows a false green.
- `unit_tests/commit_guardian`: 1471 passed, 2 failed, neither from this change.
  `test_precommit_safety_net`'s routing-parity case fails identically with these
  templates stashed, so it is pre-existing. `test_ge_127a_1` passes in isolation
  both with and without the change — its suite failure is an ordering artefact
  of that cold-process test.
- Every pre-commit hook passed. No gate was skipped.

The fix adds an instruction; it does not relax the rule. The parity guard is
what caught this, and the record's internal consistency is what the BO-400
family exists to make authoritative.
