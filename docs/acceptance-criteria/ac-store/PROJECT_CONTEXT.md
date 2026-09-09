---
title: "ac-store — AC store context"
description: Cross-agent conventions and standing notes for PO v3 / BA v3 / IT PO v3 authoring
  and decomposing ACs in the ac-store component (prefix ACS).
created: '2026-08-14'
last_updated: '2026-09-01'
type: tutorial
status: active
components:
  - ac_store
---
# ac-store component — PROJECT_CONTEXT

Cross-agent context for PO v3 / BA v3 / IT PO v3 working in the ac-store component.

## ACS-800 stable-AC-identity: framing note for the BA (2026-06-22, PO)

ACS-800 ("Reorganize your requirements freely as they grow, without breaking a
single reference") is a NEW L0 in ac-store, slug folder
`ACS-800-stable-ac-identity/`, six L1 children ACS-800a..f, origin_agent:
BrainCandy (user-authored), readiness: approved, priority: high. It decouples AC
identity from tree position: stable opaque UIDs assigned sequentially at creation
(NOT derived from position) + hierarchy expressed in metadata (parent pointer +
level + order) instead of encoded in the id string.

Placement rationale worth reusing: this was minted as a NEW root L0 (ACS-800 — the
next free hundred; 100–700 were taken) rather than an L1 under ACS-100, because
ACS-100 is already at 9 L1 children (a–i, over the 7-cap). Adding to a saturated
tree is exactly the pain ACS-800 cures. When a new capability would push an L0 over
cap, prefer a sibling L0 (horizontal split per the ac-tree-split skill) over
overloading the existing L0.

Decomposition guidance the PO baked into the L1 split (decompose each into L2
behaviors; do NOT re-cut at L1):
- ACS-800a (python-coder) — stable opaque UID assignment scheme; never-reused,
  never-renamed guarantee; relax the schema id regex so id no longer encodes
  hierarchy. documentation_triggers [reference-doc].
- ACS-800b (python-coder) — hierarchy in metadata: parent_uid + level + order are
  EXAMPLE field names; BA/IT-PO finalize exact names at L2 and add to the schema.
  documentation_triggers [reference-doc].
- ACS-800c (python-coder) — THE core payoff: re-parent is ONE metadata-field change,
  no id rename, no reference cascade across depends_on/covered_by/delivers_to/
  expects_from/superseded_by. documentation_triggers [how-to].
- ACS-800d (python-coder, complexity L) — migration/back-compat from position-encoded
  ids to UIDs; zero dangling references; touches the whole store at once (highest
  risk). documentation_triggers [how-to].
- ACS-800e (python-coder, complexity L) — update ALL tooling that derives structure
  from the id string to read metadata: check_ac_limits.py (child counting),
  check_ac_parent_covered_by.py, goal_to_epic.py, scripts/ac_store/ac_parent_id.py
  (derive_parent_id), config/ac_store_schema.json id regex.
  documentation_triggers [component-diagram].
- ACS-800f (llm-expert) — update the authoring GUIDANCE (prose/template/skill
  surface, NOT python): ac-tree-split SKILL.md, PO/BA agent templates' parent-
  derivation guidance, ac-schema.md ID Format / Parent Derivation sections.
  documentation_triggers [how-to].

Agent-assignment line for the IT-PO (scanning *it-po* files): a–e are .py/schema
tooling => python-coder; f is template/skill prose => llm-expert (per the IT-PO
"agent assignment by technical surface" convention — text that tells an agent or
skill what to DO/SAY is llm-expert, not python-coder). Do NOT let the BA
uniformly stamp all six python-coder; ACS-800f is the one that must stay llm-expert.

STOPGAP-RETIREMENT CROSS-REFERENCE (load-bearing — keep this through decomposition):
ACS-800 is the PERMANENT fix for the tree-saturation / re-parenting pain that the
newly added `child_limit_override` field on check_ac_limits.py is only a TEMPORARY
stopgap for, and that the ac-tree-split skill's repeated manual splits work around.
Once ACS-800e lands (tooling counts children from metadata, not id strings),
child_limit_override should be RETIRED. This retirement note is baked into the L0
notes and into ACS-800c/e/f notes — the BA/IT-PO should carry it into the L2/L3
it_requirements so the override does not silently become permanent.

## ACS-900 deprecation-hygiene: framing note for the BA/IT-PO (2026-06-22, PO)

ACS-900 ("When you retire a requirement, the code it claimed can't quietly stay
behind") is a NEW root L0 in ac-store, slug folder ACS-900-deprecation-hygiene/,
five L1 children ACS-900a..e, origin_agent: BrainCandy, readiness: draft, priority:
medium. A BLOCKING pre-commit hook: when an AC status flips to deprecated /
superseded / superseded_by, verify the source in its implemented_by is gone or
reconciled; block the commit if orphaned live code still claims the retired AC.

THREE NON-OVERLAPPING GOVERNANCE L0s IN ac-store (reuse this map; do NOT cross-wire):
- ACS-200 (automated-verification) = test COVERAGE of LIVE ACs.
- ACS-400 (ac-governance) = WHO may edit a requirement DEFINITION (criteria-field
  authorship protection).
- ACS-900 (deprecation-hygiene) = code-side LIFECYCLE of a RETIRED AC. This was the
  genuinely empty quadrant; that emptiness is why it earned a sibling L0 (next free
  hundred = ACS-900; ACS-200/400 are also at/over child cap) rather than an L1 graft.

> **Superseded 2026-08-14 — the map is now FOUR quadrants.** See the ACS-1200 note
> at the end of this file; ACS-1200 owns the PRE-decomposition (parked) state.

BLOCKING vs FAIL-OPEN distinction (load-bearing — carry into L2/L3 it_requirements):
the always-block-on-a-REAL-violation posture is a USER-CONFIRMED product decision and
must NOT be relaxed to warn. SEPARATELY, the standard fail-open-on-INTERNAL-ERROR
convention still applies (hook crash / parse error / git failure -> exit 0 + stderr
warning). These are orthogonal: do not let the IT-PO collapse "fail open on script
bug" into "warn instead of block on violation".

> **Refinement 2026-08-14 (GE-120).** A third case sits between these two and was
> previously unnamed: a hook that could not RUN AT ALL (its dependency, config, or
> schema was unreachable) currently takes the fail-open path and reports SUCCESS,
> making "green" indistinguishable from "did not run". GE-120 governs that case.
> Fail-open on one bad input while the check still ran remains correct; reporting
> success for a check that never executed does not.

DECOMPOSITION guidance baked into the L1 split (decompose each into L2; do NOT re-cut
at L1):
- ACS-900a = detection trigger (status transition arms the check; targets = implemented_by).
- ACS-900b = the BLOCK decision only (no message text, no reconciliation rules here).
- ACS-900c = message quality (model on ACS-400e-1: name AC id + file paths + rule +
  remedy; emit to stdout not only stderr).
- ACS-900d = no-false-positive / happy path. Legitimate PASS cases the hook must NOT
  fire on: file deleted; implemented_by emptied; for superseded_by, implemented_by
  RE-POINTED to the successor named in superseded_by (code moved, not deleted — MUST
  pass); empty implemented_by (nothing claimed). This is the guardrail against the hook
  being disabled for over-firing.
- ACS-900e = anti-duplication. Existing tool = scripts/ac_store/cross_reference_audit.py
  (BACKFILLS implemented_by but does NOT detect stale code). Reuse its AC<->source
  traceability resolution; do NOT write a second independent traversal.

Agent-assignment line for the IT-PO: all five L1s decompose to .py work in
scripts/commit_guardian/ (a new check_*.py hook joining the existing check_ac_*.py
family) plus config wiring in commit_guardian.json => python-coder. No prose/template
surface here, so unlike ACS-800f there is NO llm-expert child.

## ACS-1200 parked-ideas: framing note for the BA/IT-PO (2026-08-14, PO)

ACS-1200 ("Capture a half-formed idea without bypassing your own safeguards") is
a NEW root L0 in ac-store, slug folder `ACS-1200-parked-ideas/`, four L1 children
ACS-1200a..d, origin_agent BrainCandy, readiness draft, priority medium, NO
roadmap_phase claimed. It makes "deliberately parked, not yet decomposed" a state
the guardrails recognise, instead of a rule you must skip in order to record an
idea.

THE GOVERNANCE MAP IS NOW FOUR QUADRANTS (supersedes the three-quadrant map
above; reuse it, do NOT cross-wire):
- ACS-200 (automated-verification) = test COVERAGE of LIVE ACs.
- ACS-400 (ac-governance) = WHO may edit a requirement DEFINITION.
- ACS-900 (deprecation-hygiene) = code-side lifecycle of a RETIRED AC.
- ACS-1200 (parked-ideas) = lifecycle state of a PRE-decomposition AC. This was
  the remaining empty quadrant; that emptiness is what earned a sibling L0 (next
  free hundred; ACS-400 already carries five L1s, and the ACS-800/ACS-900
  precedent is to mint a sibling rather than overload).

GE-113 was also considered and rejected: it covers work landing in the WRONG
PLACE with a clear explanation. Here the work is in the right place and the
message is already clear — the RULE needs a recognised exception. Correct
message, wrong verdict. GE-118 was rejected too: dependency resolution, not
rule correctness.

MOTIVATING EVIDENCE: the KM-200 tree (merged 2026-08-14, PR #433) was authored
under the cheap-capture convention — L0 + L1 only, parent `covered_by`
deliberately empty so the tree is visible in the store but structurally outside
the buildable backlog (`scan_ac_store.py` `_is_leaf` matches only L2/L3).
`check_ac_parent_covered_by` demanded the back-link on all six children; the
commit only landed with `SKIP=check-ac-parent-covered-by`. `scan_ac_orphans.py`
reports the same six as orphans (60 store-wide, 54 pre-existing).

L1 split (decompose each into L2; do NOT re-cut at L1):

- **ACS-1200a** — record a parked idea with nothing skipped. Surface:
  `check_ac_parent_covered_by.py`. **RECOGNITION, NOT SUPPRESSION**: the
  exemption must key off a positive, deliberate "this is parked" signal, never
  off the ABSENCE of children — absence is also exactly what a half-broken tree
  looks like, and an absence-keyed exemption silences real breakage. What the
  signal IS (field, readiness value, level+state combination) is an L2 decision.
  `[reference-doc]` is mandatory: `ac-schema.md` currently documents the
  back-link protocol as unconditional ("missing links block the commit"), so
  shipping without amending it leaves the written rule contradicting the
  enforced one.
- **ACS-1200b** — the health surfaces agree (`scan_ac_orphans.py`, plus any
  other reader that infers breakage from a missing link — ENUMERATE them; one
  unpatched reader keeps sending people to "repair" parked trees). The 54
  pre-existing orphans are NOT in scope and must not be swept up by the
  exemption.
- **ACS-1200c** — enforcement stays full-strength for decomposed trees. The
  guard-on-the-guard: without it, the cheapest implementation of ACS-1200a
  (just relax the rule) passes and the safeguard is gone rather than corrected.
  Its evidence must be in the NEGATIVE — a decomposed tree with a genuinely
  missing link is STILL blocked after the change.
- **ACS-1200d** — un-parking is deliberate and visible. Two failure modes:
  accidental un-parking (a "fix" silently promotes an undecomposed tree into the
  backlog) and parked-forever.

DO NOT DUPLICATE KM-200c: counting parked vs queued vs authoring-WIP populations
is KM-200c's remit. ACS-1200 defines and enforces the state; KM-200c reports on
it. KM-200c is itself parked, so ACS-1200 must not take a dependency on it.

CROSS-COMPONENT SEQUENCING: ACS-1200a and GE-120b (guardrail-engine) touch the
same file for opposite-direction reasons — ACS-1200a fixes WHICH rule
`check_ac_parent_covered_by` enforces; GE-120b fixes WHETHER it runs at all in a
given working copy. Landing GE-120b alone makes the wrong rule fire more
reliably. Sequence ACS-1200a with or before GE-120b, or ship them together.

ROADMAP FLAG (unresolved, for the user at the final gate): no `roadmap_phase` is
claimed. Phase 1's exit criteria are about clean installs and build idempotency;
store-convention health does not advance them. Either a phase claims this tree or
it stays unphased backlog. No roadmap or vision file was modified while authoring
it.

## ACS-1300 trustworthy-coverage-links: framing note for the BA/IT-PO (2026-09-01, PO)

ACS-1300 ("Trust the link between a requirement and the tests that prove it") is a
NEW root L0 in ac-store, slug folder `ACS-1300-trustworthy-coverage-links/`, three
L1 children ACS-1300a..c, origin_agent product-owner, readiness draft, priority
medium, NO `roadmap_phase` claimed (same reasoning as ACS-1200 above). Subject: the
`covered_by` record has decayed in two directions — forward rot (a passing test
carries a `# covers:` tag the record does not list) and inverse rot (the record
names a test file that no longer exists).

READ THIS BEFORE DECOMPOSING — A STALE DIAGNOSIS IS IN CIRCULATION. A BA
investigation reported BO-202 as the open root cause, claiming the in-drive
auto-fix skips L3 and greps only `tests/`. That is STALE. Verified 2026-09-01 on
branch fix/ac-coverage-backfill by reading `templates/agents/ac-fulfillment-gate.md`:
§3c searches `tests/ unit_tests/` with an explicit warning about the tests/-only
scoping, and §2f explicitly instructs NOT to skip the auto-fix eligibility check
for L3. The agent's own changelog dates the fix 2026-08-26. The BA was quoting
BO-202's `notes`, which describe the defect as filed on 2026-08-25. **Do not author
or decompose anything premised on closing that leak — it is closed for work that
flows through the ticket pipeline.** What remains is the historical backlog
(ACS-1300a) and a residual: the gate is a ticket-phase agent conditional on
`ac_traceability` frontmatter, so fast-lane and direct-commit paths still get no
link written (ACS-1300b).

GENERAL LESSON WORTH REUSING: an AC's `notes` field records the defect AS FILED. It
is not a current diagnosis and it does not self-update when the fix ships. Verify
against the implementing surface on the current branch before treating any `notes`
paragraph as live. BO-202 is the standing illustration — it is still
`work_status: todo` although its fix shipped, so the record that exists to keep
coverage honest is itself mis-recorded.

THE HARD CONSTRAINT, INHERITED BY EVERY DESCENDANT: **nothing in the ACS-1300 tree
writes `work_status`, at any level.** REFUSED, NOT DEFERRED. Restoring an evidence
link is not the same act as awarding a done badge; auto-promoting finished-state
from derived evidence manufactures a done claim on the one field the whole
phantom-done edifice rests on. Flipping the badge stays with `mark_ac_done.py` and
its own evidence gate. TQ-400f was authored and then closed unbuilt on 2026-09-01
partly for approaching this line. ACS-1300c makes the refusal falsifiable rather
than merely written down.

TWO PROPERTIES ESTABLISHED AT L0 SO CHILDREN INHERIT RATHER THAN RE-DERIVE:
- BYTE STABILITY — a record with nothing to repair is never opened for writing.
  NOT "written identically": a YAML load-and-dump round trip preserves every value
  while reformatting quoting, key order and line wrapping, which at ~3,749 records
  churns the whole store. TQ-400e-1 already owns this rule and its test shape
  (raw-byte hash before/after + an anti-no-op control in the same run) — point at
  it, do not restate it in a competing form.
- ABSTENTION OVER ACTION — untrustworthy evidence produces a reported abstention,
  never a silent skip and never a write.

L1 SPLIT (decompose each into L2; do NOT re-cut at L1):
- **ACS-1300a** — the one-off repair of the historical backlog, both directions of
  rot in one pass, one report. THE JOIN IS EXACT AND MECHANICAL (`# covers:` tag,
  id to id) — no text similarity, no keyword heuristics. That line is precisely why
  ACD-800 was the wrong parent, so it must not drift back toward heuristics at L2.
  documentation_triggers `[how-to]`.
- **ACS-1300b** — records that never pass through the ticket pipeline. First L2
  should be ENUMERATION of the bypassing delivery paths, derived from the repo, not
  from a note; one unenumerated path is a permanent slow refill. Prefer routing
  those paths to the existing link-writing behaviour over building a second writer.
  documentation_triggers `[sequence-diagram]`.
- **ACS-1300c** — the trust envelope (awards nothing / rewrites nothing already
  correct / abstains out loud). Same shape as TQ-400e one tree over. Every one of
  its three guarantees is satisfied by a tool that does nothing, so each L2 must
  assert in the SAME run that records genuinely needing repair were repaired.
  documentation_triggers `[reference-doc]` — the refusal belongs written down beside
  the field it protects, because TQ-400f is the evidence that it gets re-derived.

WHY A SIBLING L0 AND NOT A GRAFT (do not re-litigate): ACS-200 is structurally
broken (no L0 file; ACS-200d depends on a nonexistent ACS-200b) and already carries
a DO-NOT-HANG-HERE note in ACS-1100. ACS-1100 is adjacent but different — it governs
whether an ANSWER states its denominator, not whether the stored LINK is true, and
it is a `scope: standing` contract explicitly "not a home for" other surfaces; this
tree INHERITS it (every figure states its denominator) rather than parenting under
it. ACS-400b/e are the wrong subject and near cap. TQ-400d is the opposite direction
(finished records that cannot be proven); TQ-400a/e are at or over the L2 cap.
ACD-800 is the closest subject match but commits to heuristic discovery and to
backfilling `work_status` — parenting there would require rewriting its goal.

CAP ARITHMETIC: 3 L1s against the 7-cap. The BA's decomposition needed five L2s,
which under a single L1 fills the 5-cap with zero room for a documentation AC and
forces a later Pattern C split with mandatory ID renames. Across three L1s the same
five redistribute to roughly 4/4/4 including each L1's doc AC. No
`child_limit_override` is authored and none may be added.

MEASUREMENTS ARE PROVISIONAL AND LIVE ONLY IN `notes`, NEVER IN A `criteria` BLOCK.
Figures with their method and denominator are in ACS-1300's notes; an independent
re-measurement was in flight when the tree was authored. A criterion pinned to a
number is falsified by the next commit that changes it — the hand-typed "244 of 607"
in the artifact map is the in-house example.

## ACS-1400 complete-child-links: framing note for the BA/IT-PO (2026-09-08, PO)

ACS-1400 ("Trust a finished claim, because nothing it covers was left out of the
count") is a NEW root L0 in ac-store, slug folder `ACS-1400-complete-child-links/`,
four L1 children ACS-1400a–d, origin_agent BrainCandy, readiness draft, priority
medium, `roadmap_phase: phase_1`. Subject: the parent→CHILD relation in `covered_by`
— the set of parts a composite's done-claim is judged against.

**THE GOVERNANCE MAP IS NOW SIX TREES.** ACS-200 test coverage of live ACs
(structurally broken — no L0 file); ACS-400 who may edit a definition; ACS-900
code lifecycle of a retired AC; ACS-1200 the parked pre-decomposition state;
ACS-1300 the requirement→TEST link; **ACS-1400 the parent→CHILD link.** ACS-1300
and ACS-1400 are the two halves of one overloaded field — see ACS-1400d.

**WHY A SIBLING L0 AND NOT A GRAFT ONTO ACS-1300 (do not re-litigate).** ACS-1300
was the serious candidate — same field, four free L1 slots, and its notes already
carry the parent/child disagreement measurement. It was rejected **by that tree's
own written instruction**, not by PO judgement. `ACS-1300a-3` (approved,
BA-authored) states: *"Repairing a stale child list is NOT this tree's job. It is a
different operation on a different relation, it already has a tool in
scripts/ac_store/fix_ac_orphans.py... This AC abstains and reports; it must not
grow a child-list repair."* ACS-1300 explicitly disclaims all done-status
consequence ("it unblocks nothing"); ACS-1400 is entirely about done-status
trustworthiness. ACS-1300a-3 is the hand-off point — treat it as the seam.

**READ THIS BEFORE DECOMPOSING — "47 ORPHANS" IS FOUR POPULATIONS WITH OPPOSITE
CORRECT ACTIONS.** Measured 2026-09-08, whole store, branch `ac/orphaned-children`.
Do NOT let any criterion say "reconcile the orphans."

1. **6 deliberate — MUST NEVER BE REPAIRED.** KM-200a–f. `covered_by` is empty on
   purpose under the cheap-capture convention; the merge only landed with
   `SKIP=check-ac-parent-covered-by`. Already owned by ACS-1200a/b, which states
   pre-existing orphans must not be swept up.
2. **26 — the field is carrying two meanings.** 11 parents (ACS-300g-1, ACS-300i-1,
   BP-100b, BP-100b-6, INF-100c-1, INF-100c-3, KM-KGS-100e-1/5/6, UXP-544, UXP-545)
   hold ONLY test paths in `covered_by`. **Repair here has TEETH**: appending a
   child id flips `done_proof._has_resolvable_child` from leaf to composite,
   changing what the store believes can be finished. ACS-1300a-3 abstains on
   exactly these.
3. **~5 on records that are themselves `status: superseded_by`** (BO-100d-1,
   BO-100d-2, TKT-100a, TKT-100f; BP-100b too). ac-schema.md's status lifecycle is
   SILENT on whether a retired parent lists retired children — settle the
   convention before implementing.
4. **~10 of plain stale drift** — the shape the brief described. BO-100d (4),
   FIN-100h (1), UXP-400a/410a/412a/420a/421a (5).

**THE COMMIT-TIME HOOK HAS THREE ESCAPE HATCHES, NOT THE ONE CLAUDE.md DOCUMENTS.**
CLAUDE.md describes only the staged-set gap. `_check_file` ALSO returns `[]` unless
the ID-derived parent appears in the child's own `depends_on` — **that alone exempts
26 of the 47**, so staging the parent would have changed nothing for a majority.
Third: parent-absent-from-index fails open with a WARNING. Its silence means three
different things and only one is a pass; reuse the existing
`OUTCOME_COULD_NOT_CHECK` vocabulary already in that file rather than inventing a
second channel.

**BOTH THE SCAN AND THE REPAIR ALREADY EXIST — CHECK BEFORE SPECIFYING EITHER.**
`scan_ac_orphans.py` is correct and has been since 2026-06-08; it is wired to
**nothing** (zero references in `.github/`, `config/`, `templates/config/`,
`.pre-commit-config.yaml`). That is ACS-1400b's whole gap — wiring, not capability.
`fix_ac_orphans.py` performs the bulk repair with **no adjudication whatsoever**:
run today it repairs all 47, undoing the KM-200 decision and performing 25 writes
with done-proof consequences; its case-4 branch `yaml.dump`s whole files (violating
byte stability) and its docstring's claim that the hook "blocks all commits that
touch AC files" is false. **ACS-1400c is a safety problem on an existing tool, not
a greenfield build.** The urgency of this tree is that the unsafe repair is one
command away and the brief that prompts it is already written down.

**L1 SPLIT (decompose each into L2; do NOT re-cut at L1).** Seam is *when the answer
is produced and who acts on it*.
- **ACS-1400a** — at commit time; close the three hatches so silence is unambiguous.
  Collides with **ACS-1200a on the same file** (this makes it stricter, that makes it
  more permissive) — sequence them. `[reference-doc]`: ac-schema.md currently
  describes an unconditional blocking rule the code does not implement.
- **ACS-1400b** — out-of-band store-wide reporting. A required gate that blocks on 47
  pre-existing orphans is unshippable before c runs; report first, block later, and
  say so. Copy `validate_ac_schema.py`'s wiring **and its scar** (bare-directory
  no-op exited 0 having checked zero files for eight days) — state the population
  examined. `[how-to]`.
- **ACS-1400c** — the adjudicated one-off pass. **"Done" is NOT zero orphans**; a
  store reporting six labelled deliberate exclusions is healthy, and any criterion
  binding success to zero forces the six wrong repairs. `[how-to]`.
- **ACS-1400d** — split the field so child links and test links have separate homes.
  The durable fix for population 2. `[reference-doc, component-diagram]`.

**ACS-1400d IS FLAGGED FOR THE USER, NOT ASSUMED.** ACS-1300a-3 names the field
split as "the real fix" and places it out of scope **twice** — it is deliberately
homeless, and it is the root cause of the largest population. It is also by far the
most expensive item here. Deferring it to its own L0 is reasonable and a/b/c survive
it; what must not happen is quiet omission, which is how it became homeless.

**INHERITED FROM ACS-1300, IN THAT TREE'S OWN FORM — DO NOT RE-DERIVE.** Byte
stability (TQ-400e-1 owns the rule and the test shape: DO NOT WRITE, not
write-the-same) and abstention-over-action (reported abstention, never a silent
skip). This tree needs abstention more than ACS-1300 did, because populations 1 and
3 are records where the correct action is to do nothing AND SAY SO.

**EVERY SAFETY GUARANTEE IN THIS TREE IS SATISFIED BY A TOOL THAT DOES NOTHING.**
"Left the parked records alone", "byte-stable", "changed no done-proof verdict" are
all trivially true of a no-op. Each must be asserted in the SAME invocation as a
repair that genuinely happened — copy ACS-1300a-3's pairing test. Bind outcomes to
`done_proof`'s and the back-link hook's **real verdicts**, not to re-implementations.
And note the hook reads the git index or `HOOK_TEST_FILES`, never argv, so any test
must confirm it actually saw the file.

**HARD REFUSAL, INHERITED: nothing in this tree writes `work_status`, at any level.**
The temptation is sharper here than in ACS-1300 because the motivating investigation
was a sweep of composites marked done with unfinished children, so "we just fixed the
child list, now recompute the badge" is the obvious next line. Correcting the count
and re-judging the claim are two acts; only the first belongs here.

GENERAL LESSON WORTH REUSING BEYOND THIS TREE: a single confident integrity number is
usually several populations with opposite correct actions. Triage per-record before
specifying any store-wide cleanup — and check whether the tool you are about to
commission already exists and is the hazard rather than the gap.
