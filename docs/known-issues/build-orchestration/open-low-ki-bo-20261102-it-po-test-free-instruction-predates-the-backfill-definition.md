---
title: "KI-BO-20261102-it-po-test-free-instruction-predates-the-backfill-definition — the technical planner is still told a test-free reason says 'why no executable test can observe it' and that prompt wording is test-free, which BO-2500a-8-iv's definition and the 2026-11-01 prompt-class decision replaced"
description: "medium — templates/agents/it-po.md section 2.7 (the `test_required: false` paragraph, built by BO-2500a-8-ii) gives `change_target: prompt` as an example of work with no executable behaviour and asks the reason to say why no executable test can observe the deliverable. On 2026-11-01 the user decided that a deliverable has observable behaviour whenever a test could fail for a reason outside the page's own text (BO-2500a-8-iv), and that prompt records are proved by eval cases with test_required true. The planner will keep declaring new prompt records test-free, and keep writing reasons by the older, looser standard. No check catches either."
type: reference
category: reference
status: active
created: '2026-11-02'
last_updated: '2026-11-02'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-ii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-iv.yaml
  - docs/reference/test-free-declarations.md
---

# KI-BO-20261102-it-po-test-free-instruction-predates-the-backfill-definition — the planner's test-free instruction disagrees with the backfill's definition and the prompt-class decision

> Filed 2026-11-02. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Every new record the technical planner plans is affected. A prompt
  record is declared test-free, which the user decided against on 2026-11-01, and a reason is
  written by a standard the user set aside. The commit-time checks refuse a missing or
  duplicated reason (BO-2500a-8-i, BO-2500a-8-v) but cannot judge whether a reason is
  honest, so nothing stops the drift. It is not high: the declaration and its reason are in
  plain sight on the record, a reviewer can catch them, and nothing breaks at run time. It is
  not low either: each such record adds to the pile the backfill has just cleared.
- **Status:** open. No AC. Draft requirement below.
- **Occurrences:** 0 observed records so far; found by reading, at the close of the
  BO-2500a-8-iv backfill (2026-11-02).
- **First seen:** 2026-11-02 · **Last seen:** 2026-11-02
- **Where** (branch `feature/backfill-test-rationales`, base `e4849a9bb`):
  - `templates/agents/it-po.md`:517-528, section 2.7, the `test_required: false` paragraph.
    It says to write the declaration "when the AC genuinely produces no executable behaviour
    (for example `change_target: prompt` or `docs`, a prompt- or docs-only change)", and
    that the reason "names what the deliverable is and why no executable test can observe
    it".
  - `templates/agents/it-po.md`:832-833, self-review item 12: "(or `test_required: false`
    with its own `test_rationale` for prompt- or docs-only work)".
  - The deployed copy `.claude/agents/it-po.md`:494 carries the same text.
  - Source of the wording: BO-2500a-8-ii's criteria ("it names what the deliverable is and
    why no executable test can observe it"; "a requirement whose change is only a guide or
    only the wording of an agent instruction"). BO-2500a-8-ii is done, so the instruction
    matches its own record. The disagreement is between two records.

## Symptom

The user's decisions of 2026-11-01, recorded on BO-2500a-8-iv, say:

1. A deliverable has behaviour a test can observe whenever a test could fail for a reason
   outside the page's own text: by comparing it to a real artefact, or by running its
   example through a real hook or step. A check that only matches words on a page or the
   shape of a diagram does not count.
2. Records with `change_target: prompt` get no reason. They have `test_required: true` and
   are proved by eval cases, as BO-2500a-8-ii itself was.
3. A reason may cover a record's prose clauses only, and names the judgement no test can
   make and what verifies that judgement instead.

The planner's instruction says the opposite on 2 (prompt work is the example of test-free
work). On 1 and 3 it asks for a different reason, "why no executable test can observe it",
with no definition of observing. In the backfill, 15 of the 30 prose records (3 in batch A,
12 in batch B) turned out to tie a label, name or value to a real artefact. The old wording
would have let them stay test-free.

## Detection

A record planned after 2026-11-01 that has `change_target: prompt` and
`test_required: false`. Or a new `test_rationale` that claims no test can observe a
deliverable which names a real file, hook, label or value.

Baseline, measured 2026-11-02 by loading every record (active records, `change_target`
prompt, `test_required` false): 37 records. 20 are done (19 with a reason, 1 without). 17
are unfinished and already carry a reason (15 todo, 2 in_progress). The 17 were outside
the backfill's population, which took only records with no reason, so the prompt-class
decision did not reach them. Whether it should is a question for the user. A new record
on top of these 37 is an occurrence of this issue.

## Workaround

When reviewing a record the technical planner wrote, apply BO-2500a-8-iv's definition and the
prompt-class decision by hand: turn a prompt record to `test_required: true` with an eval
proof, and refuse a reason whose deliverable could be compared to a real artefact.

## Draft requirement

BO-2500a-8-ii is done and its criteria hold the old wording, so the fix needs a new record
(or an approved amendment). Draft, for the product owner and business analyst to place:

```
Given the technical planner's instructions for declaring a requirement test-free,
When the planner follows them for a requirement,
Then they state that a deliverable has behaviour a test can observe whenever a test
  could fail for a reason outside the page's own text, by comparing the deliverable
  to a real artefact or by running its example through a real hook or step, and that
  a check matching only words on a page or the shape of a diagram does not observe it,
And they direct the planner to declare a requirement test-free only when no test can
  observe its deliverable by that definition,
And they state that a requirement with change_target prompt is not declared test-free:
  it gets test_required true and is proved by an eval case,
And they no longer give prompt or agent-instruction work as an example of a test-free
  change,
And they state that the reason names what the deliverable is, the judgement no test can
  make about it, and what verifies that judgement instead, and that it may cover the
  record's prose clauses only,
And the self-review checklist item on test intent states the same rule,
And a planner run on a requirement with change_target prompt, with these instructions
  loaded, writes test_required true and no test_rationale, where the same run with the
  current instructions writes test_required false with a reason.
```

Owner: llm-expert (a prompt change), proved by an eval case as BO-2500a-8-ii was.
`docs/reference/test-free-declarations.md` should be checked for the same wording when this
is built.

**Pattern:** an instruction built faithfully to its record, left behind when a later record's
decision redefined the record's key term. The instruction is correct by its own record and
wrong by the store.
