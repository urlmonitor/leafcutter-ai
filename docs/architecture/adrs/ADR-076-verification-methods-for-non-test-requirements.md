---
title: "ADR-076: Requirements That Need No Test Are Proven Done by a Typed Verification Method"
description: "A requirement record with test_required false is proven done by a typed verified_by record (method check or inspection, after the IADT practice), demanded when the record is marked done and failing closed. A prose rationale alone no longer waives the test, because any non-empty string currently unlocks done and invites always-passing placeholder tests."
type: "adr"
status: "active"
created: "2026-10-25"
last_updated: 2026-10-25
deciders:
  - BrainCandy
  - adr-author
components:
  - ac_store
  - build_orchestration
  - testing_quality
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-071-test-intent-is-not-a-test-contract.md
  - docs/architecture/adrs/ADR-075-requirement-rule-check.md
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500f.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-ii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-iv.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-v.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-1-ii.yaml
  - docs/reference/ac-schema.md
  - docs/reference/test-free-declarations.md
  - docs/acceptance-criteria/build-orchestration/BO-3500-buildable-by-any-craft/BO-3500c.yaml
  - docs/acceptance-criteria/knowledge-management/KM-ADM-005-1.yaml
  - docs/acceptance-criteria/knowledge-management/KM-ADM-005-2.yaml
  - docs/acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-3.yaml
  - docs/acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-4.yaml
  - docs/acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-6.yaml
related_code:
  - scripts/ac_store/_done_proof_phase_helpers.py
  - scripts/commit_guardian/check_done_proof.py
  - unit_tests/docs/test_artifact_graph_covers_scope.py
---

# ADR-076: Requirements That Need No Test Are Proven Done by a Typed Verification Method

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-25 |
| **Author** | adr-author (branch `ac-authoring/done-proof-verification`; decision approved by the user 2026-10-24/25) |
| **Supersedes** | None |

---

## Context

The mechanical done-proof (the BO-2500 tree) marks a requirement record done only when a
test tagged `# covers: <id>` exists and passes. Some records legitimately need no test:
a documentation requirement, a rule enforced by an existing check script, a policy
statement. For those, the done-proof has an escape hatch: the waiver from
[BO-2500a-1-ii](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-1-ii.yaml),
implemented as `is_covers_tag_waived` in
`scripts/ac_store/_done_proof_phase_helpers.py` and consumed by
`scripts/commit_guardian/check_done_proof.py`. A record is waived when
`test_required: false` **and** `test_rationale` is a non-empty string.

That waiver has two defects:

1. **Any string unlocks done.** The waiver checks that `test_rationale` is non-empty. It
   does not check what the string says, whether it is specific to the record, or
   whether anything actually proves the requirement holds. A templated sentence copied
   across many records satisfies it.
2. **It invites the placeholder-test anti-pattern.** Where a record was not waived but
   had no honest test, authors wrote an always-passing test carrying a `# covers:` tag
   only to satisfy the done-proof. Such a test proves nothing and turns the done-proof
   into a lie that no checker can see. `unit_tests/docs/test_artifact_graph_covers_scope.py`
   is part of the evidence that triggered this decision: covers-tagged tests whose
   assertions do not exercise the requirement they claim.

The KM-ADM-005 untagged-done ratchet
([KM-ADM-005-1](../../acceptance-criteria/knowledge-management/KM-ADM-005-1.yaml),
[KM-ADM-005-2](../../acceptance-criteria/knowledge-management/KM-ADM-005-2.yaml))
counts done records without a covering test. It cannot tell an honestly waived record
from a record that simply lacks proof, so it either over-counts waived records or must
exempt them wholesale with no stated ground.

