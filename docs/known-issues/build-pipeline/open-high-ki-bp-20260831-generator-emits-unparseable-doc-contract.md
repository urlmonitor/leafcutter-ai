---
title: "KI-BP-20260831-generator-emits-unparseable-doc-contract — the ticket generator writes the documentation contract in a shape its own consumer rejects, and every epic has fixed it by hand instead of at source"
description: "KI-BP-20260831-generator-emits-unparseable-doc-contract — the ticket generator writes the documentation contract in a shape its own consumer rejects, and every epic has fixed it by hand instead of at source"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260831-generator-emits-unparseable-doc-contract — the ticket generator writes the documentation contract in a shape its own consumer rejects, and every epic has fixed it by hand instead of at source

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2 known epics (`EPIC-BuildAcResolvesALeafAcsConnectedBuildSet`,
  `EPIC-TrustThatAGreenCheckActuallyChecked`)
- **First seen:** 2026-08-31 (as a source-side defect; the symptom predates this)
- **Last seen:** 2026-08-31
- **Where:** the ticket generator's `## Agent Contracts` → `### documentation-expert` emitter
  (`generate_ticket_from_ac.py` / `goal_to_epic.py`), against the Step 2 parse contract in
  `templates/agents/documentation-verifier.md`

**Symptom.** The generator emits the documentation contract as

```
- [ ] AC-1: [reference-doc] docs/architecture/components/commit-guardian.md — <constraint>
```

— bracketed genre, em-dash separator. `documentation-verifier` Step 2 requires

```
- [ ] AC-N: <genre> | <target_path> | <content_constraint>
```

and parses `target_path` as the **second pipe-delimited field**. With no pipes, the field is
unreachable, `required_docs` is empty, and the agent emits `status: blocker` — correctly, per its
mandatory fail-closed posture. It never reaches the diff check, so **whether the doc exists is
never established either way**. In the observed case the required doc *was* in the diff.

**Why this is a build-pipeline entry and not just a ticket-content one.** It has now happened in
two separate epics, and both times it was repaired **in the generated tickets**, never in the
generator:

- `EPIC-BuildAcResolvesALeafAcsConnectedBuildSet` (`BO-2600a-3`, `BO-2600a-5`) — flagged by
  `documentation-verifier`, hand-fixed; the surviving line in `tickets/99_done/` reads
  `- [x] AC-1: (unspecified genre) | templates/agents/build-ac.md | …`.
- `EPIC-TrustThatAGreenCheckActuallyChecked` — all 25 applicable tickets malformed, none correct;
  hand-fixed 2026-08-31 (`KI-ACD-20260831-agent-contracts-block-not-pipe-delimited`).

The generator is unchanged, so the next generated epic reproduces it. The cost is paid per epic,
late: the block surfaces at priority 11.9, after coder, tests, review and AC gates have passed —
roughly 1.3M subagent tokens into a ticket drive.

**Two further content defects the format fix does not cure.** Making the line parseable makes the
verifier actually *demand* the named path, which exposes what the generator put there:

1. **A cross-family directory as a doc target.** Ticket 02 (`GE-120a-1-i`) names
   `docs/acceptance-criteria/guardrail-engine/GE-116-consistent-agent-config` — a **directory**
   (`drwxr-xr-x`, confirmed), belonging to **GE-116**, an unrelated AC family. A directory can
   never appear in a git diff as a path, so this ticket still fails after the format fix, for a
   new reason. This one needs a human decision about the right target.
2. **Source files as documentation targets.** Six tickets (07, 11, 13, 14, 30, 34) name `.py` or
   `.json` files — e.g. `scripts/ac_store/validate_ac_schema.py`,
   `templates/scripts/commit_guardian/commit_guardian.json`. These may satisfy the diff check
   incidentally because the coder touches them, which is worse than failing: a documentation gate
   reports satisfied on a commit that documented nothing.

Six tickets also carry a literal `(unspecified genre)` token, so the genre field is frequently not
derived at all. The verifier does not validate field 1, so this parses — but it signals the
emitter is guessing.

**Fix direction.** Emit the pipe-delimited form at source. Add a round-trip test that runs
generator output through the verifier's Step 2 parser and asserts a non-empty `required_docs` —
the absence of exactly that test is what let a producer and its documented consumer disagree
across two epics without either side being individually wrong. Then constrain the target: reject a
directory, reject a path outside the docs roots (or make "source file" an explicit, named genre
with different semantics), and fail loudly rather than emitting `(unspecified genre)`. Have the
verifier name the expected format in its blocker text, which would have made the first occurrence
self-diagnosing.

**Related.** `KI-ACD-20260831-agent-contracts-block-not-pipe-delimited` (the ticket-side record
and the hand fix). `KI-ACD-022` (conditional phase agents written without the frontmatter fields
they depend on — the same producer/consumer mismatch class from the same emitter).

**Pattern:** a producer and its documented consumer never run against each other, where the
consumer's correct fail-closed posture turns the mismatch into a universal late-stage block, and
the repair keeps being applied to the output instead of the emitter.

---
