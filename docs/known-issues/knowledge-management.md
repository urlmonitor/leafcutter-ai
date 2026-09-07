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

---

### KI-KM-009 — ADR-034 says the knowledge loop "has never closed"; nine files on disk say otherwise, and work was specified against the wrong premise

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `docs/architecture/adrs/ADR-034-knowledge-write-ownership.md` §1 (closing
  sentence) and §2 item 2

**Symptom.** ADR-034 §1 ends "So the loop has never closed, in any direction, in any
install." §2 then demotes inline agent-side capture (its Option A) from *deferred* to
**rejected**, and that demotion rests on the §1 finding.

The sentence is false. Resolving all 10 distinct `destination` paths named by the 28
`knowledge_captured` events in `debugging/logs/agent_telemetry.jsonl` finds **9 of 10
present in the repo**, sized 3608–23474 bytes and full of substantive content. The
busiest, `memory/feedback_itpo_agent_assignment_by_surface.md` (23 KB, the target of 10
events), opens "Captured 2026-06-16 during BO-210 / GE-102 technical enrichment" —
matching the timestamp, `agent` and `destination` of the first event exactly. `git log`
shows them committed during normal work in June 2026.

So the loop *did* close, informally: agents wrote the learning themselves and then emitted
a receipt. Inline capture is not merely an unrejected alternative — it is the **only**
mechanism that has ever produced knowledge in this repository. The harvester has never
written a single line.

**Why it matters beyond the wording.** Two ACs were specified on the strength of the false
premise, both proposing to *recover* the 28 events into knowledge surfaces. Because the
event schema carries no learning body (see `KI-KM-010`), executing either would have
appended 28 placeholder strings of the form `[agent-assignment-pattern] Learning from ` on
top of nine curated files that already hold the real content. Both are now withdrawn —
`INF-400c-5-ii` (`superseded_by: [INF-700c]`) and `INF-400c-4-ii`
(`superseded_by: [INF-700c-2]`) — but they reached `reviewed` readiness first.

**The honest reading is narrower than "Option A wins."** Inline capture is the only
mechanism that has produced anything, but partly because the harvester was never wired,
not because deferred harvest cannot work. What the evidence does establish is that the
write must hang off something that actually runs, and today the agent's own run is the
only such thing.

**Fix direction.** Correct §1's closing sentence and re-examine §2 item 2 against the
corrected premise. ADR-034 §6 already contains the trigger: review criterion 1, "a caller
for the harvester proves impractical, making deferred capture unreachable in practice
rather than merely unwired." Two months with one emission is evidence for that criterion.
Do not delete the ADR's history — amend with a dated correction, because the withdrawn ACs
cite it. The ADR carries `deciders: BrainCandy`; the §1 retraction is the author's to make,
not an agent's.

**Trap.** The 28 events look like a stranded backlog and invite a recovery ticket. Resolve
the `destination` paths **before** specifying any recovery: the interesting question is not
"can we route these?" but "is there anything in them to route, and is it already
somewhere?" Here the answer was no and yes respectively.

**Related.** `KI-KM-010` (the receipt-shaped schema). `KI-BP-007` (the dead
`route-learning` / `capture-learning` references that made the fail-open path the only
reachable one). `INF-700b`, `INF-700c` (the replacement features).

---

