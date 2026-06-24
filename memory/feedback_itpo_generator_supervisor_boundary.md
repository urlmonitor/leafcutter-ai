# IT-PO learnings — generator(.py) / supervisor-template(.md) boundary (leafcutter)

Captured 2026-06-22 during TKT-500f-6 cluster (EPIC-CodeQualityHooks KI-1)
technical enrichment, component: ticket-creation.

## The "section presence is the signal" feature splits across python-coder + llm-expert

A feature where a generator EMITS a marker (here: the `## Test Requirements`
section in a generated ticket) and a SUPERVISOR reads that marker to gate a
phase (here: ticket-supervisor deciding whether to run test-writer) crosses a
hard owner boundary the BA usually misses:

- **The generator** (`scripts/ac_store/generate_ticket_from_ac.py` +
  `scripts/goal_to_epic.py`) is `.py` => **python-coder**. It owns the shared
  classification predicate and the section emission.
- **The supervisor gating rule** lives in `templates/agents/ticket-supervisor.md`
  prose (the "Docs-only / config-only test-writer skip rule" section, ~lines
  295-314) => **llm-expert**. Changing what the supervisor DOES on an absent
  section is template-prose work, not Python. (Matches my standing rule of
  thumb: "if the criteria describe what an AGENT should DO/SAY, surface is a
  template body => llm-expert.")

The BA stamped all five leaves python-coder. Split the supervisor-behavior leaf
(TKT-500f-6-iii) into `-a` (python-coder generator+helper) and `-b` (llm-expert
template rule), wired delivers_to(-a)/expects_from(-b).

## Spec-parity, NOT code-import, across the .py/.md boundary

A markdown agent/supervisor template CANNOT import a Python helper. So when the
generator and the supervisor must agree on the SAME predicate (here:
"what counts as an implementation .py in scope"), do NOT write an
it_requirement that says "reuse the shared helper" as if a code import bridges
them. Instead mandate SPEC PARITY: state the rule once normatively in a spec
doc (here `docs/reference/ac-schema.md`) and require BOTH the Python helper and
the template prose to mirror that single normative definition. Capture the
drift risk explicitly. Then flag the missing normative spec section as an
ADVISORY caveat (do not auto-author a reference-doc AC unless the parent L1
carries a `reference-doc`/`how-to` documentation_trigger — TKT-500f triggers
were [sequence-diagram, component-diagram] only, so S7b did not force it).

## Pre-existing silent-skip rule = the defect to rewrite, not extend

The ticket-supervisor's absent-section rule ALREADY existed and treated absence
as a blanket skip-for-everyone. The retro finding (KI-1) is that this silently
skips test-writer even when an implementation .py is in scope. The llm-expert
leaf must REWRITE the existing rule (make the absent branch conditional on
files_touched: halt with structured error when impl-.py present; legit skip
when docs/config-only), not bolt on a new rule beside it. Always read the
template surface first to confirm whether the behavior is new or a rewrite.

## Phantom contract target: verify delivers_to.agent against the registry

The BA wrote `delivers_to.agent: ac-supervisor` and the criteria prose said
"ac-supervisor" — there is NO `ac-supervisor` in config/agent_registry.json.
The real gating agent is `ticket-supervisor`. IT-PO fix: repoint the
delivers_to/expects_from agent field (a technical field) to the real agent;
leave the criteria PROSE unchanged (BA's domain) but add an amended_by note so
the final-gate reviewer sees the prose/field mismatch and a BA can correct the
prose in a follow-up. Always validate every delivers_to/expects_from agent id
against the registry — a phantom target produces an undispatchable contract.