Requirements engineering has a settled answer to "how is a requirement verified when a
test is not the right instrument": the IADT verification methods (Inspection, Analysis,
Demonstration, Test). Each requirement names its method, and the method carries its own
evidence. This ADR adopts that practice for records with `test_required: false`. It
complements [ADR-071](ADR-071-test-intent-is-not-a-test-contract.md) (test intent is
decided per clause during planning) and
[ADR-075](ADR-075-requirement-rule-check.md) (mechanical requirement rules are checked
by one fail-closed rule check). The cost of not deciding is that "done" stays
unfalsifiable for every untested record, and the placeholder-test pattern keeps
recurring.

---

## Decision

### 1. Wave 1 (interim): the existing waiver becomes first-class

Recorded under the new requirement
[BO-2500a-8](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8.yaml).

1.1. The BO-2500a-1-ii waiver (`test_required: false` AND a non-empty `test_rationale`,
evaluated by the single shared `is_covers_tag_waived`) MUST be treated as a first-class
done-proof outcome, not as a silent exemption.

1.2. Authoring a record with `test_required: false` MUST supply a per-record
`test_rationale` that states why this specific record needs no test. The refusal of
`test_required: false` without a rationale MUST live in the commit-time validator only,
and MUST apply only to records being written or changed in that commit. It MUST NOT be
expressed as a JSON-schema `if`/`then` rule, so the pinned whole-store schema baseline
stays unchanged.

1.3. Templated rationales MUST be refused mechanically where they are identical:
`check-ac-schema` MUST refuse a `test_rationale` whose normalised text is identical to
another record's `test_rationale`
([BO-2500a-8-v](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-v.yaml),
new). Paraphrased templates are not caught mechanically; they are caught only by the
it-po authoring instruction
([BO-2500a-8-ii](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-ii.yaml))
and by the user's batch approval
([BO-2500a-8-iv](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-8-iv.yaml)).

1.4. The KM-ADM-005 untagged-done ratchet
([KM-ADM-005-1](../../acceptance-criteria/knowledge-management/KM-ADM-005-1.yaml)) MUST
exclude waived records, and each exclusion MUST carry one category ground:
"waived: declared test-free with a stated reason". The ground is the category, not each
record's own rationale text. An exclusion with no ground MUST NOT be used.

1.5. The account of test-free declarations MUST live in a new reference page,
`docs/reference/test-free-declarations.md`. `docs/reference/ac-schema.md` MUST only link
to it and MUST NOT duplicate the account.

1.6. Wave 1 is interim. It will be replaced by Wave 2 for records marked done after Wave
2 lands.

### 2. Wave 2: a typed `verified_by` record

Recorded under [BO-2500f](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500f.yaml)
and its children.

2.1. A record with `test_required: false` MUST carry a `verified_by` record naming one
verification method. The methods are `check` and `inspection`.

2.2. **`method: check`.** The record MUST name a check script that carries the tag
`# enforces: <id>` for the requirement id, and MUST name the hook or build phase that
really invokes that script. A wiring check MUST verify that the named hook or phase
actually runs the named script; a script that exists but is not wired MUST NOT satisfy
the proof.

2.3. **`method: inspection`.** The record MUST name:
- the inspected files, each pinned by its git blob hash;
- a statement of what the inspection established;
- a reviewer identity: a reference (`gate_run`) to a person's approval given at an
  interactive workflow gate and persisted as an approval file (§2.3a).

2.3a. **Approval file.** Each gate answer MUST be persisted as a retained JSON file in a
tracked folder, planned as `docs/acceptance-criteria/_inspections/<run_id>.json` (the
exact path is not yet fixed). The file MUST hold the run id, the gate, the answer, the
timestamp, the AC id, and the inspected files with their blob hashes. It MUST be
committed together with the requirement record it proves, so CI and every machine read
the same evidence and give the same verdict. The approval MUST NOT be read from the
gitignored pause/resume store, which is local and is cleared after resume.

2.3b. **Checking the approval.** The approval MUST be checked at mark time and offline,
against the committed approval file only (no network call). A missing, unresolvable, or
mismatched approval file MUST fail closed, as MUST a mismatch between the blobs in the
approval file and those in `verified_by`.

