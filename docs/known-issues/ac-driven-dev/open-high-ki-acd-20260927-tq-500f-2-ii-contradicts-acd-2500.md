---
title: "KI-ACD-20260927-tq-500f-2-ii-contradicts-acd-2500 — an approved, unbuilt AC tells llm-expert to make the IT PO write must_catch, which the approved ACD-2500 tree assigns to a code-aware test-designer"
description: "high — two readiness: approved AC trees give the same duty to different agents. Building TQ-500f-2-ii as written puts must_catch authoring in an agent that may not read source, and ACD-2500 then has to take it out again. Verified by reading both trees on main at 93bd801c."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - ac_driven_dev
  - testing_quality
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-2-ii.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/ACD-2500.yaml
  - docs/analysis/2026-09-25-test-writers-prove-failure-not-discrimination.md
---

# KI-ACD-20260927-tq-500f-2-ii-contradicts-acd-2500 — an approved, unbuilt AC tells llm-expert to make the IT PO write must_catch, which the approved ACD-2500 tree assigns to a code-aware test-designer

- **Severity:** high. Nothing is broken yet. But `TQ-500f-2-ii` is `readiness: approved`, `work_status: todo`, `assigned_agent: llm-expert`, so the next build picks it up. Built as written, it puts must_catch authoring in the IT PO, which ACD-2500 forbids. The two trees then contradict each other in shipped prompts, not just on paper.
- **Status:** open. No AC. **Do not build `TQ-500f-2-ii` as written.**
- **Occurrences:** 1 (found in review, 2026-09-25, after PR #911 landed the schema half)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-27
- **Where:** `docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-2-ii.yaml` and the `ACD-2500` tree under `docs/acceptance-criteria/ac-driven-dev/ACD-2500-right-job-right-agent/`.

## The conflict, quoted

`TQ-500f-2-ii` (L3, `depends_on: [TQ-500f-2]` only, `:33-34`) targets the IT PO:

> `:15` Given the technical enricher (IT-PO) enriches three requirements in one pass —
> `:21` When it authors each requirement's test plan,
> `:22` Then R1's guarding test entry carries must_catch naming "revert the fix" ...
> `:36` `- path: templates/agents/it-po.md`
> `:39` relevance: "The enricher that authors test_spec; its instructions gain the must_catch duty for bug-fix and gate requirements."
> `:51` `- Edit the source template templates/agents/it-po.md only, never the deployed copies.`

The approved ACD-2500 tree says the opposite:

- `ACD-2500.yaml:31-35` (doc_links): *"That statement can only be written by something that sees the code, so it needs the code-aware test-design step this goal creates (ACD-2500c). Any L0 authored for that analysis should list ACD-2500 in depends_on."*
- `ACD-2500.yaml:81-83` (notes): *"SEQUENCING IS A HARD CONSTRAINT. This goal must land before the discrimination / must_catch work from the 2026-09-25 analysis, because that work's field lives in the test design ACD-2500c relocates."*
- `ACD-2500b.yaml:14-18`: *"Planning records which outcomes need a test and why, nothing more. ... It no longer writes test designs it has no way to ground in the code."* `ACD-2500b-1.yaml` Then clause: *"the record carries no test design written by the planner: no test names, target directories, frameworks, test types or test angles"*.
- `ACD-2500c.yaml:15-20`: *"Test designs come from a step that can see the code under test. ... This is where future guidance on which wrong implementations a test must catch will be recorded."* `:29` (doc_links): *"The planned must_catch field lands in the test design this L1 produces."*
- `ACD-2500d-5.yaml:18-26`: one new code-aware agent (working id `test-designer`, `:69`) writes the test design, and *"the technical planner's profile still declares no source-code access."* `:75` defers *"the optional Opus sub-call for must_catch ... until must_catch exists"*.

The IT PO's own template confirms it cannot do this job: `templates/agents/it-po.md:21` (`# No source code access`) and `:104-106` (*"You NEVER READ: Source code ... Test files"*). `TQ-500f-2-ii`'s R1 asks it to name *"the condition or input involved"* in a wrong version. That needs the code.

The dependency ACD-2500 asks for is missing. `TQ-500.yaml:28` is `depends_on: []`, and `TQ-500f.yaml:24-25` depends only on `TQ-500`. `TQ-500f` itself links the analysis (`:27`).

## State on main (93bd801c)

- PR #911 (merged 2026-09-27) added the `must_catch` schema field (TQ-500f-2 / -2-i). `TQ-500f-2.yaml:155` scopes out *"who fills the list (TQ-500f-2-ii)"*. The schema half does not conflict with ACD-2500, because it only adds a field.
- `templates/agents/it-po.md` has no `must_catch` text yet (grep: 0 hits), so the prompt half is unbuilt.
- `templates/agents/test-designer.md` does not exist yet (ACD-2500d-5 is `work_status: todo`).
- `TQ-500f-2.yaml:11` still reads `work_status: todo` although #911 claims it. Not investigated here.

## Detection

Read `TQ-500f-2-ii.yaml` and `ACD-2500c.yaml` / `ACD-2500d-5.yaml` side by side. No gate compares `assigned_agent` or `doc_links` targets across trees for contradictory ownership. Both pass `check-ac-schema` individually.

## Workaround

Leave `TQ-500f-2-ii` unbuilt. When pointing `/fast-lane-build` or `/build-feature` at anything in `TQ-500f`, exclude it. `TQ-500f-2.yaml:161-164` already notes that the fast lane refuses the llm-expert member.

## Suggested fix

1. Amend `TQ-500f-2-ii` (and `TQ-500f-2`'s `covered_by`/notes if its wording names the IT PO) with an `amended_by` record. Add `ACD-2500c` and `ACD-2500d-5` to `depends_on`. Retarget the prompt edit from `templates/agents/it-po.md` to `templates/agents/test-designer.md`, and change "technical enricher (IT-PO)" in the Given clause to the code-aware test-design step.
2. Add `ACD-2500` to `TQ-500`'s `depends_on`, as ACD-2500's L0 note requests. Otherwise the ordering constraint stays prose-only.
3. Keep the "declared judgement, not a classifier" clause. It still applies, now to the test-designer.

**Pattern:** two trees planned the same day from the same analysis. Each is internally consistent, and one quietly assigns a duty the other takes away. The cross-reference exists only in prose (`doc_links.relevance`, `notes`), which no gate reads.
