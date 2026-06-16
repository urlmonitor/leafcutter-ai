---
title: "Reconcile ac-scanner/build-ac skill portability with script deployment reality"
status: ready
type: design_decision_ticket
components:
  - skills_system
  - build_pipeline
  - ac_store
created: 2026-06-16
depends_on: []
priority: medium
requires_diagram: false
requires_adr: true
epic: EPIC-AcPipelineDeployGaps
files_touched:
  - config/skill_registry.json
  - scripts/build_phases.py
  - templates/scripts/ac_store/
  - docs/how-to/ac-driven-build-loop.md
  - docs/architecture/adrs/
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  documentation-expert: needed
  commit: needed
  pr-reviewer: needed
  pull-request: needed
---

# 03: Reconcile ac-scanner/build-ac Skill Portability

## Goal

Make a binding design decision about whether ac-scanner and build-ac are consumer-facing portable skills (and thus require script deployment), or package-internal non-portable skills (and thus should not be advertised to consumers).

## Context

**Design Decision Required: architect-review MUST adjudicate and record the decision before implementation begins.**

Skills ac-scanner and build-ac are marked `portable: true` in config/skill_registry.json, which signals that they are meant to deploy to consumer installs. However, the scripts they depend on have no deployment phase:

- scripts/ac_store/scan_ac_store.py
- scripts/ac_store/generate_ticket_from_ac.py
- scripts/ac_store/ac_prioritizer.py
- scripts/ac_store/mark_ac_done.py
- scripts/build_ac_mode_detection.py
- scripts/goal_to_epic.py

There is no `build_ac_store` phase in scripts/build_phases.py and no templates/scripts/ac_store/ directory. On a consumer install, the skills would be present but their scripts absent — they would fail at runtime.

**The decision is structural:** Is the AC-driven build loop intended to run on consumer installs (ADR-010 argues for portability), or is it package-development-only?

**IT PO recommendation:** Option (a) — add a build_ac_store deployment phase + templates/scripts/ac_store/ — if the AC-driven build loop is a consumer-facing feature. Option (b) — mark ac-scanner and build-ac `portable: false` (package-internal) — if /build-ac is development-only.

**Parallelism note:** TICK-B also edits scripts/build_phases.py (different function). Do not run TICK-B and TICK-C in the same parallel batch without a merge step.

## Acceptance Criteria

### AC-1: Design decision is documented and recorded
- **Given** architect-review has read ADR-010 and the skill portability context
- **When** the decision is adjudicated (either option a or option b)
- **Then** the decision is recorded in this ticket's ## Comments section with explicit reasoning, and an optional ADR clarifying portable vs package-internal boundaries is authored or recommended

### AC-2: If option (a) is chosen: build_ac_store phase is implemented
- **Given** the decision is made to add a build_ac_store deployment phase
- **When** python-coder implements the build_ac_store function in scripts/build_phases.py
- **Then** the function copies scripts/ac_store/scan_ac_store.py, scripts/ac_store/generate_ticket_from_ac.py, scripts/ac_store/ac_prioritizer.py, scripts/ac_store/mark_ac_done.py, scripts/build_ac_mode_detection.py, and scripts/goal_to_epic.py into templates/scripts/ac_store/

### AC-3: If option (a) is chosen: templates/scripts/ac_store/ directory structure is correct
- **Given** the build_ac_store phase has run
- **When** a test inspects the build output in templates/scripts/ac_store/
- **Then** all six required scripts are present and byte-identical to their source files:
  - scan_ac_store.py
  - generate_ticket_from_ac.py
  - ac_prioritizer.py
  - mark_ac_done.py
  - build_ac_mode_detection.py
  - goal_to_epic.py

### AC-4: If option (a) is chosen: build phase is called in correct sequence
- **Given** scripts/build_phases.py has been updated with build_ac_store
- **When** the build_phases module is imported and the phase execution order is inspected
- **Then** build_ac_store is called after build_workflow_scripts but before final artifact assembly, and the exported build.py main() function includes a call to build_ac_store(target_root, config, dry_run, force)

### AC-5: If option (b) is chosen: skill registry is updated correctly
- **Given** the decision is made to keep ac-scanner and build-ac package-internal
- **When** config/skill_registry.json is updated by python-coder
- **Then** both ac-scanner and build-ac entries have `"portable": false` and do not appear in a consumer install's advertised skill list

