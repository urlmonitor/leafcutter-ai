# BA learnings — the LAYOUT-SET and STARTABILITY axes (BP-900, 2026-08-25)

Captured by business-analyst while turning KI-BP-003 and KI-BP-006 into ACs.
Component: build-pipeline (folder `build_pipeline/` underscore, `component:` field
hyphenated — `build-pipeline` is the id in `docs/acceptance-criteria/index.yaml`).
§9 route-learning / capture-learning are still not installed (KI-BP-007 records why),
so persisted directly per the existing `feedback_ba_*.md` convention.

## The first thing to do with a KI in this component is check it is not already an AC

Both blockers I was asked to specify were ALREADY specified, and I nearly authored
duplicates:

- KI-BP-006 (deployed script cannot import its helper) → **BP-900g-8**, whose criteria
  name the exact module still missing a week later. Approved, `work_status: todo`.
- KI-BP-003 (declaring file unreachable) → **BP-900g-8-ii** (build refuses to ship) +
  **BP-900h-4** (empirical arrival) + **BP-900h-5** (guardrail reports unable-to-run).
  All approved, all `work_status: todo`.

So the correct finding was: these are **unimplemented specifications, not unspecified
defects**. Say that out loud in the sign-off — it changes the remedy from "author an AC"
to "build the AC that exists". Then author only the dimension the existing set cannot
express. Two existed here and both generalise:

1. **LAYOUT SET.** Every fixture in BP-900h builds exactly ONE install layout, and
   BP-900h-1's criteria pin the package directory to one name. Any AC of the form
   "prove it works in a consumer install" is silently an AC about one layout. Vary the
   package-directory name and main-checkout-vs-git-worktree INDEPENDENTLY — those two
   variables are what made two field reports of KI-BP-003 contradict each other while
   both were accurate. (Authored as BP-900h-4-i.)
2. **STARTABILITY ≠ PRESENCE.** BP-900h-4 asserts declaring files are PRESENT; the
   2026-08-25 instance had the file present and the executable unable to start. And
   BP-900h-5, the only AC in the family that invokes anything, derives its set from the
   **guardrail registry** — so a deployed command an adopter runs from the shell, and a
   helper another deployed script imports, are both invisible to it. Derive from the
   deployed tree, not from a registry. (Authored as BP-900h-5-ii.)

## Tree placement: the "obviously correct" L1 was the wrong L1

I was pointed at BP-900g (build-time, `child_limit_override: 10`, full) and asked to
choose between raising the override again or using L3s. The real answer was neither:
the behaviours were **empirical install-side proofs**, so the correct parent branch was
**BP-900h** ("verifies it empirically, by performing the install"), not BP-900g. BP-900h
is at the 5-L2 cap too, so both went as **L3 under the L2 whose rule they extend** —
h-4 (which already owns the resolution rule and the fixture) and h-5 (which already owns
the invoke-it mechanism and the three-way outcome). No cap change, no debt compounded.

Generalisable check before accepting a proposed parent: does the new behaviour assert
something the BUILD does, or something an INSTALL is? BP-900a..g is the former, BP-900h
is the latter. The KI's "fix direction" paragraph usually points at the build, which is
what makes BP-900g look obviously right when it is not.

## Reusable clause set for anything in this branch

Four clauses that were needed in both ACs and that a weaker draft omits:
- resolved **only** from the deployed output root (h-4's rule — inherit, don't restate);
- a **genuinely cold process** with the package source tree off `sys.path` (the source
  tree contains every sibling by construction — this is why 5 occurrences stayed green);
- **derived, demonstrated by an artifact created after the guard exists** (the only
  construction a hand-maintained list cannot pass);
- **accounting / non-vacuity**: started + not-exercised == size of derived set, every
  exclusion carrying a reason. A for-each over an almost-empty derived set is the most
  likely way these ship broken.

## Operational

- `Edit` was disabled again this session (second time in this folder). The parent
  `covered_by` update was done with
  `python scripts/ac_store/fix_ac_orphans.py --ac-root <feature-folder>` — `--dry-run`
  first; diff was exactly one line per parent. Do NOT hand-retype 180-line parents.
- `check_ac_parent_covered_by.py` **fails open** in this worktree —
  "cannot import derive_parent_id: ac_parent_id.py not found" — which is itself an
  instance of the KI-BP-006 class. Its exit 0 is not a pass. Use
  `scan_ac_orphans.py --ac-root <folder>` instead, which reports a real count.
- `validate_ac_schema.py` now walks a directory recursively and the folder is clean
  (61/61). The seven legacy list-form `it_requirements` records recorded in
  `feedback_ba_bp900_declaring_file_axis.md` have since been fixed — that note is stale.
- `it_requirements` object form is held to ALL FIVE keys (`config_schema_fragment`,
  `reference_file_path`, `n_location_rule`, `required_skills`, `post_write_commands`)
  regardless of `package_surface`; `reference_file_path` must resolve. `constraints` and
  `notes` are permitted extras. Top-level `additionalProperties` is **false**.
- `test_spec` angles are capped at four per AC and come from a closed enum
  (criterion, reachability, seam, real_artifact, deployed, boundary, failure).
