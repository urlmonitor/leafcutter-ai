---
title: "guardrail-engine — AC store context"
description: Conventions and standing notes for authoring/decomposing ACs in the guardrail-engine
  component (prefix GE).
created: '2026-08-14'
last_updated: '2026-08-17'
type: tutorial
status: active
components:
  - commit_guardian
  - precommit_hooks
---
# guardrail-engine — AC store context

Conventions and standing notes for authoring/decomposing ACs in the
`guardrail-engine` component (prefix `GE`). Best-effort knowledge, captured by
authoring agents across runs.

## Store structure convention (GE-1xx family)

- GE-1xx ACs are authored as **L1 directly under the component** — there is no
  separate L0 root file (see GE-100, GE-107). Each L1 lives in its own
  feature folder `GE-NNN-<slug>/` and its `depends_on` is `[]`.
- L2 leaves use the **alpha suffix** on the L1 id: `GE-107` (L1) →
  `GE-107a` (L2). Deeper leaves add a numeric segment: `GE-100a` → `GE-100a-1`.
- `created_by` on a root L1 points to **its own file path** (self-reference),
  not a ticket path — see GE-107 and GE-108.
- The `validate_ac_schema.py` wrapper accepts the workflow fields that the raw
  JSON schema's `additionalProperties: false` appears to forbid
  (`req_status`, `work_status`, `level`, `doc_links`, `origin_agent`,
  `created`, `amended_by`, `superseded_by`, `covered_by`, `implemented_by`,
  `assigned_agent`, `estimated_complexity`, `it_requirements`, `delivers_to`,
  `expects_from`). Mirror an existing sibling file's field set rather than the
  bare schema.

> **Amendment (2026-08-14):** the "no L0 root file" convention above describes
> the ORIGINAL GE-1xx family only. Newer trees (GE-113, GE-116, GE-118, GE-120)
> are authored as a proper L0 root + L1 children in a `GE-NNN-<slug>/` folder.
> Follow the newer pattern for new work; the note above is retained because the
> older GE-100/GE-107 files still have the flat shape.

## Exception-handling guard lineage (GE-107 / GE-108)

The `check_exception_handling.py` pre-commit guard enforces CLAUDE.md Error
Handling Policy Rules 1 and 3. Two sibling L1s govern distinct axes:

- **GE-107** — *scope*: WHERE the guard applies (production code only; test
  files exempt). Done (GE-107a leaf).
- **GE-108** — *faithfulness/accuracy*: HOW faithfully the guard matches the
  documented policy. Authored 2026-06-17 (readiness: draft, origin BrainCandy).

### GE-108 intended L2 decomposition (for the BA)

The three gaps below are framed at L1 in benefit language; each becomes one L2
leaf (likely `GE-108a` / `GE-108b` / `GE-108c`):

1. **Subprocess as an I/O boundary.** Rule 1 names "subprocess calls" as
   external I/O that must be wrapped. The guard currently detects only
   `requests.*`, `open()`, and `cursor.execute/executemany/callproc`. Unwrapped
   `subprocess.run / Popen / call / check_call / check_output / getoutput` pass
   with no IO-001 violation — close this gap.
2. **Blind-catch logging heuristic precision (Rule 3).** The guard treats any
   call whose name looks logging-like (`log/logger/warn/error/info/debug/print`)
   as "non-silent". Two false negatives: (a) a user-defined function
   coincidentally named `error()/info()/debug()` that is not a real logger is
   wrongly accepted; (b) a handler that only logs at DEBUG/INFO/print level is
   accepted, violating Rule 3's WARNING-or-higher requirement.
3. **Tuple exception label accuracy.** For `except (ValueError, Exception):` the
   BLE001 message reports the caught type as just "Exception" instead of the
   full tuple. Detection and line/col are already correct — only the
   human-readable label is imprecise.

## Framing preference (user: BrainCandy)

- User-authored ACs set `origin_agent: BrainCandy`; BA-created ACs set
  `origin_agent: business-analyst`.
- Priority is finalised at the workflow's final gate, not at authoring time —
  new L0/L1 ACs are written `priority: medium`, `readiness: draft`.

## GE-120 green-means-checked: framing note for the BA/IT-PO (2026-08-14, PO)

GE-120 ("Trust that a green check actually checked something") is a NEW root L0
in guardrail-engine, slug folder `GE-120-green-means-checked/`, four L1 children
GE-120a..d, origin_agent BrainCandy, readiness draft, priority medium,
roadmap_phase phase_1. It generalises a defect class: a commit-guardian check
that cannot reach what it needs exits 0 and reports success, so "green" is
indistinguishable from "did not run".