### KI-KM-010 — The emission event is a receipt with no payload, and `_event_hash` keys on a field that is empty in every real record

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/skills/signoff/SKILL.md` §7 step 4 (the emitter contract);
  `scripts/knowledge/harvest_learnings.py` `_event_hash` and the `learning_text` fallback

**Symptom.** All 28 `knowledge_captured` events on disk share exactly one key set:
`event, timestamp, agent, component, destination, entry_kind`. There is **no `text`
field, and there never was one** — §7 step 4 specifies precisely these fields. The event
records that a write happened; it does not carry what was written.

The harvester was nonetheless built to route these events into knowledge surfaces, falling
back to `f"[{entry_kind}] Learning from {ticket}"` when `text` is absent. `ticket` is also
absent from all 28, so the fallback yields a trailing-space placeholder naming nothing.
`INF-400c-2`'s own Gherkin specifies three example events each carrying a *learning text* —
a shape that has never existed on disk. **The harvester was specified against an event
schema no emitter has ever produced.**

The durable anchor for the fallback is the string
`learning_text = event.get("text", f"[{entry_kind}] Learning from {ticket}")` — cite that
rather than a line number, which has already moved once.

**The second half: a hash keyed on nothing.** `_event_hash` builds its digest from
`(ticket, timestamp, destination, entry_kind)`. Since `ticket` is empty in every real
record, one of the four key components contributes a constant. Idempotency currently holds
only because the remaining three happen to differ — but **17 of the 28** timestamps are
day-resolution, so two learnings routed to the same destination with the same kind on the
same day would collide and the second would be silently treated as already processed.
Verified: the 28 records yield 28 distinct `(timestamp, destination, entry_kind)` triples,
so the corpus alone cannot demonstrate the bug — the collision must be constructed.

**A pre-existing contract violation nobody had noticed.** §7 step 4 documents an event
keyed on `ticket`; the three v3 agent templates (`product-owner.md:473`,
`business-analyst.md:911`, `it-po.md:812`) document `agent` + `component` instead. Every
one of the 28 on-disk records uses the v3 shape. `INF-400b-2` requires v3 emissions to be
"structurally identical" to §7 step 4's — that clause is **already violated in the shipped
artefacts**, and has been since both were written.

**Fix direction.** Three separable changes, and they must not be conflated:
1. Add a `text` field to the emission contract, additively — required of producers,
   optional to consumers, so the 28 six-field records stay structurally valid and simply
   classify as ineligible-to-write. All four emission surfaces (§7 step 4 plus the three
   v3 templates) change in one commit or the parity clause breaks further.
2. Reconcile §7 step 4 against the v3 templates so `ticket` versus `agent`+`component` is
   settled one way. This is `INF-400b-2`'s to own; it needs amending either way, because
   its enumerated field list goes stale the moment `text` ships.
3. Re-key `_event_hash` on fields that are actually populated, and add a collision test
   using two same-day same-destination same-kind records. Guard the over-correction too:
   hashing the whole record restores discrimination and destroys idempotency.

**Trap.** The hash defect is invisible today — no collisions exist among the 28 (verified).
It becomes reachable the moment emissions resume at any volume, which is exactly when the
loop is repaired. Fix it *with* the repair, not after.

**Related.** `KI-KM-009` (the false premise this schema misled). `INF-400b-2-i` and
`INF-400b-2-ii` (the owning ACs, authored 2026-08-26). `INF-700b-1` (requires the record to
carry the learning text).

---

### KI-KM-011 — A valid-JSON non-object line crashes the harvester with an unhandled `AttributeError`, and the sink already contains junk lines the repo's own checklist puts there

- **Severity:** medium
- **Status:** **PARTIALLY RESOLVED 2026-08-31.** The crash is fixed — `INF-700c-1-i`
  (PR #650) added the `isinstance(event, dict)` guard and 1-based malformed-line
  reporting, so a bare JSON scalar is now counted as malformed instead of killing the
  run, and a reader can tell a whole-file read from a truncated one. Verified: 53 tests
  green, including a case built from the real 33-line sink.
  **The other half is still open, and is why this entry is narrowed rather than deleted:**
  `CLAUDE.md`'s Pre-Drive Checklist still prescribes
  `echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl`, so the
  documented check keeps writing non-event lines into the stream the harvester reads.
  The harvester now tolerates them; nothing has stopped producing them. Remaining fix:
  change the probe to a non-appending writability check (`test -w`) or point it at a
  scratch path.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/knowledge/harvest_learnings.py` — the per-line loop, at
  `event.get("event")`; `CLAUDE.md` → Pre-Drive Checklist → "Feedback sink reachable"

**Symptom.** The harvester catches `json.JSONDecodeError` and continues, so a malformed
line is survivable. A line that is **valid JSON but not an object** — `"done"`, `42`,
`[]` — passes `json.loads` and then raises `AttributeError: 'str' object has no attribute
'get'`, which is outside the caught type. The run dies with an unhandled traceback and
exit `1`, a code documented as "sink file not found or unreadable". Every well-formed
record after the offending line is never processed.

Reproduced directly against the production entry point with a two-line sink whose first
line is `"just a string"`: the valid `knowledge_captured` record on line 2 was not routed.

