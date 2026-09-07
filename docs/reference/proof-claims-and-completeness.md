---
title: "Reference: Proof Claims and What They Do Not Mean"
description: "For each of the seven kinds of proof a test can claim, states what the claim asserts, what it does NOT entitle a reader to conclude, and where the excluded question is actually settled."
type: reference
status: active
created: 2026-09-01
last_updated: 2026-09-01
components:
  - build_pipeline
  - testing_quality
  - documentation_system
related_docs:
  - docs/testing/test-angles.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g-4-i.yaml
  - docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g-5.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-2.yaml
  - docs/known-issues/testing-quality.md
---

# Proof Claims and What They Do Not Mean

A test's `# angle: <kind>` tag is a **claim by the test's author** about which
question the test was written to answer. This page states, for each of the seven
permitted kinds, what the claim asserts and — the reason this page exists — what it
does **not** entitle a reader to conclude. For the taxonomy itself (why these seven,
the incidents behind each, the literature), see `docs/testing/test-angles.md`; this
page restates none of that catalogue.

---

## The Two Axes That Sit on the Same Test Record

A tagged test carries two independent axes. They are stated here side by side
because they sit on the same records and are otherwise conflated by anyone reading
the tests alone.

| Axis | Tag | What it decides | Evaluated when | Consequence when it fires |
|---|---|---|---|---|
| Coverage | `# covers: <AC-ID>` | Which **failing** tests are treated as blocking | Every test run | A failing covered test blocks the merge (`TQ-100c-1`) |
| Kind of proof | `# angle: <kind>` | Whether every kind of proof a piece of work **promised** has a test **claiming** it | Commit time, comparing the plan's promise against the tag scanner's claim | A promised kind with no claiming test is **refused by name** (`BP-1100g-4`) |