PLACEMENT PRECEDENT (reuse this reasoning): triage suggested grafting onto
GE-118a. Rejected — GE-118a is an L1 whose SUBJECT is one check (check-secrets)
and whose only child is done; hanging a cross-cutting policy under a
single-instance L1 inverts containment and reopens a complete node. GE-118's L0
was also rejected as parent: its scope is dependency RESOLUTION from the
deployed layout, while two of GE-120's L1s cover degrade paths that are not
resolution failures. Standing rule for this component: **GE-118 = the point
fixes that landed (GE-118a-1, GE-118b, both done); GE-120 = the class they are
instances of.** GE-118 was deliberately NOT amended or superseded.

FAIL-OPEN CONTRADICTION — load-bearing, do NOT let decomposition flatten it:
this component has a deliberate fail-open convention (internal error → exit 0 +
stderr warning so a script bug never blocks an unrelated commit), documented in
the ac-store PROJECT_CONTEXT and approved as GE-116a-1-iii ("Unparseable agent
definition fails open and does not block the commit"). GE-120 does NOT repeal
it. The line it draws: fail-open on ONE bad input while the check still ran is
fine; reporting SUCCESS for a check that never ran is not. The unit of the rule
is **visibility**, not blocking. Whether a cannot-run condition should also
BLOCK is a per-check L2 decision — there is no blanket default.

L1 split (decompose each into L2; do NOT re-cut at L1):

- **GE-120a** — the POLICY: a check that cannot run says so. Cross-cutting over
  the 18 checks sharing the `_find_project_root` / `parents[]` root-walk
  pattern. `documentation_triggers: [reference-doc]` — the opposite rule is what
  is currently written down.
- **GE-120b** — PARITY: same work, same verdict from any working copy. The
  acceptance shape is the observed pair — `check_ac_parent_covered_by.py`
  exiting 0 with "skipping check (fail-open)" without the deployed-layout link
  vs. blocking with 6 violations WITH it, on identical staged files. The how-to
  trigger is a REPLACEMENT: the manual "link `.leafcutter` into your worktree"
  pre-drive step must be deleted, not left beside the fix.
- **GE-120c** — PROOF: verified by running the deployed checks from a separate
  working copy. Today's unit tests import from the source tree — the one layout
  where the bug cannot reproduce — so they are not evidence.
  `[component-diagram]` for the new harness.
- **GE-120d** — SET-UP: `setup_ticket_worktree.py`'s own "graceful no-op" on
  `verify_precommit_active.py` / `install_pre_commit_shims.py`. Different
  script, so it is its own L1; may be folded into GE-120b ONLY if decomposition
  proves the same root cause — and say so explicitly rather than dropping it.

EVIDENCE CONFIDENCE (carry the labels through — do not upgrade them): the
`check_ac_parent_covered_by` pair is DIRECTLY OBSERVED AND REPRODUCIBLE. The
"26 schema-violating files looked clean" figure from `check_ac_schema.py`'s
silent degrade to manual field validation is REPORTED BY A PARALLEL SESSION AND
UNVERIFIED — GE-120c is what makes it checkable.

REPEAT-DEFECT HISTORY: GE-112 already fixed an adjacent defect in
`check_ac_schema.py`. Three prior point patches exist in this area (GE-112,
GE-118a-1, GE-118b). Favour a structural fix; a fourth point patch is the
failure mode to avoid.

SEQUENCING WITH ac-store: GE-120b and ACS-1200a touch the same file
(`check_ac_parent_covered_by.py`) for opposite-direction reasons — GE-120b makes
it run everywhere, ACS-1200a makes it enforce the right rule. A check that
starts running reliably everywhere while still holding the wrong rule blocks
every parked idea MORE consistently. Sequence ACS-1200a with or before GE-120b,
or land them in the same release.

## GE-119 is a DUPLICATED id — do not mint by "the next number looks free" (2026-08-17)

Two unrelated ACs both claim `GE-119`: the L0 tree
`GE-119-green-means-checked/GE-119.yaml` and a parentless L2 at
`guardrail-engine/GE-119.yaml` (authored by `/quick-fix` from a different
worktree, subject: the contract-shrinking guard distinguishing an edited test
from a deleted one). Different levels, different subjects, same id; neither has
been renumbered yet. When picking a new root id in this component, scan the FLAT
files as well as the folders — `GE-114-*.yaml` and `GE-115.yaml` also sit loose
at component root, so a folder-only listing under-reports the taken ids.

**Update (2026-08-18, reconciliation after origin/main merge):** the sentence
this note originally ended on — "`GE-120` was minted 2026-08-17; the next free
root is `GE-121`." — is now wrong on both halves and is corrected here rather
than silently rewritten. The parentless L2 above was renumbered to `GE-111f`
under `GE-111`, resolving this collision from that side. Separately and
concurrently, `origin/main` (PR #453) resolved the SAME collision from the other
side by renaming the L0 tree `GE-119-green-means-checked/` itself to
`GE-120-green-means-checked/`. `GE-119` is therefore now a RETIRED identifier,
claimed by no record, and must never be reissued. The `GE-120` this note minted
for the unrelated "numbers-mean-one-thing" tree was independently reused by that
same main-side rename, so that tree was renumbered again, to `GE-122` — **not**
`GE-121`, which that tree's own prose cites roughly twenty times as the rejected
candidate for the `GE-111f` move and which would therefore resolve to the wrong
thing if reused. Re-verify the next free root at time of use rather than trusting
any number recorded in this note.

## GE-122 numbers-mean-one-thing: framing note for the BA/IT-PO (2026-08-17, PO)

New root L0 minted as `GE-120-numbers-mean-one-thing/`; renumbered 2026-08-18 to
`GE-122-numbers-mean-one-thing/` after an identifier collision with origin/main
(see the update note above this section) — five L1 children GE-122a..e,
origin_agent BrainCandy, readiness draft, priority medium, roadmap_phase
phase_1. Scope: id / number drift across FOUR namespaces — AC ids, ticket ids +
lifecycle location, ADR numbers, diagram sequence numbers — enforced at three
stages (authoring-time session hook, pre-commit, CI).

L1 CUT — deliberate; do NOT re-cut per namespace. One-L1-per-namespace was the
rejected alternative (four near-identical ACs that hide where the real
differences are). The cut is by GUARANTEE, not by artifact type:

- **GE-122a** — the invariant: one number, one thing. Covers BOTH the collision
  shape and the one-id-two-lifecycle-copies shape, and all four namespaces,
  because for this guarantee they genuinely are the same requirement applied
  four times.
- **GE-122b** — enrolment: an artifact that takes NO id can never collide, so
  without this L1 the uniqueness promise has a silent opt-out.
- **GE-122c** — remediation quality: you are told which two things collide and
  what to do, not merely blocked.
- **GE-122d** — strength of the promise: three stages, unskippable backstop.
- **GE-122e** — one-time repair of the drift that already exists, so the guard
  does not certify a broken state as clean.

THREE DISTINCT DRIFT SHAPES — only the first is a collision. (1) two artifacts
claim one id (GE-119 today; BO-2700 previously, renumbered to BO-2900);
(2) an artifact takes no id at all — 11 unnumbered diagrams sit beside 12
correctly-sequenced ones despite `scripts/next_diagram_seq.py` existing (drift by
abandonment); (3) one id, two files in different lifecycle folders free to
disagree — 5 tickets (4× 00_inbox+99_done, 1× 00_inbox+01_todo).
Measured 2026-08-17: 2,969 AC files / 2,968 distinct ids; ADRs 1..33 contiguous,
zero duplicates, zero gaps. Guarding ADR numbers LOCKS IN a good state — do not
write them up as though a defect existed.

ROOT CAUSE IS THE UNIT OF INSPECTION: the AC schema validator is PER-FILE, so it
is structurally incapable of noticing that a second file elsewhere claims the
same id. No gate in the repo runs a whole-store uniqueness pass. Another
per-file rule cannot satisfy GE-122a.

HONESTY CONSTRAINT ON THE "SPAWN A BA" REQUIREMENT (load-bearing, GE-122c):
a git pre-commit hook is a plain subprocess — it can BLOCK and PRINT, it CANNOT
spawn an agent. A CI job can FAIL and PRINT, it CANNOT spawn an agent. Only a
Claude Code PostToolUse hook on Edit|Write runs inside the live session with its
output fed back into the running agent's context; `ticket_frontmatter_guard.py`
is the existing precedent for that hook point. ANTI-PRECEDENT that must not be
repeated: `templates/scripts/commit_guardian/check_glossary_coverage.py` is
documented in CLAUDE.md as "dispatches the glossary-triage agent automatically"
and does not — its docstring says "Returns: Always 0 (fail-open contract)" and
`_dispatch_triage_standalone` blacklists every novel term with reason
"standalone-mode placeholder". A documented-but-dead remediation path is worse
than none, because authors believe they are covered. Any L2 claiming an agent is
dispatched needs a test that proves it actually happens.

BOUNDARY WITH ACS-800a-3 — do NOT close either as a duplicate of the other.
ACS-800a-3 (`ac-store/ACS-800-stable-ac-identity/`, readiness approved, priority
high, work_status todo) already specifies store-wide AC-id uniqueness, but it
depends on ACS-800a — a 38-file approved but entirely UNBUILT restructure that
replaces today's position-encoded ids with opaque, position-independent UIDs.
User decision: DECOUPLE. GE-122 enforces uniqueness on TODAY's position-encoded
ids and ships now; ACS-800a-3 carries the same invariant forward to the future
UID model. Complementary and sequential. The ACS-800 tree must NOT be edited,
reopened, or re-authored by GE-122 work.

INHERITED, NOT REPEALED: GE-119's "a check that cannot run says so" and this
component's deliberate fail-open convention (GE-116a-1-iii) both apply to GE-122
unchanged. The new hazard specific to a whole-store check is "I could not read
the whole store, therefore it is fine" — decide block-vs-announce per stage
explicitly at L2.

## SECOND id collision, on GE-120 this time — resolved 2026-08-18

`GE-120` was claimed by two unrelated records for about 24 hours: the L0 goal
tree `GE-120-green-means-checked/` (renamed onto that id by PR #453 on
2026-08-17) and a loose L2 at the namespace root authored by `/quick-fix` via
`/plan-feature` in PR #466 on 2026-08-18 ("A guard enforces the document types
the project declared..."). Same defect class as the GE-119 collision one day
earlier, same cause: the id-allocation step did not see ids owned by feature
FOLDERS. See `docs/known-issues/ac-driven-dev.md` KI-ACD-008.

**Resolution: the loose L2 moved, and it became `GE-118c` under `GE-118`.**
Three rules were applied and all three are reusable:

1. **The number was chosen for its SHAPE, not for being free.** `GE-124` was
   free by ADR-029's both-tests rule and was still rejected. `derive_parent_id()`
   returns `None` for a root-shaped id, and both `check_ac_parent_covered_by.py`
   and `scan_ac_orphans.py` derive a parent from id shape alone — neither reads
   the documented `parent:` field. A root-shaped id therefore carries a parent
   link that no gate can police. Take the next free suffix under the chosen
   parent. (Inherited from GE-122e-1; this is its second application.)

2. **Check whether the attractive parent is FROZEN before assuming it is
   available.** GE-120 was the semantically right parent — a guard silently
   substituting a narrower built-in list is textbook "green when it could not
   check". It was mechanically forbidden:
   `unit_tests/commit_guardian/test_ge_122e_1.py` asserts
   `git diff origin/main -- .../GE-120-green-means-checked/` is EMPTY, so
   neither adding a file to that folder nor appending to `GE-120.yaml`'s
   `covered_by` is possible without turning that guard red. Every `GE-120a..e`
   is independently at the 5-child L2 cap, closing the other route.
   **This is the second time in two days that the semantically obvious parent
   turned out to be a byte-frozen survivor set.** Check the guard tests over a
   candidate parent's folder BEFORE choosing it.

3. **The standing "GE-118 is not amended" rule was read for its purpose, not
   its letter.** That rule (recorded above and in GE-120's L0 notes) exists to
   stop the cross-cutting green-means-checked POLICY being grafted onto the
   point-fix tree, which would put the general rule beneath a specific
   instance. Adding a third point fix of the same shape as `GE-118b` — same
   hand-counted `parents[2]`, same hardcoded `leafcutter` segment, same silent
   no-op — does not invert containment. GE-118 is now 3 of 7.
   Still true, and now more visibly so: GE-112, GE-118a-1, GE-118b and GE-118c
   are four point patches in this area. That is the argument for building
   GE-120, not against filing the fourth one where it belongs.

> **Correction (2026-09-01, PO): rule 2 above is STALE and must not be relied on.**
> The byte-identity freeze over `GE-120-green-means-checked/` no longer exists.
> `unit_tests/commit_guardian/test_ge_122e_1.py` was amended **2026-08-18** — eight
> days before GE-126's L0 notes repeated the freeze as current fact — from
> `git diff origin/main -- <folder>` must be EMPTY to a one-directional **id-stability**
> set difference: every id the folder claimed at the baseline must still be claimed, and
> every record under the folder must declare a `GE-120*` id. Its own docstring states that
> adding a record is "ordinary growth ... and must not fail." Verified empirically on
> 2026-09-01: adding `GE-120f.yaml` and appending to `GE-120.yaml`'s `covered_by` leaves
> all six tests in that module green. GE-120 is an available parent again; what is NOT
> available is a sixth L2 under any of GE-120a/b/d/e or any GE-126a..e (all at the 5 cap,
> GE-120c already at 6 on a live `child_limit_override`). The room in this family is the
> two free L1 slots under each of the two L0s — GE-120f took one of GE-120's.
> The general rule this makes concrete: **the freeze note and the guard test drift apart,
> and only the guard test is binding.** Read the test.

**Also settled here: a test module IS a citation.** The GE-119 repair left
`test_ge_119_contract_shrinking_rename_aware.py` under its old name. That was
tolerable because `GE-119` is RETIRED — the stale name resolves to nothing. It
was NOT tolerable here: `test_ge_120_*` would have resolved to a LIVE, DIFFERENT
record, which ADR-029 calls out as worse than the ambiguity being repaired. The
module was renamed to `test_ge_118c_doc_types_deployed_resolution.py`. Rule:
rename when the old id still resolves to something; leave it when the old id is
retired.
