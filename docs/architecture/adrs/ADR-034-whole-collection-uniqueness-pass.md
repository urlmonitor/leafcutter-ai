---
title: "ADR-034: Whole-Collection Uniqueness Pass — Verdict-Object Contract and Decision-Namespace Guard Registration"
description: "Decision to express numbered-artifact uniqueness as one importable whole-collection pass returning a fixed verdict object — one finding per contested number, with a mandatory per-namespace inspected count — to adopt rather than reimplement the existing decision-number comparison, and to separate whole-collection inspection from diff-scoped commit disposition."
type: "adr"
status: "active"
created: "2026-08-18"
last_updated: "2026-08-18"
deciders:
  - BrainCandy
components:
  - commit_guardian
  - documentation_system
  - ac_store
  - ticket_lifecycle
related_docs:
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/commit-guardian.md
  - docs/conventions/adr-numbering.md
related_code:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/scripts/commit_guardian/check_adr_collision.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - scripts/adr_refs.py
---

# ADR-034: Whole-Collection Uniqueness Pass — Verdict-Object Contract and Decision-Namespace Guard Registration

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-18 |
| Author | adr-author, on the handoff from `architect-review` recorded in ticket `GE-122a-1` |
| Supersedes | None |
| Context ADRs | [ADR-029](ADR-029-adr-number-collision-prevention.md) (decision-number collision prevention, incl. Amendment 1), [ADR-001](ADR-001-self-hosting-boundary.md) (self-hosting boundary) |

## Context

Four artifact namespaces in this repository are keyed by a number that is expected to
resolve to exactly one artifact: acceptance-criterion identifiers, decision-record
integers, architecture-diagram level-and-sequence identifiers, and work-item (ticket)
identifiers. A number claimed by two artifacts is a silent ambiguity — a reader who
follows a bare citation has no way to tell which of two records they landed on — and git
never surfaces it, because the filenames differ and so no merge conflict occurs. The
2026-08-13 numbering repair (recorded in [ADR-029](ADR-029-adr-number-collision-prevention.md)
and [`docs/conventions/adr-numbering.md`](../../conventions/adr-numbering.md)) cost six
renames and roughly 430 citation rewrites to undo one namespace's worth of this drift.

Every guard the repository had for these namespaces was **per-file**. `check_ac_schema.py`
reads its file set from the staged diff and judges each record alone; it is structurally
incapable of noticing that a sibling file claims the same number, because it never sees
the sibling. `check_adr_collision.py` compares a staged decision number against
`origin/main` and in-flight branches — the right comparison, but it was registered in no
manifest and had therefore never executed in the package's history (the false claim that
it was wired is corrected in ADR-029 Amendment 1). `scripts/adr_refs.py` does perform a
genuine collection-wide audit, but only for the decision namespace and only as a
manually-invoked CLI, so nothing enforces it.

Detecting collisions therefore requires a **new unit of inspection** — a pass over the
whole on-disk collection rather than over a change set. That pass is also the load-bearing
producer for the rest of the GE-122 tree: six sibling acceptance criteria (`GE-122a-1-i`,
`GE-122c-1`, `GE-122c-2`, `GE-122d-1`, `GE-122d-3`, `GE-122e-3`) consume its output, and
`GE-122d-1` requires the same evaluation to run at three separate commit-lifecycle stages.
Its result shape is consequently a cross-cutting contract with six consumers, and no
existing ADR describes it. Two further constraints bind the design: the pass runs at
commit time over roughly 2,975 requirement records, 33 decision records and 23 diagrams,
so it must stay fast enough not to be bypassed; and the collection carries a backlog of
pre-existing collisions that a naive gate would convert into a block on every unrelated
commit.

## Decision

### 1. The pass will be a library, not a hook

Uniqueness evaluation MUST live in a single importable module with a callable entry
point — `run_uniqueness_pass(collection_root) -> UniquenessVerdict` in
`templates/scripts/commit_guardian/check_identifier_uniqueness.py`. The logic MUST NOT be
inlined into a pre-commit hook script. Hook scripts and CI stages are thin callers of this
function. Consumers MUST import the function and read the returned object; they MUST NOT
shell out to a CLI and parse its text.

### 2. The verdict object is a fixed, additive-only contract

The returned object MUST expose exactly this shape, and future changes to it MUST be
additive:

