---
title: "Kernel contracts: every field says why it exists, in the schema LLMs and Atlas read"
status: in_progress
components:
  - decision_kernel
created: 2026-10-09
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - contracts
  - documentation
last_updated: 2026-10-09
agents:
  python-coder: signed_off
  commit: needed
---

# Kernel contracts: every field says why it exists, in the schema LLMs and Atlas read

## Actor / Goal
In order for LLMs and humans to understand why each field of a kernel contract exists, we need that purpose recorded on the Pydantic model, where it flows into the committed JSON Schemas. Every host work packet already sends those schemas to the LLM (`output_json_schema`), so the purpose would reach the LLM directly.

## Context
- **User request (2026-10-09):** "summarize for LLMs and humans why fields in specific contracts exist".
- **Today:**
  - 38 kernel modules use Pydantic v2 (2.13.5).
  - There are 0 `Field(description=...)`, and 197 `#:` comments carry the purpose but never reach a schema.
  - The committed schemas describe almost no fields; `decision_report.v1` has 49 typed properties and 8 descriptions.
- **Mechanism:** `ConfigDict(use_attribute_docstrings=True)` (Pydantic 2.7+) turns a docstring placed directly under a field into its schema `description`.
- **Follow-up:** a separate decision (product-truth field guide) may point flows at these descriptions instead of repeating them.

## Scope (no ACs, by user decision)
- Enable `use_attribute_docstrings=True` on `KernelModel`.
- Convert the `#:` comments to attribute docstrings with the same meaning.
- Write the missing purposes for public contract fields: the schemas in `kernel/schemas/` and the models behind them.
- Regenerate the committed schemas and keep the sync tests green.
- **Coverage test:** every field of every committed contract schema has a description, and a description does not merely repeat the field name or type.
- **Style:** a description says why the field exists or which step or decision uses it, in one sentence. It names no code paths.

## Out of Scope
- Non-kernel schemas (AC store, product truth): covered by the field-guide decision.

## Sign-offs

- [x] python-coder — 2026-10-09
- [ ] commit

## Comments

### 2026-10-09 — python-coder (status: ok)
feedback-id: fb_2026-10-09_e834dbcb

- `KernelModel` and the other contract bases (`_Section`, `_Model`, the context/entity/memory config models) set `use_attribute_docstrings=True`. The `#:` field comments in my files became attribute docstrings.
- A purpose was written for every property of the 18 `kernel/schemas/*.schema.json`, `config/decision_record.schema.json` and `config/kernel_config.schema.json`. The committed schemas were regenerated with `export_json_schemas`, `write_schema` and `write_config_schema`.
- `tests/kernel/contracts/test_schema_descriptions.py` fails if any property of those 20 schemas lacks a description or only repeats its name. It also checks a host packet's `output_json_schema` (the `findings.v1` schema and a real graph-built packet).
- No allowlist: every field is described. The knowledge-graph binding fields get theirs in `integrations/knowledge_config.py`.
- To stay under 400 lines: `config.py` was split into `config_sections.py` and `config_retrieval.py`; `payloads.py` into `payloads_human.py`; `memory/models.py` into `memory/record_sections.py`. The old import paths still work.