### AC-6: Skill portability is consistent with script presence
- **Given** the chosen option is implemented and a consumer build has run
- **When** test-writer adds a test_skill_portability_consistency test to the build test suite
- **Then** the test asserts:
  - Every skill with `portable: true` has all its dependency scripts present in the deployed target directory
  - Every skill with `portable: false` is absent from the consumer-facing skill registry (does not appear in config/skill_registry.json in the deployed target)
  - No skill is advertised (portable: true) whose scripts are missing

### AC-7: Consumer install receives consistent artifact
- **Given** a consumer runs the leafcutter build against their project
- **When** the build completes successfully
- **Then** either:
  - (Option a path) the consumer's .leafcutter/scripts/ includes ac_store/ with all six scripts, and `/build-ac` and `/ac-scanner` commands are available
  - (Option b path) the consumer's .leafcutter/scripts/ does not include ac_store/, and `/build-ac` and `/ac-scanner` commands are not advertised in the skill list

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

**Ticket hardening: 2026-06-16**
- Stub expanded into AC-rich, design-decision ticket format
- Seven comprehensive Gherkin ACs added (AC-1 through AC-7) covering decision gate, both implementation options, and consistency verification
- Implementation tasks broken down by agent with explicit deliverables and checkboxes
- Risk assessment expanded with reversibility analysis and breaking change notes
- Parallelism guidance added for EPIC-AcPipelineDeployGaps orchestration
- Frontmatter enhanced with type: design_decision_ticket, requires_adr, and files_touched

**Execution notes:**
- architect-review is the critical path gate — no implementation begins until this agent records the design decision
- This ticket is ready for `/build-feature` dispatch after hardening
- Recommended execution order: architect-review → python-coder + documentation-expert (parallel) → test-writer → pr-reviewer → commit

## Implementation Tasks

### architect-review (Design Decision Gate)

**Deliverables:**
- Design decision recorded in ## Comments section before any code work begins
- Optional ADR authored or recommended (if boundary between portable and package-internal skills needs permanent documentation)

**Task breakdown:**
- [ ] Load ADR-010 and the skill portability design docs to understand consumer-facing feature scope and design rationale
- [ ] Examine the skills_config.json pattern for portable-false examples to understand precedent (if any)
- [ ] Check ADR-001 (self-hosting boundary) to understand how portability decisions affect consumer installations
- [ ] Adjudicate and record the design decision: is the AC-driven build loop (a) a consumer-facing feature requiring portable script deployment, or (b) package-development-only?
- [ ] If the decision establishes a clear policy for portable vs package-internal, author or recommend a new ADR (e.g. ADR-012-portable-skill-boundary.md)
- [ ] Record the decision in this ticket's ## Comments section with reasoning before implementation begins

### python-coder (Implementation Gate: Depends on architect-review decision)

**For option (a) — Portable AC-driven pipeline with script deployment:**

- [ ] Create a new `build_ac_store()` function in scripts/build_phases.py following the pattern of existing build phases (build_workflow_scripts, build_hooks)
  - Function signature: `build_ac_store(target_root: Path, config: dict, dry_run: bool, force: bool) -> int`
  - Return value: number of files written
  - Behavior: copy all six scripts from source to templates/scripts/ac_store/
- [ ] Ensure the function copies the exact files with identical content (no compilation or template rendering):
  - scripts/ac_store/scan_ac_store.py → templates/scripts/ac_store/scan_ac_store.py
  - scripts/ac_store/generate_ticket_from_ac.py → templates/scripts/ac_store/generate_ticket_from_ac.py
  - scripts/ac_store/ac_prioritizer.py → templates/scripts/ac_store/ac_prioritizer.py
  - scripts/ac_store/mark_ac_done.py → templates/scripts/ac_store/mark_ac_done.py
  - scripts/build_ac_mode_detection.py → templates/scripts/ac_store/build_ac_mode_detection.py
  - scripts/goal_to_epic.py → templates/scripts/ac_store/goal_to_epic.py
- [ ] Create templates/scripts/ac_store/.gitkeep if it doesn't exist (directory structure placeholder)
- [ ] Verify the build step is called at the correct point in scripts/build_phases.py (after build_workflow_scripts but before final artifact assembly)
- [ ] Update the module docstring in build_phases.py to document the new phase

**For option (b) — Package-internal AC pipeline (non-portable):**

- [ ] Update config/skill_registry.json:
  - Locate the ac-scanner entry (if present) and set `"portable": false`
  - Locate the build-ac entry (if present) and set `"portable": false`
- [ ] Verify the entries do not have a template_path field (or it points to a location that will not be deployed)
- [ ] Test locally that the skill registry JSON is valid