2.3c. **Who writes approval files.** Approval files MUST be written only by the
inspection gate's code path. There MUST be no CLI that writes an approval file.
Residual trust: an agent with shell access can still forge an approval file, and the
gate answer itself passes through the agent harness. This ADR accepts that residual
trust. An upgrade to signed commits, verified in CI against an allowed-signers file,
stays possible and is deferred (see Alternatives).

2.3d. **The `/inspect` workflow.** A dedicated `/inspect` workflow MUST produce
inspection approvals. Given an AC id and its inspection draft, it MUST show the inspected
files with their current blob hashes and the statement, and ask the person to approve
or reject. On approve it MUST write the approval file and fill `gate_run` and the blob
hashes into the record's `verified_by`. On reject it MUST write nothing to
`verified_by`. The workflow MUST be independent of `plan-feature.js`.

2.4. An inspection MUST expire when any inspected file changes: if a named file's current
blob hash differs from the recorded hash, the inspection is void. This MUST be checked
at the moment the record is marked done.

2.5. `method: inspection` MUST NOT be used for a record whose `change_target` is code,
schema, or pipeline. Those targets MUST be proven by a test or by `method: check`.

2.6. Once Wave 2 is in force, a prose `test_rationale` alone MUST NOT waive the test. It
remains as authoring context only.

2.7. The typed `verified_by` record MUST be demanded only when a record is marked done.
It MUST NOT be demanded when the record is first written or edited before that point.

2.8. The verification MUST fail closed: a missing, malformed, unwired, expired, or
unresolvable `verified_by` record blocks the done mark. Any error in evaluating it
blocks the done mark.

### 3. Ownership boundaries

3.1. BO-2500f owns the record side: the `verified_by` field, its shape, and its
evaluation at mark time.

3.2. The per-kind proofs (what counts as proof for each kind of change target) MUST come
from [BO-3500c](../../acceptance-criteria/build-orchestration/BO-3500-buildable-by-any-craft/BO-3500c.yaml).
A second, parallel vocabulary of proof kinds MUST NOT be introduced.

3.3. Periodic re-checks of finished records and their demotion when a proof no longer
holds stay with TQ-400a and TQ-400b; this ADR does not add a second re-check loop.
The related durable-proof requirements
[TQ-400e-3](../../acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-3.yaml),
[TQ-400e-4](../../acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-4.yaml)
and [TQ-400e-6](../../acceptance-criteria/testing-quality/TQ-400-durable-done-proof/TQ-400e-6.yaml)
apply to `verified_by` proofs as they do to test proofs.

3.4. Migration of records already marked done under the prose waiver MUST go through
TQ-400b / TQ-400d. Wave 2 MUST NOT retroactively demote finished records on its own.

---

## Consequences

### Positive

- "Done" becomes falsifiable for untested records: each carries evidence that a machine
  (check wiring, blob hashes, the committed approval file) can re-verify.
- Approval evidence is committed with the record, so CI and every machine give the same
  verdict; no local-only state decides done.
- The placeholder-test anti-pattern loses its motive: an honest non-test proof exists,
  so there is no reason to write an always-passing covers-tagged test.
- The KM-ADM-005 ratchet becomes accurate: waived records are excluded with a ground,
  and unproven records are still counted.
- Inspection proofs cannot silently go stale; a change to an inspected file voids them.
- Reuses BO-3500c's proof kinds and TQ-400's re-check machinery, so no parallel system
  is built.

### Negative

- Authoring cost rises: Wave 1 demands a specific rationale per record; Wave 2 demands a
  wired check script or a person's approval at a workflow gate for every untested record.
- Inspection depends on a person answering an interactive workflow gate; agent-only
  flows cannot mark an inspection-verified record done without a person.
- Inspection proof carries residual trust: the gate answer passes through the agent
  harness, and an agent with shell access can forge an approval file. It is weaker than
  an identity an outside system attests, until signed commits are adopted.
- A tracked `_inspections/` folder grows by one retained file per inspection approval.
- Paraphrased templated rationales escape the mechanical identity check and rely on the
  it-po instruction and the user's batch approval.
