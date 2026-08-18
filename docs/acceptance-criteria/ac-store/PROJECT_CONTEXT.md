---
title: "ac-store — AC store context"
description: Cross-agent conventions and standing notes for PO v3 / BA v3 / IT PO v3 authoring
  and decomposing ACs in the ac-store component (prefix ACS).
created: '2026-08-14'
last_updated: '2026-08-14'
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