### test-writer (Test Gate)

**Deliverables:** Tests that verify skill-to-deployment consistency

**Test implementation (option-agnostic structure):**
- [ ] Add `test_ac_store_scripts_deployed()` to the build test suite:
  - Only runs if option (a) is chosen (read decision from ticket comments or a config flag)
  - Verifies all six scripts exist in the build output at templates/scripts/ac_store/
  - Asserts byte-identical content between source and deployed files
  - Failure message lists which scripts are missing
- [ ] Add `test_ac_store_skills_not_advertised_when_not_portable()` to the build test suite:
  - Only runs if option (b) is chosen
  - Loads the deployed skill registry from the build output
  - Asserts ac-scanner and build-ac do not appear in the skills list
  - If they do appear, fails with a message indicating portable: false is not being honored
- [ ] Add `test_skill_portability_consistency()` as a general assertion (applies to both options):
  - For every skill in the deployed skill registry with `portable: true`, verify all scripts it depends on are present in the build output
  - For every skill with `portable: false`, verify it does NOT appear in a consumer-facing skill registry (if a separate registry exists)
  - Maintain a mapping of skill id → required scripts (ac-scanner → [scan_ac_store.py, ac_prioritizer.py, mark_ac_done.py], build-ac → [generate_ticket_from_ac.py, build_ac_mode_detection.py, goal_to_epic.py])

### documentation-expert (Documentation Gate)

**For option (a) — Portable AC-driven pipeline:**

- [ ] Create docs/how-to/ac-driven-build-loop.md documenting the AC-driven build loop as a consumer-facing capability
  - Explain the purpose: AC store as authoritative backlog, ticket generation, and automated work dispatch
  - Link to ADR-010 and ADR-007b
  - Show an end-to-end example: creating an AC, running /build-ac, and completing the generated ticket on a consumer install
  - Document the relationship between /ac-scanner, /build-ac, and the AC store
  - Note: /build-ac requires /plan-feature deployment (see EPIC-AcPipelineDeployGaps ticket 02)
- [ ] Update docs/glossary.md with definitions for any new terminology introduced (e.g., "portable skill", "ac-driven build loop")

**For option (b) — Package-internal AC pipeline:**

- [ ] Update docs/architecture/adrs/ADR-001-self-hosting-boundary.md or create a new section documenting why ac-scanner and build-ac are package-development-only tools
  - Link to the decision record (this ticket)
  - Explain what tools are available for building software on consumer installs vs package development
  - Note: the AC store framework is available (read-only) for advanced consumers, but ac-scanner and build-ac are reserved for leafcutter package maintainers
- [ ] Add a note to docs/how-to/ (or a new docs/reference/package-development-tools.md) listing which tools are package-internal and why

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No (affects build deployment and consumer product scope only).
- **Reversibility?** Medium. Switching between options (a) and (b) is reversible but requires rebuilding skill registry and re-deploying consumers. A consumer that installed with option (b) cannot be upgraded to option (a) without a new deployment; the reverse also requires explicit instruction.
- **Breaking changes?** If option (a) is chosen, new templates/scripts/ac_store/ scripts will be deployed to all consumers. If option (b) is chosen, consumers who expect /build-ac or /ac-scanner will see skill-not-found errors — must be documented as a breaking change or a policy decision.
- **Scope interaction:** This ticket does NOT implement /plan-feature or /build-ac skill templates themselves. It only decides whether those skills' scripts deploy with them. EPIC-AcPipelineDeployGaps ticket 02 handles /plan-feature deployment; the actual skill templates are created separately.

## Parallelism & Dependencies

**Parallel safety:** This ticket is **independent** of EPIC-AcPipelineDeployGaps tickets 01, 02, and 04 in terms of code changes (each edits a different module or decision layer). However, **do not run TICK-C (this ticket) in the same parallel batch as TICK-B (ticket 02) without a merge step** if TICK-B also edits scripts/build_phases.py. The two tickets have different functions they add (build_plan_feature vs build_ac_store), so both can coexist, but editing the same file concurrently will create merge work. Recommendation: merge TICK-B first, then run TICK-C on the resulting main branch.

**Dependency chain after this ticket:**
- If option (a) is chosen, the build_ac_store phase is available but dormant until templates/workflows-js/plan-feature.js and templates/workflows-js/build-ac.js are deployed (handled by other tickets or future work).
- If option (b) is chosen, no downstream tickets depend on this decision — the AC pipeline continues to work for package developers, and consumers do not see the tools.
