# BA learnings — the DECLARING-FILE deployment axis (BP-900, 2026-08-18)

Captured by business-analyst during L2/L3 decomposition of the "guardrail data and
config dependencies reach the consumer, and a missing declaring file fails loudly"
request. Component: build-pipeline (folder `build_pipeline/` underscore, `component:`
field hyphenated per PROJECT_CONTEXT). §9 route-learning / capture-learning skills are
NOT installed in this repo, so persisted directly as a memory file per the existing
`feedback_ba_*.md` convention.

## A FIFTH deployment-gap axis: NON-CODE declaring files

The four documented axes (see `feedback_ba_bp1000_source_template_parity.md` and
`feedback_itpo_bp900f_tracked_source_axis.md`) are ALL phrased in terms of scripts:

- BP-1000 (a–d): byte-equality of scripts present in BOTH `scripts/` and `templates/`.
- BP-900b: build preflight — template SCRIPT references vs the deployable manifest.
- BP-900e: a registered/referenced SCRIPT has a deploy-source copy at all.
- BP-900f: a deployable SCRIPT's source is tracked in git.
- **NEW — BP-900g-8-ii + BP-900h-4:** the DATA and CONFIGURATION files a deployed
  guardrail reads (schemas, type vocabularies, registries, mapping tables).

All four incumbents were green on 2026-08-18 while five declaring files were absent
from a deployed output root. Cite this list when authoring near any of them; the
vocabulary gap, not the five files, is the defect.

## The self-hosted layout is why nothing detected it (reusable framing)

Every build test installs into leafcutter's own workspace, where the package source
tree sits beside the deployed output root, so a declaring file resolves via an
ancestor directory even when the build never deployed it. Any AC about deployment
completeness needs an explicit resolution clause ("resolved ONLY from the deployed
output root — not from the package checkout, not from a parent directory, not from
the working directory"), or a mere existence check passes for the wrong reason.
BP-900h-1 already forbids building from a copy of the repo; that is necessary and
NOT sufficient, because the leafcutter workspace is not a copy of the repo — the repo
is nested inside it.

## Three DISTINCT shapes of "missing declaring file" degradation — do not merge

BP-900g-10 (parent) forbids only the FIRST. The other two escape its wording and were
authored as siblings under it:

1. **Neutral default** — empty mapping / empty list / passthrough. Parent's clause.
   Harm: indistinguishable from a correct result.
2. **Substitute rule** (BP-900g-10-i) — fall back to a different, built-in rule.
   Harm is the OPPOSITE of neutral: loud, specific, confident, and wrong. The live
   case rejected 920 of 973 records against an id pattern that never applied.
3. **Default-deny** (BP-900g-10-ii) — an absent record coerced to a boolean is false,
   and false is a verdict. Harm: reports a permission denial the reader must go and
   disprove in a file that is correct.

Shapes 2 and 3 are *worse* than 1 precisely because they command attention and aim it
somewhere false. When decomposing any fail-open/fail-closed request, enumerate these
three explicitly — an AC that says "must not degrade" without naming shape 2 and 3
will be satisfied by a fix that only removes the neutral default.

Related: a CWD-relative read of a declaring file (BP-900g-10-iii) is the same class one
layer down — deploying the file makes the symptom vanish while the read stays
conditional on where the process started. Keep it EXPLICITLY out of scope of
ACS-300g-6 (CWD-anchored repo-root resolution), which is a separate defect.

## Structural: BP-900 tree is full — L3 under a class-rule L2 is the release valve

BP-900 (L0) is at `child_limit_override: 8` with 8 L1s; BP-900g is at
`child_limit_override: 10` with 10 L2s; BP-900e is at the 5-L2 cap. Free L2 slots on
2026-08-18: BP-900a(2), b(2), c(2), d(5), f(2), h(2).

The BA cannot author an L1, so new behaviour in a capped branch goes as **L3 under the
L2 that already states the class rule** (here: three L3s under BP-900g-10, two under
BP-900g-8). L3s have no cap. This is legitimate when the new behaviour genuinely is an
edge case of the parent's rule — verify that before using it, or the branch becomes a
dumping ground and the real answer (a PO-owned tree split) keeps being deferred.

## Agent assignment held from prior runs

`.js` workflow body + Python glue = **python-coder** (confirmed in
`feedback_itpo_agent_assignment_by_surface.md`; `workflow-architect` is
`is_ticket_phase: false` and NOT dispatchable). So the workflow-surface fail-loud case
did NOT need splitting out from the script-surface one — one AC per shape, not one per
file. Rule-text corrections in CLAUDE.md ARE a separate surface and DID need a split
(BP-900g-8-iii → documentation-expert), because two agents on one criterion is not
permitted.

## Operational: the Edit tool can be disabled in a BA session

This run `Edit` was unavailable ("Edit is disabled for this session"). The mandatory
parent `covered_by` update was done two ways:
- Short parent (BP-900h): `Read` then `Write` the full file, preserving every field and
  recording a structured `amended_by` entry.
- Long parents (BP-900g-8 at ~250 lines, BP-900g-10 at ~270): do NOT hand-retype these.
  Run `python scripts/ac_store/fix_ac_orphans.py --ac-root <feature-folder>` — it takes
  an `--ac-root`, so it scopes to one folder, has a `--dry-run`, and its diff is
  surgical (only the `covered_by` line changes). Verified: 4 files, 10 insertions.
  It also repaired a pre-existing stale link (BP-900c-1 → BP-900c-1-1).

Verification pair worth reusing after any authoring run in this folder:
`scan_ac_orphans.py --ac-root <folder>` then `validate_ac_schema.py <explicit file
paths>`. Note `validate_ac_schema.py` does NOT glob a directory (prints "No YAML files
to validate" and exits 0), and a `find ... -name A -o -name B -exec` binds `-exec` to
the LAST `-o` branch only — that combination silently validates a subset and reports OK.

## Pre-existing store defect found in passing (not fixed — out of BA scope)

Seven records in `BP-900-deployment-completeness/` fail `validate_ac_schema.py` with
`it_requirements ... is not of type 'object'` — they carry the legacy list form:
BP-900a-1, a-1-1, a-2, a-3, c-1-1, c-3-i, d. Pre-existing, unrelated to this run,
would block a commit that stages them. IT-PO or a store-hygiene pass should convert
them to the object form.
