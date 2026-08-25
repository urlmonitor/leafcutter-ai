---
title: "Known issues — knowledge-management"
description: "Open, observed defects in the knowledge-management component: the artifact knowledge graph, its trust ratings, and the coverage answers derived from the AC store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-25
components:
  - knowledge_management
related_docs:
  - docs/architecture/components/knowledge-management.md
  - docs/reference/artifact-knowledge-graph-data-map.md
  - docs/reference/artifact-knowledge-graph.graph.json
---

# Known issues — knowledge-management

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-KM-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-KM-001 — SourceFile → AC does not exist, so nothing can answer "which ACs govern this file?"

- **Severity:** high
- **Status:** open — recorded as a `status: absent` edge, no AC authored
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json` (edge `source-implements-ac`)

**Symptom.** The graph has no edge from a source file back to the acceptance criteria
that govern it. Before touching a file you cannot mechanically ask what behaviour is
specified against it, so "what must I not break here?" is answered by reading and
recall rather than by traversal. This is the single most load-bearing missing relation
for refactoring, and it is the direction the graph was commissioned to serve.

**Evidence.** The edge is recorded in the graph JSON with `"status": "absent"` and no
`field`, alongside three other absent edges (`test-exercises-source`,
`changelog-delivers-ac`, `mockup-realizes-ac`). The reverse edge (`ac-implements`, AC →
SourceFile via `implemented_by`) exists but is rated untrusted, so inverting it does not
recover the answer.

**Best available substitute today.** `Ticket.files_touched` → the ticket's
`ac_traceability` block. Two hops, and only as good as the declared file list.

**Why it is not just "not built yet".** The absent edges are drawn in the Atlas as red
dashed gaps precisely so this stays visible. Recording it here escalates it from
"documented gap" to "next design decision" — it needs a decision between marker comments
in source and a derived index built from ticket traceability before any AC can be
written.

**Candidate home when it earns an AC.** `KM-ADM-100b` ("a connection the project does not
have shows up as a gap you can see") — this issue is the highest-value instance of that
L1, and the L1 is where a future child belongs.

---

### KI-KM-002 — 244 of 607 done ACs have no covering test; the ratchet holds the floor, TQ-400d owns the drawdown

- **Severity:** high
- **Status:** open — floor ratcheted by `KM-ADM-005`; retirement owned by `TQ-400d` (draft, unbuilt)
- **Occurrences:** 1
- **First seen:** 2026-08-13 (measured) · **Last seen:** 2026-08-18
- **Where:** the AC store as a whole; ratchet at `unit_tests/docs/test_artifact_graph_covers_scope.py`

**Symptom.** Roughly 40% of ACs marked `work_status: done` carry no `# covers:` test tag
anywhere in `unit_tests/`, `tests/`, or `leafcutter-web/`. "Done" therefore does not mean
"test-proven" for most of the store's history, and any tool that counts done ACs as
covered is reporting a number nobody computed.

**Root cause.** `check-done-proof` is **diff-scoped**: it evaluates only the ACs changed
in the current commit or PR, and never re-examines a done AC that predates the gate. The
gate is genuinely enforced — it just never looked at the back catalogue.

**Evidence.** 607 `work_status: done` ACs; 363 tagged by at least one `# covers:`
reference; 244 untagged (measured 2026-08-13). `HIGH_WATER_MARK = 244` in the ratchet
test fails the build if that count rises.

**What is and is not fixed.** `KM-ADM-005` shipped the measurement, the scope disclosure
on the `test-covers` edge, and the ratchet — so the backlog cannot grow. It does **not**
retire any of the 244.

**Who owns the retirement (corrected 2026-08-18).** This entry previously said the
drawdown "has no AC and no owner". That was wrong on the day it was written.
`TQ-400d` — "the pile of unproven finished work gets worked through, not written off",
authored 2026-08-17 with five L2 children covering the worked list, per-item decisions,
progress measurement and a triage how-to — owns exactly this pile. `TQ-400a` owns the
store-wide sweep that produces the inventory. Do **not** author a new AC for it; the
work is specified and unbuilt, which is a scheduling problem, not a gap.

**Watch out — the pile has two different counts.** `KM-ADM-005` says 244 of 607
(2026-08-13, all levels, ids quote-stripped before joining); `TQ-400`'s L0 notes say 240
of 641 (2026-08-17, done L2/L3 records only). Neither cites the other, so the delta
cannot be read as progress. Reconcile the inclusion rules before triaging, and state the
rule alongside whichever number you publish.

