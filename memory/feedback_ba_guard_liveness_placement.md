# BA — guard-liveness authoring (2026-09-01): placement facts and re-derivations

Captured while authoring L2/L3 for the "a guard that never refuses anything" bleed
(GE-126b-5, GE-126b-5-i, GE-126c-5, GE-126c-5-i, BP-100n-5, BP-100n-5-i).

## Placement — both false-green goals are now structurally full at L1

Measured with `derive_parent_id()` over the whole store, 2026-09-01, AFTER this run's
three additions:

| parent | level | override | L1 kids | L2 kids | cap |
|---|---|---|---|---|---|
| GE-120 | L0 | – | 5 | – | 7 |
| GE-120a/b/d/e | L1 | – | – | 5 each | 5 |
| GE-120c | L1 | **6** | – | 6 | 5→6 |
| GE-126 | L0 | – | 5 | – | 7 |
| GE-126a…e | L1 | – | – | **5 each** | 5 |
| BP-100n | L1 | – | – | **5** | 5 |
| BP-100k | L1 | – | – | 5 | 5 |

Consequences for the next author:

- **Every L1 under GE-120 and GE-126 is now at the cap.** Any further L2 in this
  family needs a new L1. Both L0s hold 5 L1s against a cap of 7, so two free L1 slots
  each — that is where the room is.
- **BP-100k's `child_limit_override` was DISCHARGED** in the BP-100k → BP-100n split
  (2026-08-26). It sits at 5/5 with no override. Do not read its history as headroom.
- **GE-120c carries a live `child_limit_override: 6`** and is already at 6.

## GE-120's folder is NO LONGER frozen — the widely-repeated note is stale

`unit_tests/commit_guardian/test_ge_122e_1.py` was **amended 2026-08-18** from
`git diff origin/main -- <folder>` must be EMPTY to an **id-stability** set-difference.
Its own docstring says adding a record is "ordinary growth ... and must not fail."
GE-126's L0 notes (written 2026-08-26) still cite the freeze as a reason GE-120 cannot
be extended — that reason expired eight days before the note was written. Read the
guard test, not the note that describes it.

## Re-derivations worth not repeating

- **`config/verification_flow.schema.json` has zero code readers.** Seven files mention
  it repo-wide: the schema, one instance document, two AC records, two changelogs,
  `docs/testing/test-angles.md`. It already models `negative_control`,
  `not_applicable + reason`, and the four-value `currently.state`
  (passing/failing/blocked/unverified). **Reuse this vocabulary; never mint a second one.**
- **`scripts/commit_guardian` is a symlink** to `../.leafcutter/scripts/commit_guardian`;
  `templates/scripts/commit_guardian` is canonical. A mutation proof applied to the
  template does not land, and fails **green**.
- **`readme_read_guard` is inert by two different mechanisms.** In the main workspace,
  `.resolve()` escapes the repo root and `relative_to` raises. **In a worktree it does
  not raise** — `.leafcutter` is inside the root, so the resolved path simply fails the
  prefix test. A fix that only handles the `ValueError` leaves every worktree inert.
  Its fourth prefix, `alembic/versions/`, matches nothing: the repo has no `alembic/`.
- **`config_schema_fragment` has two incompatible shapes in the store** — keys that are
  config part names, and keys that are JSON-Schema vocabulary (`type`/`properties`/
  `required`). Any check reading the field must distinguish them or it misreports both.
- The declaration-versus-reality gap is **not** in
  `check_package_surface_declaration.py` (that file contains no occurrence of
  `config_schema_fragment`). Shape validation lives in `scripts/ac_store/validate_ac.py`
  and `config/ac_store_schema.json`.

## GE-120f decomposition (2026-09-01, second BA pass) — what the remainder actually was

GE-120f took one of GE-120's two free L1 slots and is now at **5/5 L2** with no override.
The family has **zero L2 headroom left anywhere**; the remaining room is one free L1 slot
under GE-120 and two under GE-126.

The split that survived cross-referencing the six in-flight siblings:

| id | behaviour | why it is not a sibling's |
|---|---|---|
| GE-120f-1 | the observation is PRODUCED by putting the declared input through the entry point | GE-126b-5 defines the datum and the four values but is silent on where the value comes from — a declaration read back as its own answer satisfies every clause it states |
| GE-120f-2 | consequence: named + the run fails; never-asked never counts as protection | GE-126b-5 gives visibility; visibility is not consequence |
| GE-120f-3 | stated examined figure MOVES when the POPULATION moves | GE-126b-5's figures move when a RECORD changes value — population held fixed. A hardcoded total satisfies its summing clause exactly |
| GE-120f-4 | declaration is a condition of REGISTRATION | nobody owned "the next check inherits by existing" |
| GE-120f-5 | reference-doc (parent's own trigger) | documentation-expert; cannot be folded into a coder AC |

Two reusable findings:

- **A registration-time AC is the one place "a declaration exists" is a legitimate subject** —
  and it is only safe with an explicit clause saying passing the gate places the check among
  the *not yet demonstrated*, never among the protected. Without that clause the anti-grep AC
  becomes the defect.
- **The strongest L3s are the ones whose named mutation turns ONLY the child red.** Three of
  the four here are built that way (advisory-instead-of-outcome; inside-call instead of entry
  point; group-exemption by registration date). If a candidate L3's mutation also reddens the
  parent, it is a parent clause, not a record.
- **`refuses everything` is the regime's off switch** and no sibling owned it. Any "prove it
  can refuse" rule needs a paired acceptable input or it is discharged by widening the guard.

## Decomposition strategy that worked

BP-100n-4 is the house style to copy for anti-grep criteria: state the measured
populations in the `Given`, and close with a **varying-population** clause ("add one, the
stated count must be one greater"). That single clause is the only form no
literal-carrying implementation can satisfy — a stated count alone is satisfiable by a
hardcoded number. Put the named mutation for every absence-asserting clause in `notes`,
and put a clause whose mutation turns *only that clause* red into its own `-i` record;
that asymmetry is what stops an implementer satisfying the parent while collapsing two
distinct failures into one message.