**This is not hypothetical — the sink is already dirty.** `debugging/logs/agent_telemetry.jsonl`
is 33 lines: 28 knowledge records, **4 probe lines**, and 1 malformed line (line 19 is the
bare string `</content>`, a fragment from an agent hand-writing its JSON append — itself
corroboration of `INF-400c-5`'s claim that free-hand appends caused the vocabulary sprawl).

**The repo instructs people to write the probe lines.** `CLAUDE.md`'s Pre-Drive Checklist
prescribes `echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl` as
a writability test. Lines 1, 21, 31 and 33 are that probe. So the documented pre-drive
check is itself a producer of non-event lines in the shared stream the harvester reads —
a small instance of the same shape as `KI-BP-007`: an instruction that quietly creates the
condition another component must tolerate.

**Fix direction.** ~~Widen the guard to `isinstance(event, dict)` before `.get()`, and count
skipped lines with their line numbers rather than dropping them silently~~ — **done in
PR #650**, with no sixth exit code added, as prescribed. **Still outstanding:** change the
checklist's probe to a `test -w` style check that does not append, or point it at a scratch
path. Until that lands the sink keeps accruing probe lines; they are now counted and
reported rather than fatal, which is a smaller problem but not the absence of one.

**Related.** `INF-700c-1-i` (owns the resilience-and-reporting behaviour, with test specs
authored). `INF-400c-4-iii` (owns filtering the harvester's own stream out of the shared
telemetry file). `KI-BP-007` (documented instruction, silent consequence).

---

### KI-KM-20260826-id-convention-diverged-across-registers — two registers adopted different replacement id forms, eleven still teach the one known not to work

> **First entry in this file using the date-and-slug id form,** for the reason the entry
> itself describes. The sequential `KI-KM-NNN` entries above keep their ids.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** ongoing (introduced 2026-08-26)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** the `## How to use this file` → **Adding an issue** block in all thirteen
  `docs/known-issues/*.md` registers

**Background.** `KI-BO-024` established that *"append the next free number"* cannot work
under concurrent authors: it requires every author to read the same file at the same moment
and act before anyone else does. On 2026-08-25 it produced ten collisions in one day, one
of which reached `main`. The prescribed remedy is a date-plus-slug id, which cannot collide.

**Symptom, measured 2026-08-26 against `origin/main`.** Of the thirteen registers, **two**
adopted a replacement id form and they do not agree with each other, and **eleven** still
instruct the author verbatim to do the thing that is known not to work:

```text
**Adding an issue.** Append a new `### KI-XX-NNN` section using the next free number.
```

| register | its "Adding an issue" says |
|---|---|
| `build-pipeline.md` | `KI-BP-YYYYMMDD-short-slug`, with a full "Why not the next free number" rationale |
| `build-orchestration.md` | `KI-BO-YYYYMMDD-HHMM`, using UTC `date -u "+%Y%m%d-%H%M"` |
| the other eleven | "append the next free number" — unchanged |

So a register's declared convention now depends on which register you open, and neither of
the two that changed mentions the other. An author landing in any of the eleven is told to
use the sequential form by a file that does not mention `KI-BO-024` at all.

**Three id forms are live, and none of them is wrong.** Filed within hours of each other:

| form | example | status |
|---|---|---|
| sequential | `KI-SS-004` | historical, all registers |
| date + time | `KI-BP-20260826-1421` | in four registers; the declared form in `build-orchestration.md` |
| date + slug | `KI-BP-20260826-worktree-hooks-only-on-one-path` | the declared form in `build-pipeline.md` |

Both replacements are collision-free, so this is a consistency problem, not a correctness
one. What makes it worth an entry is *how* it happened: the two forms were adopted
independently, hours apart, by sessions that could not see each other's work — which is the
same concurrency `KI-BO-024` exists to survive, reproduced on the fix for `KI-BO-024`.

**Do not renumber to unify them.** Measured, not assumed: the date-and-time ids already
carry **20 inbound references across four registers**. Renumbering breaks every one, and
`build-pipeline.md`'s own note says the sequential ids must not be renumbered for exactly
this reason. Both forms sort and grep identically on the `KI-XX-` prefix, so the cost of
leaving them is cosmetic and the cost of unifying them is broken cross-references. This
register already carries renumbering scar tissue (`KI-BP-020`, and the `KI-CG-012`
collision) from the last attempt.

**Fix direction.**

1. **Pick one of the two replacement forms and propagate it to all thirteen.** Either works;
   the choice matters less than that it is the same everywhere. Date-and-slug carries more
   information at the grep line, date-and-time is shorter and mechanically derivable from
   `date -u` with no naming judgement — that is the whole trade-off.
2. **Say explicitly that no existing id gets renumbered,** in whichever block is propagated.
   Both replacement forms are already load-bearing.
3. **Keep the block in one place.** `docs/known-issues/README.md` exists; hosting the
   convention there once, with the per-register sections pointing at it, removes the failure
   mode directly. Thirteen copies of one convention is how they came to disagree, and
   propagating a fourteenth copy of the *right* text still leaves the next author free to
   edit one of them.

**Related.** `KI-BO-024` (diagnosed the collision and named the remedy). `KI-BP-020` and the
`KI-CG-012` collision in `commit-guardian.md` (the scar tissue from renumbering).

**Pattern:** a convention fixed in the copy the author happened to be editing, in a system
with thirteen copies.