**Related.** `ACS-1100-honest-coverage-answers` (draft, unbuilt, `scope: standing`) is the
general contract this is one instance of, and the disagreement above is that contract's
defect occurring inside its own reconciliation. The two are cross-linked in the store as
of 2026-08-18: `ACS-1100` notes carry a per-L1 breakdown of what `KM-ADM-005` already
satisfies, and `KM-ADM-005` carries `doc_links` back to `ACS-1100` and `TQ-400d`.

---

### KI-KM-003 — The map understates `ticket-touches`: config flipped to strict, the rating and both notes did not

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json` (edge `ticket-touches`);
  `templates/scripts/commit_guardian/commit_guardian.json` (hook `_comment`, and the
  `files_touched_reconciliation` section)

**Symptom.** `files_touched_reconciliation.strict` is now `true` on main, so undeclared
source files **block** a ticket commit. But the graph JSON still rates the edge
`enforcement: "warn"` and its note still reads "advisory: files_touched_reconciliation.enabled
true, strict false … Flipping strict:true promotes this edge to 'enforced'." A reader of
the map concludes the edge is advisory when it now blocks.

**Second, same drift, different file.** The hook's own `_comment` in
`commit_guardian.json` still says "Advisory by default (… strict: false)" while the
`files_touched_reconciliation` section eight hundred lines below sets `"strict": true`.
The config contradicts itself.

**Why the guard did not catch it.** `unit_tests/docs/test_artifact_graph_trust_ratings.py`
derives expected enforcement from **hook registration** in `commit_guardian.json` — which
is exactly right for `KM-ADM-001`'s purpose, and is why `ac-tested` was correctly
demoted. It contains zero references to `strict`, so a registered hook that changes from
advisory to blocking is invisible to it. The rating drifted inside 24 hours of the parity
test shipping.

**Note the direction.** The map is wrong conservatively — it under-claims trust. That is
the safe direction, and it is still drift: the whole point of the ratings is that a
reader can act on them.

**Suggested fix shape.** Extend the trust-ratings test to read the three-state config
(`enabled` / `strict`) for hooks that have one, not just registration. Then correct the
rating, the note, and the stale `_comment` together.

**Candidate home when it earns an AC.** `KM-ADM-100a` ("a connection's trust rating
reflects what actually runs, and says how much it covered") — this is the same failure
class as `KM-ADM-001`, one config field deeper.

---

### KI-KM-004 — `check_ac_coverage.py` exists on disk but is registered nowhere, so `covered_by` test entries are never read

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_ac_coverage.py`

**Symptom.** A hook script that looks like a live coverage gate is not in
`commit_guardian.json`'s `hooks_manifest`, so it never runs. Nothing in the repo reads
the test entries in an AC's `covered_by` field. The `ac-tested` edge (AC → Test) is
therefore unenforced despite a plausible-looking enforcement script sitting next to the
registered hooks.

**Evidence.** Zero matches for `check_ac_coverage` or `ac-coverage` in
`templates/scripts/commit_guardian/commit_guardian.json`. The `ac-tested` edge is rated
`enforcement: "none"` in the graph JSON on exactly this ground — the demotion that
`KM-ADM-001` was authored to produce.

**Why it stays dangerous while it sits there.** The next person to ask "is AC→Test
enforced?" finds a script named `check_ac_coverage.py` and reasonably assumes yes. Either
register it or delete it; leaving it is the trap.

**Workaround.** Use the reverse edge `test-covers` (`# covers: <AC-ID>` in test files),
which **is** enforced by `check-done-proof` — subject to KI-KM-002's diff scope.

---

### KI-KM-005 — Six reviewed `KM-ADM-*` ACs sit as orphan L2s with no L0/L1 parent