Neither axis feeds the other. A test can fail and be covered (blocks, regardless of
its angle tag) or pass and be angle-tagged (proves nothing about whether it fails).
The angle tag **never** enters `_classify_outcomes`, `verify_done_eligible`, or any
pass/done/eligibility computation (`BP-1100g-3`'s fourth clause) — it is a completeness
check between two written declarations, nothing more.

---

## What a Claim Is, and Is Not

**An `# angle: <kind>` tag is evidence that a proof of that kind was PROMISED and
ANSWERED.** It is authored by whoever wrote the test, exactly as `# covers:` is.

**It is never evidence that the work is reached when the product actually runs.**
Whether a test's claimed way-in was genuinely entered during that test's execution is
an execution-derived fact, decided by watching the run — never by reading the test's
text (`BO-2900a-2`). That question is settled downstream, by BO-2900's execution
observer (`BO-2900a`), which installs a call-level recorder for the duration of the
proof run and reports whether the claimed entry point was an ancestor on the real
call stack while the code under proof executed. Nothing on this page, and no
mechanism the seven kinds below feed into, performs that check. A claim is the
paperwork; the observer is the audit.

---

## The Seven Kinds

The kind values below are read verbatim from `config/ac_store_schema.json`,
`properties.test_spec[].angle.enum` — the single source `BP-1100g-1` establishes.
They are not hand-typed from memory: any future change to that enum must be
reflected here by re-reading the schema, not by editing this table in isolation.

For the trigger rule (when each is mandatory vs. conditional), the cap of four, and
the incident catalogue behind each, see `docs/testing/test-angles.md`. This table
states only the entitlement boundary: what claiming the kind means, and what it does
not.

| Kind | Claiming it means | It does **NOT** mean | Concrete evidence |
|---|---|---|---|
| `criterion` | The test asserts the unit directly implements the AC's Gherkin `Then` clause, on the unit itself, mocking collaborators freely. | That the unit is ever reached by a production entry point, that its real caller uses the tested signature, that its fixture is a real artifact, or that the deployed copy behaves the same way. Every other kind below is checked against "proof of the behaviour alone" — this is that baseline, and nothing more. | `docs/testing/test-angles.md` — "The taxonomy" table. |
| `reachability` | The test invokes the real production entry point (CLI via `subprocess`, hook via its real runner, workflow dispatch, `main()` with real `argv`) and asserts the behaviour occurred and its result was consumed in control flow. | That the entry point was **observed** to be entered — that determination is execution-derived and belongs exclusively to BO-2900's observer (`BO-2900a`, `BO-2900a-2`). The promise-versus-claim check that reads this tag takes it at **face value**: it never opens, reads, parses, tokenizes, or pattern-matches the claiming test's body, so a pre-existing direct-import test given only the tag receives the identical outcome as a genuine one (`BP-1100g-4-i`). | `BP-1100g-4-i` (accepted-paste invariance); `BO-2900a-2` (verdict is execution-derived, never text-derived); `docs/testing/test-angles.md` reachability-gap incident table. |
| `seam` | The test pipes the REAL producer's actual output into the REAL consumer and asserts the consumer's observable behaviour. | That the fixture spans the failure mode, that the deployed copy was exercised, or that this work needed a seam test at all — a reasoned "no seam applies" is an equally valid, first-class hand-off answer, not a lesser one (see "The Seam Rule's Answer" below). | `docs/testing/test-angles.md` seam-gap incident table (5 incidents, both sides green in isolation, never wired together); `BP-1100g-5`. |
| `real_artifact` | The fixture bytes come from the real serializer (e.g. `yaml.safe_dump`) or a verbatim on-disk file, and any module-load claim was verified in a genuinely fresh subprocess. | That the fixture, being non-trivial and non-vacuous, actually **spans the failure mode** it exists to guard. A test can carry real on-disk fixtures, the real serializer, the real production entry point, and explicit anti-vacuity assertions and still be inert against the exact leak it was written to catch — fixture realism and failure capability are different properties, and only a mutation proof distinguishes them. | `KI-TQ-010` — `BP-1100g-3-i`'s test 3 (tagged `real_artifact`, carrying every mark of quality listed above) stayed green under the injected leak that its three siblings caught; "self-certified non-vacuity is not falsifiability." |
| `deployed` | The test runs `build.py` into a temporary target and exercises the DEPLOYED copy of the file. | That the same behaviour holds for the source-tree copy, or that "deployed" names a single unambiguous file — this repository maintains real duplicate copies of some modules (`scripts/ac_store/` vs. `.leafcutter/scripts/ac_store/` are separate directories; `scripts/commit_guardian` is a symlink), and a proof applied to the copy a production path does not actually load reports green while proving nothing about the copy that runs. | `KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy` (a mutation proof injected into the template copy proved nothing because the tests import the build output); `docs/testing/test-angles.md` deployment-gap incident table (`BP-811`: the cleanest recorded case of "copy present" vs. "copy reachable" being different tiers). |
| `boundary` | The test exercises the empty / one / many / limit / malformed-but-parseable edge of a range, count, or shape the AC names. | That every edge was tested, or that this axis is proactively authored rather than caught in review — the evidence base for this conditional angle is concentrated (two source epics) and every recorded incident was found by post-merge adversarial review, not by a boundary test identified in advance. | `docs/testing/test-angles.md` — "The two conditional angles" section (`TKT-500f-15`; `EPIC-PhantomDoneFilesTouched` round-1 #3-#6; `BO-400c-3` T03). |
| `failure` | The test feeds a known-bad input through the same entry point or gate and asserts it blocks (non-zero exit, or the blocker string in the payload) or degrades fail-closed. | That the gate is fail-closed against every input, only the one tested — nor that the failure path is reachable in production (that is `reachability`'s question, on the failure path specifically, and is a separate claim). | `docs/testing/test-angles.md` negative-control-gap incident table (`BO-1700` fail-open gate; `FIN-100h` inverted branch; `EPIC-InFlightVisibility` FP-5 silently-dropped guards; `TQ-100` L-4 `continue-on-error` CI job). |

**A claim can also be vacuous by construction.** Any of the seven kinds can be
claimed by a test that cannot fail — a negative control asserting an absence is
green on arrival the moment the implementation is correct, has no red baseline to
capture, and the claim tells a reader nothing until a **mutation proof** (inject the
forbidden leak, show red, then show green on revert) exists in its place. See
`KI-TQ-010` and the `TQ-500` tree (`docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/`)
for the mechanism and the two known occurrences this affected.

---

## The Accepted Paste — a Deliberate Design Decision, Not an Oversight

The promise-versus-claim check (`BP-1100g-4`) is trivially satisfiable by pasting an
`# angle: reachability` tag onto a pre-existing, unmodified happy-path test that
merely imports the unit directly. **This is accepted by design, not a gap left to
close.**

The reason is structural, not a matter of effort: closing it would require the check
to decide, from the claiming test's text, whether that test genuinely does what it
claims — and that is exactly what `BO-2900a-2` prohibits. `BO-2900a-2`'s own grounds
are the decisive ones here: a source-text scan living inside a phantom-done guard is
itself phantom-done, precisely the failure mode that shipped in the fast-lane
runner's grep-only structural tests. Building a paste-detector into the
promise-versus-claim check would put a second phantom-done guard inside the first.

So the check's contract is deliberately narrow (`BP-1100g-4-i`): it compares exactly
two written declarations — the promised kinds from the plan, and the claimed kinds
the tag scanner collects — and its output is reported as **"promised and claimed,"**
never as "reached," "proven," "verified," or "done." No path to that outcome opens,
reads, parses, tokenizes, or pattern-matches the claiming test's body, and the
outcome for a pasted claim is byte-identical to the outcome for a genuine one, and
stays byte-identical even when the claiming test's body is replaced wholesale.

**The lie is caught downstream, not here.** The only mechanism that can catch a
pasted-but-unreached claim is BO-2900's execution observer (`BO-2900a`), which
watches the actual call stack during the proof run rather than reading any test's
source. Do not author a sibling check that tries to detect the paste — `BP-1100g-4-i`
and `BO-2900a-2` both name that as reopening the exact defect this boundary exists to
prevent.

---

## The Seam Rule's Answer Is a Required Part of the Hand-off Record

Deciding whether a piece of work crosses a producer→consumer boundary — and, if so,
writing a `seam`-angle test that feeds the real producer's real output into the real
consumer — is a rule that applies to **every** piece of work, not only work that
turns out to need one. `BP-1100g-5` requires that the answer to that rule, for every
piece of work, land in the same hand-off record that already carries the writer's
other machine-checkable statements (the `completion_manifest` block), under one fixed
key: `cross_layer_seam_answer`.

Exactly one of two conforming shapes is recorded per piece of work:

| Shape | Fields | Meaning |
|---|---|---|
| Covered | `{result: covered, producing_side, consuming_side}` | A seam applies, and both sides are named. |
| Not applicable | `{result: not_applicable, reason, remediation}` | No seam applies, and the reason is stated. |

**A reasoned "no seam applies" is a first-class, valid recorded outcome — not a
failure, not a skip, and not evidence of lesser rigor than a covered answer.** A
mandate with no legitimate negative answer gets rubber-stamped; forcing a fabricated
seam claim onto work that has no producer/consumer boundary costs a real test's worth
of effort and produces a false record, which is worse than recording the honest
negative. What is not acceptable is silence: a hand-off record carrying no answer to
the rule at all must be distinguishable from one that answered it, and the answer is
scoped per piece of work, never per run, so one item's answer can never be read as
covering a sibling's.

The seam answer, like every kind-of-proof claim above, is a **declaration by the
writer**. It is not evidence the seam test is any good, and it feeds no done, pass,
or eligibility decision.

---

## See Also

- [Test Angles — A Set-Cover Taxonomy for Proof of Done](../testing/test-angles.md) —
  the full taxonomy: trigger rules, the cap of four, and the incident catalogue each
  kind is grounded in. This page states the entitlement boundary; that page states
  the "why."
- **The ASK-side companion page — not yet authored.** `BO-2900g-5` (`work_status: todo`)
  owns a page stating what a plan is permitted to request, in the same seven-kind
  vocabulary this page uses for what claiming a kind means. No path is linked here
  because the page does not exist yet — a frontmatter `related_docs` entry is
  machine-validated for existence, and a link to an unwritten file is broken
  regardless of intent. Referenced by AC id instead: when `BO-2900g-5` lands,
  reconcile it against this page's table so the two never state different permitted
  kinds.
- [Phantom-Done Prevention — Real-Effect / Real-Intent Verification](../architecture/components/phantom-done-prevention.md) —
  the component page this reference is reachable from.
- `docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-2.yaml` —
  the prohibition on deciding reachability from source text.
- `docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g-4-i.yaml` —
  the accepted-paste invariance contract in full.
- `docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100g-5.yaml` —
  the seam-rule hand-off record contract in full.
- `docs/known-issues/testing-quality.md` — `KI-TQ-010` and the `real_artifact` /
  `deployed` incidents cited in the table above.
- `config/ac_store_schema.json` — `properties.test_spec[].angle`, the single source
  for the seven permitted kinds.
