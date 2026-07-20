> Re-authored under GE-117 (originally drafted as GE-114; renumbered to resolve id collisions on main).

# IT-PO learning — two component registries: components.json (validity) vs index.yaml (directory_patterns / inference)

Captured 2026-07-02 during GE-114 (code-declares-what-it-serves) technical enrichment.
Component: guardrail-engine (GE). Confirmed with user (BrainCandy).

## The trap: "reuse the components.json directory_patterns field" is WRONG

PO/BA authoring notes on GE-114 (and the earlier PROJECT_CONTEXT note) said the
autofix component-inference should "reuse the components.json directory_patterns
precedent (same field /quick-fix uses)". This CONFLATES two distinct registries:

- **docs/components.json** — the CODE-component registry. Fields: `id`,
  `primary_code`, `name`, `type`, `status`, `detail_ref`. Ids look like
  `commit_guardian`, `ac_store`, `build_pipeline`. It has NO `directory_patterns`
  field. This is what `check_components_integrity.py` guards and what the
  `components_registry: docs/components.json` config key points at. => This is the
  VALIDITY target: a module-docstring component declaration must resolve to a
  components.json id.
- **docs/acceptance-criteria/index.yaml** — the AC-STORE component index. Fields:
  `id`, `prefix`, `description`, `owner`, and `directory_patterns`. Ids look like
  `guardrail-engine` (prefix GE), `build-pipeline` (BP), `ac-store` (ACS). The
  `directory_patterns` field is the one /quick-fix uses (BP-600b-2-i:
  "maps file paths to component IDs via index.yaml directory_patterns field").

The two id namespaces DO NOT map 1:1 (guardrail-engine ≠ commit_guardian), so
index.yaml directory_patterns CANNOT be used to infer a valid components.json id.

## Consequence to encode as an it_requirement (not silently assume)

When a feature's autofix must INFER a components.json id from a file path, that
inference is NOT implementable off index.yaml. It is a PREREQUISITE: either add a
directory/primary_code-pattern-based inference to components.json, or add a
components.json<->index.yaml bridge. Until then, the autofix must PROMPT for the
component (fall back to the prompt-on-ambiguity edge case) rather than infer it.
The AC-id inference for the AC surface is UNAFFECTED — it resolves against the AC
store via scan_ac_store.py `_load_ac_by_id`, not against either component registry.

Always ask: "is this path->component mapping being resolved for VALIDITY
(components.json) or for INFERENCE (index.yaml directory_patterns)?" They are
different files with different ids. Do not let a PO/BA note that names one imply
the other.

## Reusable resolver + validator lineage for GE-114-class docstring hooks

- AC-id existence resolver: `scan_ac_store.py :: _load_ac_by_id(ac_store_root, ac_id)`
  returns the record or None. EXTRACT it into a shared importable module (don't
  copy-paste, don't import-from-CLI); None cleanly distinguishes invalid
  (well-formed dangling ref) from missing (no ref) — the exact valid/invalid/missing
  trichotomy the three declaration surfaces need.
- Decision-history AC surface EXTENDS the existing tail-tag validator
  (check_documentation.py + doc_validators.py + docstring_validators.py) which
  already carries the TICKET tag — add the AC dimension only, never re-specify the
  ticket tag.
- Module + symbol surfaces = a NEW check_declaration_traceability.py; "public"
  symbol detection is in-process stdlib `ast` over the staged blob (underscore rule
  + __all__ authoritative) — a commit hook has NO MCP channel (recurring GE-111 rule).
- All three surfaces emit a structurally-uniform per-item verdict so the aggregator
  (block/proceed) can consume them together; single-valued expects_from keeps the
  primary upstream, the other two surface producers travel via depends_on +
  it_requirements.

## Opt-out wire-format decision for a per-item escape hatch

For a "deliberate, visible, per-item, reason-required, non-global" opt-out the
concrete wire-format chosen (user-confirmed) is the inline sentinel
`AC-EXEMPT: <reason>` in the item's own docstring/entry (lands in the diff,
reviewable). Reason-less marker and any global disable are fail-closed (rejected).
This is the reusable shape when a criteria text pins the opt-out BEHAVIOR but
leaves the token to the IT-PO.

## Agent-assignment spine confirmed (no re-route needed this run)

The BA's assignments were correct for this hook class: every behavioral/wiring
leaf = python-coder (one new hook + one extended validator, both under
scripts/commit_guardian/ deployed + templates/commit-guardian/ source, ADR-001
parity); how-to leaves = documentation-expert; sequence-diagram leaves =
architecture-diagram-author. No llm-expert surface (no prompt/skill/template-prose).
No splits — the BA had already separated hook vs how-to vs diagram cleanly. The 6
composite ACs (L0 + 5 L1s) correctly carry no assigned_agent/it_requirements.