- **Severity:** medium
- **Status:** resolved on branch `coverage-answers-reconcile`, pending user approval of the
  framing — parent authored as `KM-ADM-100` with L1s `KM-ADM-100a`–`d`. Delete this section
  when that lands on main.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/acceptance-criteria/knowledge-management/KM-ADM-00{1..6}.yaml`

**Symptom.** All six ACs governing the artifact knowledge graph are `level: L2`,
`readiness: reviewed`, and parentless — they sit loose at the top of the component
directory rather than under an L0/L1 benefit statement. They were authored one at a time
by `/quick-fix`, which produces a single L2 per run and does not graft it onto a tree.

**Consequence.** They express no shared benefit, so the body of work they constitute is
not visible as one thing to anyone reading the store top-down. Whether any traversal or
prioritiser actually skips them is **not yet verified** — do not assume it does, and do
not assume it does not.

**Resolution (2026-08-18, product-owner).** `KM-ADM-100` ("rely on the map of how your
project fits together, because it admits what it cannot prove") now parents all six
through four L1s: `100a` trust ratings reflect what runs and state their scope
(`001`, `005`); `100b` a missing connection is visible as a gap (`002`, `003`);
`100c` the links that tell you what a change breaks are followable (`004`); `100d` every
copy of the map agrees (`006`). The six stay in `knowledge-management` — they are one
artifact-map body, and their relationship to `ACS-1100` is inheritance of a standing
contract, not ownership.

**Residual, and the reason this is only half-fixed.** The links are carried by the
`parent` field, `depends_on`, and `covered_by` — **not** by ID derivation. Compound-prefix
ids (`KM-ADM-005`, and `KM-ADM-100a` itself) both derive to `KM-ADM`, which is not an AC,
so `check-ac-parent-covered-by` never fires on them and `check-ac-tree-limits` counts the
new L0 as childless. The back-links are a convention nothing mechanically defends. The
same is already true of the shipped `KM-KGS-100` tree, so this is a store-wide gap in
`derive_parent_id()` for compound prefixes, not a KM-ADM authoring error. Re-IDing is not
an option — ids never change, and `KM-ADM-005` is cited by `# covers:` tags in shipped
tests.

**Related.** This is the structural half of the same problem as KI-KM-002: a shipped
`/quick-fix` AC has no home in the tree that governs its subject.

---

### KI-KM-006 — The artifact graph is a hand-authored type-level schema; no AC covers making it dynamic

- **Severity:** low
- **Status:** open — no AC authored
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json`; consumed by
  `leafcutter-web/lib/data/flows.ts`

**Symptom.** The graph describes artifact **types** and the relations between them. It
cannot answer an instance question — "show me this AC, its tests, its dependencies, and
what it changed" — because it holds no instance data and no generator produces it. Every
edit is by hand.

**Evidence.** No script under `scripts/` references the graph JSON; its only consumers
are `flows.ts`, `types.ts`, and one test.

**Prerequisite, not just effort.** A dynamic instance graph must carry each rendered
edge's trust rating from the type-level map, or it silently re-introduces the false
confidence that `KM-ADM-001` and `KM-ADM-005` were built to remove. The type map becomes
the schema the dynamic layer reads from — design it that way from the start.

**Precedent that this is buildable.** `UXP-421a` (done) already colours each Atlas flow
step live from the acceptance-criteria store, so live per-request store reads are proven
in this app.

---

### KI-KM-007 — Compound-prefix AC ids are invisible to the store's own parent/child tooling

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/ac_parent_id.py` (`derive_parent_id`), and its callers in
  `scripts/ac_store/scan_ac_store.py`
- **True home:** this is an `ac-store` defect. Recorded here because it was found here and
  it is what makes the `KM-ADM` tree's parent links non-enforcing. Move it when an
  `ac-store` known-issues file exists.

**Symptom.** `derive_parent_id` splits on the last hyphen-delimited segment, which assumes a
single-token prefix. For a compound prefix it strips the wrong segment:

```
derive_parent_id("KM-ADM-005")   -> "KM-ADM"    (expected "KM-ADM-100"-family root)
derive_parent_id("KM-ADM-100a")  -> "KM-ADM"    (expected "KM-ADM-100")
derive_parent_id("ACS-1100a")    -> "ACS-1100"  (correct — single-token prefix)
```

`"KM-ADM"` is not an AC id, so the lookup misses and the check treats the record as having
no parent to validate.

**Consequence.** For every compound-prefix family, `check-ac-parent-covered-by` never fires,
`check-ac-tree-limits` reads a populated parent as childless, and orphan scans report a
clean result over a set they cannot see. The hooks are silent, and their silence reads as a
pass. This is the AC-store analogue of KI-KM-004: tooling that looks live and is not.

**Verified by execution**, not by reading — the three calls above were run against
`scripts/ac_store/ac_parent_id.py` in this worktree on 2026-08-18.

**Blast radius beyond `KM-ADM`.** `KM-KGS` and `KM-VIS` use the same shape; `KM-KGS-100` has
carried the flaw since June. Any future `XX-YYY-NNN` family inherits it silently.

