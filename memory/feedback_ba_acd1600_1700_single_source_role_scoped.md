# BA learnings — ACD-1600 / ACD-1700 decomposition (single-source-buildable + role-scoped context)

Captured 2026-08-11 (BA, origin_agent: BrainCandy run) decomposing the two new
ac-driven-dev L0s discovered via the effective-prompt render tool + comprehension tests.

## Governance reversal to carry through enrichment/build (LOAD-BEARING)

ACD-1600a ("thin ticket references its AC, no criteria copy") DIRECTLY REVERSES the
inherited, already-DONE rule ACD-400b ("the ticket body contains the AC's Gherkin
criteria verbatim") and its L2 ACD-400b-1 ("## Acceptance Criteria section contains
the criteria field verbatim", implemented_by scripts/ac_store/generate_ticket_from_ac.py).
The reversal is flagged in ACD-1600a-1.notes and the ACD-1600 L0 notes. IT-PO / user
MUST amend or supersede ACD-400b + ACD-400b-1 via governance BEFORE building ACD-1600a,
or the generator has two contradictory contracts. This is not optional cleanup — the
generator behaviour (copies criteria in) is exactly what ACD-1600a removes.

## Component-home caveats surfaced by the PO, kept in ac-driven-dev but flagged

- ACD-1600f (AC-vs-supporting-artifact consistency gate): the validation-gate mechanism
  may fit guardrail-engine or ac-store better. Authored under ac-driven-dev to keep the
  ACD-1600 goal cohesive; re-home candidate.
- ACD-1700a (role-scoped context injection) and ACD-1700c (render tool): touch the harness
  injection channels / agent knowledge plane — may belong to `infrastructure`. Kept in
  ac-driven-dev; flagged for the user.

## Agent-assignment by surface — a real internal-convention TENSION to reconcile

ACD-1700b encodes "assigned_agent must match deliverable surface". I anchored the flagged
case on the task's stated observed failure: a JS/Node DELIVERABLE handed to python-coder.
BUT memory/feedback_itpo_agent_assignment_by_surface.md (and ACD-1500/BP-1000 enrichment)
treats a `.js` WORKFLOW body under templates/workflows-js/ as python-coder work
(".js workflow body + Python glue = python-coder"). These are not obviously consistent.
IT-PO must pin the exact surface->craft mapping for the .js-workflow case when enriching
ACD-1700b-1/-2 — do not let the check flag legitimate .js-workflow python-coder ACs.

## Assignment pattern I used across both L0s (IT-PO: expect this)

- Generator behaviour (generate_ticket_from_ac.py) => python-coder (ACD-1600a-*).
- "Phase agent reads spec from the store, store wins" => llm-expert (agent-template prose:
  test-writer / python-coder / ac-validator templates) — ACD-1600b-*.
- Readiness/completeness gate, canonical-source pointer check, behaviour-only criteria
  check, artifact-consistency check, role-scoped injection, assignment-quality check,
  render tool => python-coder (deterministic checks / pipeline glue).
- Every documentation_triggers entry got exactly one doc AC per trigger:
  reference-doc/how-to => documentation-expert; sequence/component-diagram =>
  architecture-diagram-author.

## Positive-plus-negative pairing worked well for gate ACs

For each "flag/hold X" gate I authored a positive-pass sibling (…-2) and a concrete-real-
example L3 (…-1-i) using the empirically observed data (ACD-300c-3 / TQ-200a-1 lacking
file targets; `input` vs `request` fixture mismatch; scripts/ path with no templates/
counterpart not falsely flagged). Concrete observed values keep the L3s automated-testable.

## Live field convention (confirmed against ACD-1500 siblings, NOT the stale strict schema)

ACD-1500* (approved) use: id, components[ac_driven_dev], readiness, priority, title,
component, level, status, req_status, work_status, roadmap_phase, criteria, depends_on,
doc_links(list of {path,relationship,status}), assigned_agent, estimated_complexity,
delivers_to, expects_from, origin_agent, created, amended_by, superseded_by, covered_by,
implemented_by, change_target, risk_surface. They do NOT carry `created_by` (contrary to
the older feedback_ba_ac_store_conventions note) — match the same-folder siblings.
validate_ac_schema.py takes explicit file paths (not a directory) — pass *.yaml globs.
