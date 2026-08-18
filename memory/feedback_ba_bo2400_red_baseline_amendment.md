# BA learnings — BO-2400a-3 red-baseline amendment (2026-08-17)

## The schema forces the BA to author it-po-shaped `it_requirements`

`config/ac_store_schema.json` has a conditional at the bottom: when an AC has
`assigned_agent: python-coder` AND `component` in {`build_pipeline`,
`build-orchestration`}, `it_requirements` becomes **required** and must be a
structured **object** with all five keys (`config_schema_fragment`,
`reference_file_path`, `n_location_rule`, `required_skills`,
`post_write_commands`). A list-of-strings `it_requirements` fails validation
for those ACs, and omitting the field entirely fails too.

Consequence for the BA in these two components: you cannot hand off a
python-coder AC with `it_requirements` unset "for it-po to fill in" — the file
will not validate and will not commit. Author a minimal, honest object (the
sibling ACs BO-2400a-2 / BO-2400a-4 are the shape template) and mark inside
`constraints` which entries it-po must deepen. `assigned_agent: llm-expert`
sidesteps the conditional entirely, as does omitting `assigned_agent` (see
BO-2400f-9), but neither is the right dodge when the surface really is Python.

Also note `validate_ac_schema.py` takes **file paths, not a directory** — a
directory argument silently prints "No YAML files to validate" and exits 0.
Always pass a glob and check the file count in the OK line.

## Amend vs supersede: the test that decided BO-2400a-3-i

BO-2400a-3-i (`work_status: done`) mandated the exact behaviour being removed
("a green-at-baseline test is a hard halt, never a warning that proceeds").
Rule of thumb used, and worth reusing:

- **Supersede** when the criterion's *outcome contract* is retired. `status`
  becomes `superseded_by`, which excludes the record from
  `check_ac_coverage` enforcement — so only supersede when you genuinely want
  the behaviour to stop being enforced.
- **Amend** when only the *trigger condition* changes and the outcome contract
  survives. Keep `status: active`, rewrite `criteria`, quote the withdrawn
  wording verbatim in the `amended_by` reason so nothing is deleted from the
  record's history, and reset `work_status` to reflect that the shipped code
  now enforces the pre-amendment rule.

BO-2400a-3-i was amended: the halt itself (hard halt before coder dispatch,
structured blocker, report naming test + AC id) is unchanged and must stay
enforced; only "which condition fires the halt" moved.

`amended_by` item shape in this store is `- reason: "<text>"` (object with a
`reason` key), per BO-1700a-3-ii / BO-1700h-3.

## Decomposition pattern: separate the fidelity gap from the intent change

When an implementation diverges from its AC *and* the AC itself is wrong, these
are two defects and must land in different ACs, or reviewers cannot tell which
change needed the user's authorisation:

- fidelity gap (code ≠ existing AC) → new ACs describing the correct
  derivation; the parent AC's wording does not change.
- specification gap (AC ≠ desired behaviour) → an `amended_by` entry on the
  existing AC plus a new AC carrying the new rule.

## Child-count caps do not apply below L1

`check_ac_limits.py` caps children only on L0 (7 L1s) and L1 (5 L2s). An L2 can
carry any number of L3s (only a "<3 children" advisory exists). When an L1 is
already at its `child_limit_override` ceiling — BO-2400a is at 8/9 — decompose
downward into L3s under the relevant L2 rather than burning the last L2 slot.
