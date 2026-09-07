# BA — UXP-700 truthful-project-record decomposition (2026-09-07)

Captured while decomposing UXP-700a..e into L2/L3, splitting UXP-514, and repairing
covered_by drift in the ux-prototyping component.

## `declares_side_effect` is DERIVED, not authored — and the derivation is a narrow regex

`check_ac_schema` (via `_ac_schema_validators.derive_declares_side_effect`, BO-2900g-2)
recomputes the field from the AC's own **Then** clause and blocks the commit when an
authored value disagrees. This is not documented in `docs/reference/ac-schema.md`, whose
entry reads as though the field is an ordinary authored boolean. Ten records in this run
were blocked on first staging.

Practical rules for the next author:

- Do **not** stamp `declares_side_effect: true` because the work "obviously writes files".
  The Then clause has to say so in the pattern's vocabulary.
- Matching phrasings that work: `... is written into <destination>`, `a store index is
  written ...`, `a mark is written to disk`, `<durable noun> is/are written`. The durable
  noun set is `file, record, artifact, entry, document, index, manifest, AC, criterion,
  ticket, log`.
- Non-matching phrasings that read identically to a human: "the project **holds** a
  record", "it **writes a store index**" (index is not in the `writes? (a|the|an)
  (file|record)` alternation), "the journey **carries** a durable mark".
- Only the first `Then` onward is searched; a `Because` clause is stripped first.
- Where the Then genuinely does not assert a durable write, **remove** the field rather
  than bending the criteria. Bending prose to satisfy a regex is how the derivation stops
  meaning anything.

## `scan_ac_orphans` requires covered_by on EVERY parent, including L2 → L3

The parent-covered_by protocol is easy to apply only to the L1s. It applies at every
level: an L2 with `-i` / `-ii` children must list them in its own `covered_by` or the
scan reports them as orphans (14 parents in this run). `check_ac_parent_covered_by`
passed while `scan_ac_orphans` failed, because the hook only inspects staged files and
the scan walks the store — run **both**.

## Cap arithmetic must be done BEFORE choosing the L2 set

`ACS-100c-1`: 7 L1s per L0, 5 L2s per L1; the cap keys on the parent's `level` field, so
an L2 has **no** cap on its L3 children. `documentation_triggers` on an L1 consume L2
slots at one AC per trigger (different agents ⇒ cannot be merged). UXP-700c declared
`[how-to, sequence-diagram]`, leaving exactly three behavioural L2 slots against four
named sub-surfaces — the cross-platform behaviour had to become an L3
(`UXP-700c-3-i`). Count `5 − len(documentation_triggers)` first, then decompose.

Also: a re-parented child linked only by `depends_on` + `covered_by` (UXP-300 under
UXP-700e) does **not** derive to its parent, so it consumes no cap slot. UXP-700e reads
as 5 children but counts as 4.

## Universally quantified criteria are the vacuity smell

Every clause of UXP-514 is "errors if **any** X differs". On an empty store all four are
true and the checker prints a clean pass. When decomposing any drift/validation AC in
this repo, look for `any`/`every` in the criteria and author a paired anti-vacuity
sibling — the shape already existed as `UXP-609-2` and is now generalised as
`UXP-700b-3` / `UXP-514-5`.

## The UXP-590 vs UXP-700c axis, and where index-vs-source belongs

The L0 notes draw it sharply: **UXP-590 = the record agreeing with itself**;
**UXP-700c = the record agreeing with the code**. The 14/14 index-summary mismatch reads
like drift and is not — it is the record disagreeing with itself, so it was authored as
`UXP-514-6` under UXP-590, not under UXP-700c. The *growth* that caused the duplication
is UXP-700e's (`UXP-700e-2`). Three ACs, three axes, no overlap. Use this test when a
piece of evidence seems to fit two L1s.

## Numeric-sibling ids defeat the cap silently

`derive_parent_id("UXP-491")` returns `None`. UXP-490 accumulated nine children by
`depends_on` while counting as **zero** against the 3–7 cap. Always use the canonical
child form (`UXP-514-1`, `UXP-700a-1`). The store's own precedent for an L3 under an L2
is `UXP-609-2` under `UXP-609` — the `level` field is positional, so a child of an L2 is
`L3` even when the request calls it "an L2".

## Linking a half-covering test

Two tests genuinely covered one clause each of UXP-511 and UXP-513. They were linked in
`covered_by` **with an explicit `notes` block naming the uncovered clauses** and a
`test_spec` work order for them. Linking a half-covered AC as covered converts a visible
gap into a hidden one — the exact failure UXP-700b exists to prevent. If you link a
partial test, say so in the record or do not link it.

## covered_by is a DIRECT-CHILDREN list — settled 2026-09-07

Previously undefined in `docs/reference/ac-schema.md`; now documented there under
"covered_by — Scope Convention". Decided from tool behaviour, not preference: both
enforcers (`check_ac_parent_covered_by`, `scan_ac_orphans`) do a single-hop
`derive_parent_id` check and never read a grandparent — the hook's own ACS-100i-3
decision entry says grandparents are not required to list grandchildren, with six tests
pinning it; `done_proof._resolve_all_child_ids` recurses through each entry's own
`covered_by`; `approve_acs` treats every entry as a leaf. A grandchild entry is
therefore unverifiable — nothing requires it, nothing reads it, nothing notices if it
goes stale. Before removing one, confirm the descendant's own immediate parent lists it.

Corollary that bit here: when a record's declared parent (`depends_on`) and its
ID-derived parent disagree — which happens throughout the UXP-490 subtree, where
`UXP-400a` declares `UXP-491` but derives to `UXP-400` — keep the entry on the declared
parent. That is the only edge the record actually asserts. Those records are invisible
to both the hook and the scan in both directions; five of them show as permanent
false-positive orphans under `UXP-400/410/412/420/421`.

## Splitting an overcrowded L0 whose children use numeric-sibling ids

`ac-tree-split` Pattern A works fine (reparent by `depends_on` + `covered_by`, no
renames), but be honest about what it does NOT do: `check_ac_limits` counts by
`_derive_parent_id`, so if the children keep the numeric-sibling form the hook counted
zero before the split and counts zero after. The split fixes the store's recorded edges,
not the hook's view. Only renaming to canonical child ids would fix the count, and that
breaks citations in `docs/product-truth/index.json` `by_ac`, flow `implements` arrays,
ADRs and agent cards — not worth it for an advisory count. Say so in the record's
`amended_by` rather than letting the next reader assume the cap is now enforced.

Done on UXP-490 (9 -> 5) with new sibling L0 `UXP-800` taking 493/590/592/594. The split
axis that held up: consumption (look at it, approve it, read a true status) vs production
(the store, what decides what gets written, who drafts it, what keeps links honest).

## declares_side_effect is DERIVED, not authored

`check_ac_schema` computes it from the record's own `Then` clause (`Because` clauses
stripped first, case-sensitively; window runs from the first `Then` to end of text) and
blocks on any disagreement OR on absence when the derivation is true. Writing
`declares_side_effect: false` on a record whose Then says "a record file is written"
blocks the commit. The matcher is narrow and phrase-based — the discriminator is the
OBJECT written, not the verb. `docs/reference/ac-schema.md` documented it as an ordinary
authored boolean until 2026-09-07; the derivation and the qualifying phrase list are now
written up there under "declares_side_effect is derived from the Then clause".

## Harness note

Staging AC files triggered a regeneration of `docs/INDEX.md` that dropped 183 of 229
lines (the whole Components table) and reset its `created` date. Restored with
`git checkout --`. Check `git status` for files outside the AC store after any
`git add` in this repo.