- Inspections expire on any change to an inspected file, including harmless edits, which
  forces re-inspection.
- Fail-closed evaluation means a missing or uncommitted approval file or a hash lookup
  failure blocks done marks until resolved.

### Operational

- Wave 1 changes the authoring rule, the commit-time validator, `check-ac-schema`
  (identical-rationale refusal) and the KM-ADM-005 ratchet; `is_covers_tag_waived` stays
  the single shared predicate. The pinned whole-store schema baseline is unchanged.
- A new reference page, `docs/reference/test-free-declarations.md`, carries the
  test-free account; `docs/reference/ac-schema.md` gains only a link.
- Wave 2 adds a `verified_by` field to the requirement record schema, an `# enforces:`
  tag convention for check scripts, a wiring check, and mark-time evaluation in the
  done-proof path (`scripts/ac_store/_done_proof_phase_helpers.py`,
  `scripts/commit_guardian/check_done_proof.py`).
- Wave 2 adds a dedicated `/inspect` workflow, independent of `plan-feature.js`, and a
  tracked approval-file folder (planned `docs/acceptance-criteria/_inspections/`).
- Existing finished records keep their status until TQ-400b / TQ-400d migrate them.

---

## Alternatives

- **(A) Keep the prose waiver only.** Rejected. The waiver tests only that
  `test_rationale` is non-empty, so any string, including a templated one, unlocks done;
  nothing ties the claim to evidence, and the ratchet cannot distinguish an honest waiver
  from a missing proof.
- **(C) Executable proof commands for every record.** Rejected. Documentation and policy
  requirements have no honest command that proves them, so a mandatory command
  degenerates into placeholder scripts that always exit 0: the same anti-pattern as the
  always-passing covers-tagged test, moved to a different file.
- **Inspection reviewer identity from a GitHub pull-request review approval.** Rejected.
  GitHub never lets a pull request's author approve it, and the user is a solo
  maintainer whose agents open pull requests under the user's own account, so no
  person's approval can ever be recorded on those pull requests. The proof would be
  unobtainable for every inspection.
- **Reading the approval from the local pause/resume store.** Rejected. That store is
  gitignored, local to one machine, and cleared after resume, so CI and other machines
  could not see the evidence and the verdict would differ by machine or vanish after the
  run.
- **Signed commits verified in CI against an allowed-signers file.** Deferred, not
  rejected. It would close the forgery gap left by §2.3c by binding the approval to a
  person's signing key, but it adds key management for a solo maintainer; the
  approval-file design stays compatible with adopting it later.
- **Refusing `test_required: false` without a rationale through a JSON-schema
  `if`/`then` rule.** Rejected. A schema rule applies to the whole store at once and
  would break the pinned whole-store baseline; the commit-time validator applies the
  rule only to records being written or changed.
- **Placeholder covers-tagged tests (status quo practice).** Rejected. An always-passing
  test with a `# covers:` tag satisfies the done-proof mechanically while proving
  nothing, and no checker can see the difference. This anti-pattern is what triggered
  this decision.

---

## References

- Requirement records: BO-2500f, BO-2500a-8 (Wave 1, new), BO-2500a-8-ii,
  BO-2500a-8-iv, BO-2500a-8-v (new), BO-2500a-1-ii, BO-3500c,
  KM-ADM-005-1, KM-ADM-005-2, TQ-400a, TQ-400b, TQ-400d, TQ-400e-3, TQ-400e-4,
  TQ-400e-6.
- Code: `scripts/ac_store/_done_proof_phase_helpers.py` (`is_covers_tag_waived`),
  `scripts/commit_guardian/check_done_proof.py`,
  `unit_tests/docs/test_artifact_graph_covers_scope.py`.
- Related ADRs: [ADR-071](ADR-071-test-intent-is-not-a-test-contract.md),
  [ADR-075](ADR-075-requirement-rule-check.md).
