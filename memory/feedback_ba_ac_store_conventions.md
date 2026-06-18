# BA learnings — AC store conventions (leafcutter)

Captured 2026-06-16 during BO-210 / GE-102 decomposition.

## Canonical L2/L3 field set (live convention, NOT the stale strict schema)

`config/ac_store_schema.json` declares `additionalProperties: false` and only
allows a thin field list. It is STALE. Every live, committed, passing AC file
(e.g. the GE-100 family) uses the richer v3 field set and FAILS the strict
JSON schema. The actual enforcing `check_ac_schema.py` hook falls back to
"manual field validation" (exit 0) when it cannot find the schema relative to
cwd — that manual path is what gates commits in practice.

Author L2/L3 files with this field set (matches GE-100a, the cleanest live
exemplar):
`id, readiness, priority, title, component, level, status, req_status,
work_status, created_by, criteria, depends_on, doc_links (list of
{path, relationship, status}), assigned_agent, estimated_complexity,
it_requirements (L2/L3 only), delivers_to, expects_from, origin_agent,
created, amended_by, superseded_by, covered_by, implemented_by`.

- `created_by` is required by the manual validator and present on all GE-100
  files; set it to the parent/source AC YAML path.
- `readiness: draft` on newly authored L2/L3; `origin_agent: business-analyst`
  on agent-authored, `origin_agent: BrainCandy` on user-authored top-level ACs.
- Older BO-200 files predate `created_by`/`readiness`/`priority` — do not copy
  them as the field-set template; use GE-100 instead.

## Cross-component routing by directory_patterns

When a feature spans components, route each AC to the component whose
`index.yaml` `directory_patterns` match the files it governs:
- `guardrail-engine` (GE): owns `scripts/commit_guardian/check_*.py` and
  `templates/commit-guardian/check_*.py` — i.e. hook scripts, hooks_manifest
  tier fields, AUTOFIX_AGENT emission, transform hooks.
- `build-orchestration` (BO): owns the autofix skill/commit-agent orchestration,
  `.claude/precommit-autofix.json` config, and signoff-skill capsule behavior.

Link cross-component children to the originating feature via `depends_on`
(a GE-102 L1 can `depends_on` a BO-210 L0 across components).

## Parent covered_by must stay same-folder

`check_ac_parent_covered_by.py` and `derive_parent_id()` require the parent
file to live in the same feature folder. Do NOT make an L3 in component A a
child of an L2 in component B — create a same-component parent and use
`depends_on` for the cross-component link instead.

## Hooks_manifest shape (for IT PO / coders)

`commit_guardian.json` -> `hooks_manifest.hooks[]` entries currently have
keys: id, name, entry, language, files, stages, pass_filenames, enabled,
fail_open, types. No `tier` field yet (GE-102c adds it). `doc_frontmatter`
config section already holds required_fields per path glob + allowed_types +
allowed_statuses — the transform_doc_frontmatter hook should read defaults
from there.

## GE component: GE-104 established the first goal-level L0 (2026-06-17, PO)

The guardrail-engine component was a flat set of sibling L1 features (GE-100
jscpd, GE-101 diff-cover, GE-102 transform-tier) with NO goal-level L0. GE-104
("New work never ships without the documentation it needs") is the first L0 in
the component, living in its own slug folder GE-104-enforced-page-docs/ with its
sole L1 child GE-104a ("A new frontend page can never ship undocumented").

Framing note for the BA decomposing GE-104a: the user explicitly described TWO
enforcement layers (a commit-time guardrail that blocks/warns when a commit adds
a new frontend page without its reference doc; and a planning-time trigger that
flips documentation-expert from not_needed -> needed when a new page appears in
ticket scope without a matching doc). The PO deliberately kept these as ONE L1
outcome (enforced, not discretionary). Decompose the two layers as sibling L2
behaviors under GE-104a, not as separate L1s. The deterministic
route->doc->component naming convention is the reliable mapping to check
against. documentation_triggers on GE-104a is [how-to, sequence-diagram].

## BO-1300 independent spot-check: framing note for the BA (2026-06-18, PO)

BO-1300 ("Catch the problems your tests never thought to check before calling a
feature done") is a NEW L0 in build-orchestration, slug folder
BO-1300-independent-spot-check/, five L1 children BO-1300a..e, origin_agent:
BrainCandy (user-authored). It introduces a post-build "spot-check" review pass
that is DISTINCT from TDD / unit tests.

Decomposition guidance the PO baked into the L1 split (do not collapse or
re-cut these at L1 — decompose each into L2 behaviors instead):
- BO-1300a — on-demand surface: a standalone slash command/template the user
  invokes against a finished feature. documentation_triggers [how-to, sequence-diagram].
- BO-1300b — exactly THREE independent reviewer agents running in parallel
  (three perspectives, one pass). Keep "3 parallel" as the load-bearing fact.
- BO-1300c — scope BOUNDARY: reviewers MUST NOT re-run unit tests; they exercise
  the feature for gaps not covered by existing tests/ACs. This is the line that
  separates spot-check agents from test-writer/test-runner. Likely needs an
  explicit negative AC ("does not invoke the unit-test suite").
- BO-1300d — automatic surface: the SAME pass runs as the closing step of
  /build-feature before "done". Two surfaces (a + d) share one underlying pass —
  the BA should factor the shared spot-check pass once and wire both entry points
  to it, not duplicate the logic.
- BO-1300e — found issues become tickets in tickets/00_inbox/ so ticket-supervisor
  picks them up via the normal fix flow. The auto-ticketing contract (one ticket
  per finding, valid frontmatter, inbox placement) lives here.

IT-PO surface hints (for assignment): the standalone command is a workflow/skill
template body + a new reviewer agent template => llm-expert for the agent prompts
and the perspective definitions; the /build-feature end-of-run wiring and the
ticket-emission glue is workflow-script/python-coder. The three reviewer agents
are dispatched at depth 1 per ADR-006 — the spot-check pass must NOT chain a
build supervisor inline.