| Accessor | Type | Meaning |
|---|---|---|
| `verdict.passed` | `bool` | True when every namespace passed. |
| `verdict.namespaces` | `dict[str, NamespaceVerdict]` | Keyed by namespace name. |
| `namespace_verdict.passed` | `bool` | True when the namespace has no findings. |
| `namespace_verdict.inspected_count` | `int` | Artifacts inspected in this namespace. |
| `namespace_verdict.findings` | `list[Finding]` | One entry per contested number. |
| `finding.number` | `str` | The contested number. |
| `finding.paths` | `list[str]` | **Every** artifact claiming it. |
| `finding.declared_states` | `dict[str, str]` | Per-path declared state; `{}` where not applicable. |

Three properties of this shape are binding, not incidental:

- The pass MUST emit **exactly one finding per contested number**, never one per claimant
  file. A collision is a property of the number, not of either file, and per-file
  reporting multiplies one problem into N alarms.
- Each finding MUST name **every** claimant path, so a reader can see both sides of a
  collision without searching the collection.
- `inspected_count` MUST be reported per namespace on **every** run, including passing
  runs. It is not optional diagnostic output: it is the only thing that distinguishes a
  real pass from a pass produced by inspecting nothing, which is the failure mode a
  misconfigured root path produces silently.

An artifact whose number is claimed only once MUST NOT appear in the report.

### 3. Inspection is whole-collection; disposition is diff-scoped

`run_uniqueness_pass` MUST be called exactly once per invocation and MUST always inspect
the whole collection. Narrowing *what is inspected* to the change set is forbidden — it
reintroduces the per-file blindness this ADR exists to remove.

Narrowing *what blocks* is required instead. `compute_commit_disposition(verdict,
staged_paths)` filters the already-produced verdict without re-walking the collection. A
contested number with a claimant in the current change set MUST block the commit. A
contested number with no claimant in the change set MUST be reported and MUST NOT block,
and the count of such unattributed findings MUST be printed so the pre-existing backlog
stays visible rather than silently tolerated.

### 4. Adopt the existing decision-number comparison; do not reimplement it

The decision namespace MUST reuse `check_adr_collision.py`'s existing
staged-vs-`origin/main`-vs-in-flight-branch comparison. A second implementation of the
same comparison MUST NOT be written. Registration, not reimplementation, was the gap: the
guard is now registered as `check-decision-number-uniqueness` in the `hooks_manifest.hooks`
array of `templates/scripts/commit_guardian/commit_guardian.json`.

Registration MUST target that manifest. `.pre-commit-config.yaml` is a **build output** —
`scripts/build_precommit.py` re-renders it from the manifest on every `build.py` run — so
a hook added by hand-editing the generated config works locally and vanishes in CI. Per
[ADR-001](ADR-001-self-hosting-boundary.md), `templates/scripts/commit_guardian/` is the
canonical source and the `.leafcutter/` copy is a build output; edits MUST go to the
template.

### 5. Failing to read the collection MUST NOT read as "everything is fine"

