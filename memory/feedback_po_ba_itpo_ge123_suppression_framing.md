# PO learnings — GE-123 (suppression narrows, never disables) framing

Captured 2026-08-18 (product-owner) authoring a new L0 + 4 L1s in
`guardrail-engine`. Written to `memory/` rather than the component
PROJECT_CONTEXT.md because the Edit tool was disabled for that session and a
wholesale Write over a 245-line shared file was judged too risky. **Fold these
sections into `docs/acceptance-criteria/guardrail-engine/PROJECT_CONTEXT.md`
when next editing it.**

## GE-120 is CURRENTLY a duplicated id — observed 2026-08-18

Two records claim `GE-120`: the L0 tree
`guardrail-engine/GE-120-green-means-checked/GE-120.yaml` (renamed onto this id
from its retired predecessor by origin/main PR #453) and a loose L2 at
`guardrail-engine/GE-120.yaml` (subject: the doc-frontmatter guard enforcing the
declared document types). Same id, different levels, different subjects — the
same shape as the earlier collision the PROJECT_CONTEXT records as resolved. It
is NOT resolved; the rename relocated it. Flagged, not fixed. It is exactly the
defect class GE-122a exists to catch, and GE-122e ("repair the drift that
already exists") should treat it as a live instance rather than assuming the
store is clean.

(The retired predecessor id is deliberately not written out here. A guard added
by GE-122e-1 fails the build on any live citation of it outside dated
historical records — changelogs, tickets, the guardrail-engine AC tree — and
this note is none of those. PR #453 is the durable pointer.)

**RESOLVED 2026-08-18 — the two paragraphs above are a dated observation and are
left as written; this is the current state.** The loose L2 was renumbered to
`GE-118c` and moved into
`docs/acceptance-criteria/guardrail-engine/GE-118-hooks-work-in-worktrees/`,
parented under `GE-118` (now 3 of 7 children). `GE-120` resolves to exactly one
record — the L0 goal tree — and a store-wide sweep finds 3,185 records with
3,185 distinct ids, zero duplicates. Three things a future authoring run should
take from how it was resolved:

- **The goal tree could not be the parent even though it was the semantically
  right one.** `unit_tests/commit_guardian/test_ge_122e_1.py` asserts
  `git diff origin/main -- .../GE-120-green-means-checked/` is EMPTY, so neither
  adding a file to that folder nor appending to its `covered_by` is possible.
  Check for a guard test over a candidate parent's folder BEFORE choosing it —
  this is the second consecutive collision where the obvious parent was frozen.
- **A suffix-shaped id beat a free root number.** `GE-124` was free by both
  tests and was still rejected: `derive_parent_id()` returns `None` for a root
  id, so the parent link would have been unpoliceable.
- **The test module was renamed** to `test_ge_118c_doc_types_deployed_resolution.py`.
  Unlike the earlier collision — where the old id was RETIRED and its stale
  filename resolved to nothing — `test_ge_120_*` would have resolved to a live,
  different record.

The id-ALLOCATION defect that produced this collision is untouched and still
open: see `docs/known-issues/ac-driven-dev.md` KI-ACD-008.

## Root-id registry for guardrail-engine, 2026-08-18

Taken: GE-100..GE-113, GE-114 (loose, as `GE-114-N`), GE-115 (loose), GE-116,
GE-117, GE-118 (with the suffix-shaped child GE-118c), GE-120 (was
claimed twice — resolved 2026-08-18, see above), GE-122, GE-123.

- The id between GE-118 and GE-120 is RETIRED and must never be reissued (see
  PR #453; not written out here, per the GE-122e-1 citation guard).
- `GE-121` must not be reissued either: GE-111f's and GE-122e's prose cite it
  repeatedly as the rejected candidate for the GE-111f move, so a reader would
  resolve it to the wrong thing.
- Next free root at time of writing: `GE-124`. Re-verify rather than trusting
  this number, and scan the LOOSE `GE-*.yaml` files at component root as well as
  the folders — a folder-only listing under-reports the taken ids.

## GE-123: framing note for the BA and IT PO

New root L0 `GE-123-suppression-narrows-never-disables/`, four L1 children
GE-123a..d, `origin_agent: product-owner`, `readiness: draft`, `priority:
medium`, `roadmap_phase: phase_1`, `change_target: code`, `risk_surface: safety`.
Subject: the secrets scanner can be switched off — partially or completely —
without anyone noticing. Through-line: **a suppression is a scalpel and currently
behaves like a switch.** Full evidence, confidence labels, cut rationale and
inherited constraints live in the L0's `notes`; read that before decomposing.

`risk_surface: safety` (not the family's usual `contract_boundary`) was chosen
deliberately: under `config/guardrail_gates.yaml` both map to the same mandatory
agent set for `change_target: code`, so no scrutiny is lost, and "could cause
harm or irreversible state" is the honest description of a credential entering
permanent history.

### L1 cut — by guarantee, not by defect

One-L1-per-observed-defect was the rejected alternative: it yields point patches
and hides that two of the three observed defects are instances of one invariant.
This component already has four successive point patches in this area.

- **GE-123a** — the coverage FLOOR: a file is judged on its contents, not its
  name.
- **GE-123b** — the INVARIANT that (a) is an instance of: no single suppression
  takes a file's effective coverage to zero.
- **GE-123c** — HONESTY of the instruction: an entry that can never match says
  so.
- **GE-123d** — the OPPOSITE error: prose describing a risk is not treated as
  taking one. Included in this goal because false positives are the pressure
  that makes people write suppressions in the first place.

### Boundary with GE-113c-3-v — the sharpest hazard for the BA

GE-113c-3-v is DONE and already covers malformed entries: a target path with
zero path segments in any spelling, a line with no separator at all, the
warn-and-skip disposition, the warning's information content (file, 1-based line
number, verbatim text), per-line-not-per-file skipping, and silence on
blank/comment lines. **GE-123c is the RESIDUAL only** — an entry that parses
SUCCESSFULLY into something the author did not write (observed: a trailing
explanatory comment absorbed into the line-number field, so the entry never
matches and never warns). Re-specifying -v's scenarios reopens completed work;
reuse its warning contract rather than inventing a second one.

### Standing scanner fact that invalidates casual examples

`scan_file` short-circuits environment-named files to a single name-based
finding and never reads their content. A sibling audit found two existing ACs
describing scenarios unreachable through the real entry point for exactly this
reason. Never use an env filename as a generic "a file with a finding" example —
use an ordinary `.py` filename. The coverage-collapse behaviour itself is
legitimately the subject of GE-123a and must be described there; the ban is on
casual illustrative use elsewhere.

### Verification standard for this tree

Every claim in GE-123 was measured through the path a real commit takes: five
env-named files containing an AWS key, an RSA private-key header, a password and
a high-entropy token produced **0 findings, exit 0** with ONE allowlist line in
place; the same content in a `.py` file produced **4**. Unit-level coverage of
the matcher in isolation does not discharge any L2 in this tree.

### Negative arms are mandatory here, not optional hardening

GE-123b's scenarios are all satisfiable by an implementation that stops
honouring suppressions entirely. GE-123d's widening is satisfiable by an
exemption broad enough to smuggle a live credential into a ticket. Each needs a
regression arm proving that the thing which should still work still works.