**Do NOT "fix" this by re-IDing.** AC ids never change — `KM-ADM-005` is cited by shipped
`# covers:` tags in the test suite, so renaming it breaks done-proof. The fix is in
`derive_parent_id`: support compound prefixes, or read an explicit `parent` field as a
fallback when derivation misses.

**Bearing on the 2026-08-18 reconciliation.** `KM-ADM-100` and its four L1s were authored
with correct `covered_by`/`parent` links. Those links are **documentation-grade**: a human
or an agent reading the store sees the tree, but no hook enforces it until this is fixed.

---

### KI-KM-008 — 241 ACs are marked `todo` while a covering test already exists, so the store also lies in the direction that hides finished work

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 (measured) · **Last seen:** 2026-08-25
- **Where:** the AC store as a whole; the `work_status` field against `# covers:` tags in
  `unit_tests/` and `tests/`

**Symptom.** 241 AC records carry `work_status: todo` while at least one test in the suite
already carries their id in a `# covers:` tag. `KI-KM-002` measures the store lying one
way — done with nothing proving it. This is the mirror image: work that has a test, and a
record that still says it has not been started.

**Why it is not merely cosmetic.** Three consumers read `work_status` and each is misled
differently. `ac_prioritizer.py` picks the next unimplemented AC, so it will keep offering
work that is finished. `depends_on` edges resolve against it, so a downstream AC reads its
dependency as unmet and blocks or re-does it — `BO-2900g-4` sat behind `BO-2900g-3` in
exactly this way for six days. And every "how much is left" figure derived from the store
is inflated by up to 241 records, which makes the roadmap's own progress reporting
unreliable in the optimistic-effort direction.

**Root cause — the same diff-scoping as KI-KM-002, plus a workflow gap.** Nothing
re-examines a record after the commit that touched it. The dominant producer is the
direct-commit drive: `CLAUDE.md` → "AC-store reconciliation when pivoting to a
direct-commit drive" prescribes reconciling `work_status`, `implemented_by` and
`covered_by` before opening the PR, and that step is manual, easy to skip, and has no
gate. `BO-2900g-3` is a worked example — shipped in `ac564814` (PR #505) on 2026-08-19,
still `todo` with empty `implemented_by` and `covered_by` on 2026-08-25.

**Evidence.** Measured 2026-08-25 at `d37687ff` by joining every `# covers:` tag in
`unit_tests/**/*.py` and `tests/**/*.py` against `work_status: todo` records:

| level / readiness | count |
|---|---|
| L2 reviewed | 75 |
| L2 approved | 72 |
| L3 approved | 43 |
| L3 reviewed | 33 |
| L3 draft | 6 |
| L2 draft | 6 |
| L1 reviewed / draft / approved | 4 / 1 / 1 |
| **total** | **241** |

**The count is an upper bound on the lie, not a to-do list — do not bulk-flip it.** A
`# covers:` tag proves a test *names* the AC. It does not prove the test passes, and it
does not prove the test covers what the criteria actually ask for; a tag can be authored
red at the start of a TDD cycle that was then abandoned, and a passing test can cover one
clause of a five-clause AC. Flipping 241 records on the strength of the tag alone would
replace an understatement with an overstatement and manufacture the phantom-done this
repo exists to prevent — and, per the finalize step-3.5 incident, a bulk `work_status`
sweep is the specific operation that has already gone wrong here once. Each record needs
its tests run and its criteria read. `BO-2900g-3` was reconciled individually on
2026-08-25 on exactly that basis: six tests green under `AC_ENFORCE_STRICT=1`, plus both
load-bearing claims re-checked against the files on disk.

**Fix direction.** The measurement is the cheap part and should be automated first: a
store-wide report of `todo`-with-passing-covering-test, run on a schedule rather than in
the per-PR gate, so the population is visible and its trend is known. Retirement is then
per-record triage, and it should reuse whatever `TQ-400d` builds for the `KI-KM-002` pile
rather than growing a second parallel process — the two are the same review ("does this
test actually prove this criterion?") reached from opposite starting states. A ratchet
like `KM-ADM-005`'s would hold the floor in the meantime.

**Related.** `KI-KM-002` (the inverse population, 244 of 607, with an owner in `TQ-400d`).
`KI-ACS-004` (an AC marked done with no link to implementing code — the `implemented_by`
half of the same reconciliation gap). `KI-ACS-008` (the oracle's tag-to-test layer cannot
see async or parametrised tests, so any automated measurement here inherits that
undercount).