Disposition on error MUST be derived from whether the collection was actually read, not
from which exception class was caught — the rule established by
[ADR-029 Amendment 1](ADR-029-adr-number-collision-prevention.md#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects).
A guard that completed its scan and then tripped on the way to reporting MAY exit 0 with a
warning. A guard that could not read a namespace at all MUST NOT exit 0; it MUST name what
it could not read and report how many numbers it did read. This rule binds
`check_identifier_uniqueness.py` as well as the adopted `check_adr_collision.py`.

The same principle governs the change set: when the staged set cannot be determined at
all, the pass MUST fall back to the whole-collection pass/fail outcome. Treating an
undeterminable change set as "nothing is staged" would let an unrelated git failure turn
the gate into a permanent no-op.

### 6. Scope of this decision

This ADR governs the pass's contract and the decision-namespace registration. Wiring the
whole-collection pass into all three commit-lifecycle stages is `GE-122d-1`'s work and is
deliberately **not** decided here; the library-not-hook rule above is what keeps that work
possible.

## Consequences

### Positive

- Six downstream consumers can be built against a written contract instead of against an
  implementation, and the three-stage requirement of `GE-122d-1` becomes reachable.
- Collisions in all four namespaces become detectable at all, for the first time — the
  per-file guards could not see them by construction.
- The decision namespace stops being guarded only on paper. A guard that had never
  executed now runs.
- A passing result is falsifiable: `inspected_count` makes "inspected nothing" visibly
  different from "inspected everything and found nothing".
- Reports stay proportional to the problem — three collisions produce three findings, not
  six.

### Negative

- The verdict object is now a public contract with six consumers, so narrowing it is a
  breaking change requiring an ADR amendment. Additive evolution is the only cheap path.
- Every commit that touches a numbered artifact pays for a whole-collection walk. The pass
  MUST complete in under five seconds over the present collection; a slower gate gets
  bypassed, and a bypassed gate protects nothing.
- Pre-existing unattributed collisions are reported on every run. This is intentional
  visibility, but it is also recurring noise until the backlog is drained.

### Operational

- New modules placed under `templates/scripts/commit_guardian/` are deployed wholesale by
  `build_commit_guardian()`, so they need no additional deploy-manifest entry. Helpers
  placed **outside** that directory (`scripts/ac_store/*.py`, top-level `scripts/*.py`) do
  require one, or the deployed hook raises `ModuleNotFoundError` while source-tree tests
  stay green.
- Registering a hook is a two-step operation: edit the manifest, then run `build.py` and
  commit the regenerated `.pre-commit-config.yaml`.
- Because the decision-number guard is now live, `adr-author` runs must allocate numbers
  by the free-number rule (`scripts/adr_refs.py` "Unclaimed numbers": free means neither a
  file nor a citation), not by highest-plus-one.

## Alternatives

- **Add another rule to `check_ac_schema.py`.** Rejected. That validator reads its file set
  from the staged diff and judges each record in isolation, so it can never observe that a
  second file claims the same number. The gap is the unit of inspection, not the rule set.
- **Inline the logic in one pre-commit hook script.** Rejected. `GE-122d-1` requires the
  same evaluation at three lifecycle stages and five other ACs consume the verdict; logic
  living inside one stage's script is unreachable from the other two without copying it.
- **Expose the pass as a CLI and have consumers parse its output.** Rejected. It would make
  a human-readable message the machine contract, so any wording change would break
  consumers, and it forfeits typed access to per-namespace counts and claimant paths.
- **Report one finding per claimant file.** Rejected. It converts one contested number into
  N alarms, and it forces the reader to correlate separate lines to discover who the other
  claimant is — the specific work this decision removes.
- **Reimplement the decision-number comparison inside the new pass.** Rejected. A working
  implementation already exists and is now registered; a second copy would be a duplicate
  to keep in sync, and duplication is the class of defect this tree exists to close.
- **Register the hook by editing `.pre-commit-config.yaml`.** Rejected. That file is
  regenerated from the manifest on every `build.py` run, so the edit passes locally and
  disappears in CI before any hook executes.
- **Keep `check_adr_collision.py` unconditionally fail-open.** Rejected. Exiting 0 after
  failing to read the sequence asserts "your number is fine" on no evidence. ADR-029
  Amendment 1 already narrowed this; the narrowed rule is adopted here rather than
  re-litigated.
- **Block on every contested number regardless of attribution.** Rejected. The collection
  carries pre-existing collisions, so this would block every unrelated commit until the
  entire backlog was drained, and the gate would be disabled within a day.
- **Scope inspection itself to the staged diff for speed.** Rejected. It restores exactly
  the per-file blindness described in Context; the diff-scoped decision belongs in
  disposition, after a whole-collection inspection.
- **Leave enforcement to the manual `scripts/adr_refs.py` audit.** Rejected. It covers only
  the decision namespace and runs only when someone remembers, which is how the four
  duplicated integers of the 2026-08-13 repair accumulated in the first place.

## References

- Originating ticket: [`tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/01_TICKET-20260818-GE-122a-1.md`](../../../tickets/00_inbox/epics/EPIC-GE122UniquenessPassAndRepair/01_TICKET-20260818-GE-122a-1.md) — AC `GE-122a-1`, under goal `GE-122` ("numbers mean one thing")
- [ADR-029 — ADR Number Collision Prevention](ADR-029-adr-number-collision-prevention.md), including Amendment 1 (fail-open narrowed; wiring claim corrected). This ADR adopts that amendment's rule; it does not modify ADR-029.
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — template-is-canonical, `.leafcutter/` is a build output
- [`docs/conventions/adr-numbering.md`](../../conventions/adr-numbering.md) — the free-number rule the decision namespace enforces
- [`docs/architecture/components/commit-guardian.md`](../components/commit-guardian.md) — the component this pass belongs to
- [`scripts/adr_refs.py`](../../../scripts/adr_refs.py) — the retrospective decision-namespace audit this pass generalises and automates
