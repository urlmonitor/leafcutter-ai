#!/usr/bin/env python3
"""
MODULE: _gtfa_decision_history
GOAL: Hold the ticket generator's DECISION HISTORY — the dated record of why
    each behaviour of ``generate_ticket_from_ac`` is the way it is.
BUSINESS CONTEXT: Almost every entry below records a defect that shipped and a
    rule adopted to stop it recurring. Several of them describe behaviour that
    looks arbitrary or removable until you read the entry: the pipe-delimited
    contract line, the union semantics on non_triggering_classifications, the
    refusal to default a ticket's location. Losing this record is how a fix
    gets undone by someone tidying up.
ARCHITECTURE: A module whose entire contents are its docstring. It exists as a
    separate file only because the history is 174 lines and the shell module it
    documents must stay under the repo's 400-line cap — the history is
    documentation, and the size gate must never be satisfied by deleting
    documentation. ``generate_ticket_from_ac`` points here from its own
    docstring; nothing imports this module for behaviour.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [ticket-01]: Initial implementation.
  Searches ac_root recursively for the AC with the given id. Extracts
  local paths from doc_links (filtering http URLs). Builds agents map with
  assigned_agent + canonical support agents. Writes ticket to tickets_root.
  Performs implemented_by back-write using targeted line replacement (not
  full yaml.dump round-trip) to minimise diff noise. Idempotency guard:
  exits 1 when a ticket with source_ac: <ac_id> already exists.
- 2026-07-08 [ticket-03 EPIC-PromptAssemblyHardening]: Add ## Implementation Notes emission.
  Added _build_implementation_notes_section() helper that serialises the
  it_requirements dict from an AC record to a YAML code block inside a
  ## Implementation Notes section. Omits the section entirely when
  it_requirements is absent (no empty stub). Section is placed after
  ## Test Requirements and before ## Sign-offs for consistent locatability.
  (AC BO-2000c-1, BO-2000c-1-i, BO-2000c-2)
- 2026-07-08 [feature/ac-source-of-truth-test-spec]: Derive ## Test Requirements
  from the AC (source of truth) instead of emitting a hardcoded tests: [] stub.
  Added _build_test_requirements_section() + _test_descriptors_from_spec()
  (from the AC's test_spec) with a _derive_tests_from_criteria() fallback
  (Gherkin Then-clauses). The derived block always carries >=1 populated test
  entry so the check-ticket-test-requirements guard passes by construction;
  omitted only when the AC sets test_required: false. Added a --verify flag +
  _build_verification_report() that prints the would-be ticket plus a PASS/WARN/
  FAIL readiness report (exits non-zero on FAIL) so an author can confirm the AC
  gives a coder enough to build and test-writer enough to test. (AC BO-2000e)
- 2026-07-16 [TICKET-20260715-BO-2200c-1]: Emit ## Agent Contracts section.
  Added _build_agent_contracts_section() that emits an '## Agent Contracts'
  heading with a '### documentation-expert' subsection when documentation-expert
  is in the agents map as 'needed'. The subsection carries one globally-numbered
  '- [ ] AC-1: <title>' checklist item for the source AC. Section is positioned
  after ## Acceptance Criteria (and Test Requirements / Implementation Notes)
  and before ## Sign-offs. Tickets without documentation-expert:needed are
  unaffected. (AC BO-2200c-1)
- 2026-07-17 [TICKET-20260715-BO-2200a-1]: Add documentation_gates data-driven trigger.
  Added a documentation_gates read-path in _build_agents_map: after the
  flow_change_gates processing, the gates config is checked for a
  documentation_gates.change_target_triggers list.  When any change_target in
  the call intersects that list, documentation-expert is added to guardrail_set
  as 'needed'.  The trigger set is read from config at call-time so that
  adding/removing a value is purely a config edit (BO-2200a-1).  Also added the
  documentation_gates section to config/guardrail_gates.yaml with
  change_target_triggers: [ui, schema, pipeline, docs] and risk_surface_triggers
  for future use.
- 2026-07-17 [TICKET-20260715-BO-2200a-2]: Add risk_surface_triggers dimension to
  documentation_gates policy in _build_agents_map.  Extended the documentation_gates
  evaluation to read risk_surface_triggers from the gates config.  When risk_surface
  matches any entry in risk_surface_triggers, documentation-expert is added to
  guardrail_set as 'needed' independently of the change_target_triggers check (OR
  semantics: documentation-expert is required if EITHER dimension matches its
  triggering set).  The trigger set {contract_boundary, safety, auth, privacy} is
  already present in config/guardrail_gates.yaml — no config change required (BO-2200a-2).
- 2026-07-20 [TICKET-20260715-BO-2200a-3]: Add non_triggering_classifications guard to
  documentation_gates policy in _build_agents_map.  After both trigger dimensions have
  had a chance to add documentation-expert, a third read-path checks
  documentation_gates.non_triggering_classifications from the gates config.  If any
  entry's (change_target, risk_surface) pair matches the call's arguments,
  documentation-expert is discarded from the guardrail set — even if the general trigger
  lists would otherwise require it (explicit negative rule overrides positive triggers).
  Added non_triggering_classifications list to config/guardrail_gates.yaml covering the
  four internal-refactor pairs: code/internal, config/internal, prompt/internal,
  infrastructure/internal (BO-2200a-3).
- 2026-07-20 [TICKET-20260715-BO-2200a-4]: Apply union semantics to list-valued
  change_targets in non_triggering_classifications check (Dimension 3).  Fixed a bug
  where a non_triggering entry for one element (e.g. config/internal) could suppress
  documentation-expert even when a different element in the list (e.g. ui) independently
  triggered it via change_target_triggers.  The fix: instead of discarding
  documentation-expert whenever any non_triggering entry's change_target is found in the
  list, collect all triggering elements (change_targets ∩ doc_change_triggers) and only
  discard when EVERY triggering element is covered by a non_triggering entry for the
  current risk_surface.  For the Dimension-2-only path (risk_surface_triggers trigger),
  the original scalar suppression is preserved unchanged.  (AC BO-2200a-4)
  (#EPIC-DocumentationCoverageGuarantee/05)
- 2026-07-20 [TICKET-20260715-BO-2200b-4]: Inject documentation-verifier alongside
  documentation-expert; set documentation_required: true in frontmatter.
  _build_agents_map: after all non_triggering_classifications discard passes, when
  documentation-expert remains in guardrail_set, documentation-verifier is also added to
  guardrail_set.  Both agents are gated on the same trigger decision so removing
  documentation-expert via the non-triggering guard also removes documentation-verifier.
  _build_frontmatter: when documentation-verifier appears in the agents map as 'needed',
  sets documentation_required: True in the frontmatter, signalling to downstream agents
  that a documentation review cycle is in flight.  When the AC does not trigger a
  documentation demand, neither documentation-verifier nor documentation_required: true
  appears.  Added documentation-verifier to _CANONICAL_PHASE_ORDER (after
  documentation-expert) and _FLOW_CHANGE_PHASE_ORDER (after documentation-expert).
  (AC BO-2200b-4) (#EPIC-DocumentationCoverageGuarantee/13)
- 2026-07-21 [TICKET-20260715-BO-2200c-2]: Each documentation-expert contract line
  carries a Diataxis genre, a target doc path, and a criteria-derived content constraint.
  Added three helpers: _extract_doc_genre (reads documentation_triggers[0], defaults to
  "explanation"), _extract_doc_path (scans doc_links for first local path with "/",
  computes docs/<genre>/<slug>.md default), _derive_content_constraint (extracts first
  Then clause from Gherkin criteria, falls back to first non-empty criteria line).
  Modified _build_agent_contracts_section: the "- [ ] AC-1:" line now emits
  "[<genre>] <doc_path> — <constraint>" instead of the AC title verbatim.
  (AC BO-2200c-2) (#EPIC-DocumentationCoverageGuarantee/18)
- 2026-07-21 [feature/bp-1100f-hardening/BP-1100f-5]: Add declares_side_effect
  routing (BP-1100f-5). Added declares_side_effect: bool = False parameter to
  _build_agents_map. When True, user-surface-smoker is added to all_needed so
  the observable-side-effect smoke check runs automatically and gates the done
  state. The routing is data-driven: the smoke check fires because the work item
  DECLARED a durable side-effect, not because of an opt-in flag or hard-coded
  name. Items without the declaration are exempt (BP-1100f-5-i). Added
  user-surface-smoker to _CANONICAL_PHASE_ORDER and _FLOW_CHANGE_PHASE_ORDER at
  position 11.5 (after pr-reviewer, before ac-validator) so the phase is correctly
  ordered and cannot be silently skipped. _build_frontmatter propagates
  declares_side_effect from the source AC to the ticket frontmatter so downstream
  tools can read the declaration directly. Both call sites in main() updated to
  extract and pass declares_side_effect from the AC record.
- 2026-08-18 [python-coder]: Corrected the _build_frontmatter docstring's false
  claim that ac_traceability enables "ac-validator and ac-fulfillment-gate" to
  locate the source AC. ac-validator does not read ac_traceability at all;
  ac-fulfillment-gate (via the new ac_coverage_resolver module) is the sole
  consumer. The producer's emitted two-key {id, path} shape is unchanged
  (ACD-1900b-5-i). (#ACD-1900b-5-i)
- 2026-08-26 [python-coder BO-2200c-5 / KI-ACD-002]: Fixed two producer/consumer
  format defects in the ## Agent Contracts -> ### documentation-expert block.
  (1) Changed each '- [ ] AC-N:' checklist line from the bracket + em-dash
  format ('[<genre>] <doc_path> — <constraint>', zero pipe separators) to the
  pipe-delimited format documentation-verifier.md Step 2 actually documents
  and parses ('<genre> | <target_path> | <content_constraint>'). Every real
  doc-required ticket previously failed the verifier's documented parse rule.
  (2) _resolve_genres_from_parent now distinguishes a parent L1's ABSENT
  documentation_triggers key (still falls back to the "(unspecified genre)"
  fail-soft marker, BO-2200c-3-i) from an explicit, present
  documentation_triggers: [] (returns [] — the store's documented way of
  declaring "no documentation required", e.g. BP-900g.yaml's
  documentation_rationale). _build_agent_contracts_section now suppresses the
  entire documentation-expert subsection when genre resolution yields an
  empty list, instead of emitting a phantom '(unspecified genre)' contract
  line. (#BO-2200c-5)
- 2026-09-01 [python-coder]: Added location-keyed phase deferral (TKT-600b-1
  family). _build_agents_map gained resolved_destination / phase_deferral_path
  / deferred_phases parameters; a phase the new config/phase_deferral.yaml
  declaration defers for a location (e.g. pull-request for an epic-member
  ticket) is now recorded as an explicit "not_needed" entry rather than left
  "needed" or silently omitted (TKT-600b-1-ii's catch-all: every canonical
  phase agent now gets an explicit entry). Added PhaseDeferralDeclarationError
  and UnresolvedDestinationError so a missing declaration or an unresolved
  final location REFUSES generation instead of defaulting (TKT-600b-1-i);
  main()'s ticket-writing path (never --dry-run/--verify) always resolves the
  declaration and requires --resolved-destination whenever it is
  location-dependent. Added --resolved-destination and --phase-deferral-path
  CLI flags. Added reject_phantom_signoff() so an agent recorded "signed_off"
  with no backing comment-log entry is rejected rather than accepted as an
  alternative to "not_needed" (TKT-600b-2). A standalone ticket's own
  pull-request phase is unaffected (TKT-600b-3). KNOWN FOLLOW-UP: this makes
  main()'s write path refuse for any caller that omits --resolved-destination,
  including scripts/goal_to_epic.py (named as a co-requisite file in
  TKT-600b-1-i's doc_links but out of this batch's authored test scope) and a
  handful of pre-existing non-dry-run generator tests
  (unit_tests/test_generate_ticket_from_ac.py::TestEndToEndGeneratorComputedMap
  and three cases in unit_tests/ac_store/test_generator_frontmatter_gaps.py)
  that call main() without the new flag — each needs a one-line
  --resolved-destination addition. (#TKT-600b-1) (#TKT-600b-1-i) (#TKT-600b-1-ii)
  (#TKT-600b-2) (#TKT-600b-3)
- 2026-09-07 [python-coder]: Added TKT-600a-2's structured-declaration
  suppression rule to _build_files_touched. New helper
  _paths_declared_non_edit_surface_only(doc_links) maps each dict-shaped
  doc_links path to the set of relationships it is declared under; a path
  declared ONLY at relationships outside _EDIT_SURFACE_RELATIONSHIPS (e.g.
  related, describes) and never at an edit-surface relationship is now
  excluded from Source 1's prose harvest, even when the same path is also
  named in a prose it_requirements bullet and exists on disk. A path
  declared at an edit-surface relationship anywhere in the record is never
  suppressed (the edit-surface declaration wins over a co-existing
  non-edit-surface declaration of the same path). This is a second,
  independent filter in front of TKT-600a-1's on-disk existence gate — it
  reads the record's own structured doc_links relationship enum, not
  English prose cues, and does not touch _is_real_prose_path or
  _extract_paths_from_prose. (#TKT-600a-2)
- 2026-09-14 [python-coder]: Decomposed the module. generate_ticket_from_ac.py
  had reached 4035 lines against the repo's 400-line Python cap, with a single
  455-line function (_build_agents_map) inside it. The file is now a SHELL that
  imports and re-exports 21 `_gtfa_*` sibling modules; no function was renamed,
  no signature changed, and no output byte differs — verified against a
  golden-output characterization harness covering 41 real store records
  (previews, write path, implemented_by back-write, and the leaf helpers) plus
  a before/after diff of the module's whole attribute surface. Three seams are
  late-bound through _gtfa_seams because the test suites reach into them on the
  SHELL: _find_worktree_root (patched by test_tkt_500f_17), the logger name
  (asserted by test_tkt_500f_18_i and test_tkt_500f_17), and
  _COMPONENT_MIGRATION_MAP (whose module-level assignment stays in the shell so
  importlib.reload re-runs it, as test_tkt_500f_18_i requires). Every sibling
  is registered in build_phases.AC_STORE_DEPLOY_MAP — the deployed layout
  imports them at module scope, and unit tests import from source, so an
  unlisted sibling would leave the deployed generator dead at import while the
  suite stayed green (the BP-900a-1 / BP-900g-8 failure shape).
====================================================================
"""
