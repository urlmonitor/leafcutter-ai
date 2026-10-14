---
title: "JSON contracts for Product Truth flows"
description: "The checked input/output documentation standard, worked authoring example, validation boundaries and validator JSON run outcome."
type: reference
status: active
created: 2026-10-05
last_updated: 2026-10-09
components:
  - ux_prototyping
related_docs:
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
  - docs/product-truth/README.md
related_code:
  - docs/product-truth/schemas/flow.schema.json
  - docs/product-truth/scripts/product_truth_contracts.py
  - docs/product-truth/scripts/product_truth_contract_sources.py
---

# JSON contracts for Product Truth flows

Use this standard for every flow step and branch. Start with the
[authoring workflow](../how-to/authoring-product-truth-artifacts.md) for search,
registration and review; use the [artifact schema reference](../how-to/product-truth-schema-reference.md)
for the rest of each artifact's shape. This page specifies checked handoffs and
what their validation can establish.

## Document callable inputs and outputs

For every existing and new step and branch, author `io_contracts` using the
[checked JSON handoff reference](#checked-json-handoffs).
A contract name is a reference label, not an extra JSON wrapper. Field paths
start at the contract value; for example, `/original_question` selects that
property directly inside the value shown by the example.

Read the actual contract and receipt first. Name exact field paths, actual JSON
types, requiredness and known defaults. Keep arbitrary transport objects distinct
from any payload schema applied to them. Supply a coherent complete example or an
explicitly labelled projection; observed examples must point to their real receipt.
Use `not_applicable` only for a genuine human/UI/internal transition without a
serialized data handoff. An undefined proposed interface uses `missing_bindings`
with a concrete reason and source, alongside any known bindings. If a proposal
already defines its fields, document that design schema and illustrative example
instead. Never invent an implemented DTO to fill a presentation gap.

For each boundary, identify its authority: an actual runtime contract, a
`source_reviewed` documentation schema, or `illustrative_design`. The latter two
require a nonblank `note` naming the source and limitation; they do not claim
automatic source-code parity or runtime validation. Use the [worked example and checklist](#checked-json-handoffs) below.

Keep the step's `description` to one plain sentence of what happens: the
handoff detail lives here in `io_contracts`, never in the description (see
[What goes where](../how-to/product-truth-schema-reference.md#what-goes-where-in-a-step)).
Run the canonical generator, then `python docs/product-truth/scripts/validate_product_truth.py --quiet`.
That same validator is used by the existing pre-commit gate and focused CI job;
it rejects missing documentation, stale fields/types/defaults, invalid examples,
unsafe references, stale compatibility labels and descriptions that break the
description gates.
Inspect the reported checked-field/example counts, explicit binding gaps and
legacy count (zero after the complete migration). Every existing/new step and
branch needs metadata; no legacy opt-out remains. Passing schema/model checks does not prove semantic correctness or request-bound
relationships between separate payloads. No AC approval or completion follows
from this validation.

## Checked JSON handoffs

The flow-level `contract_definitions` object names local schemas or reviewed runtime models. Every
step and branch needs `io_contracts`: checked JSON bindings with examples, a
precise `not_applicable` reason for a genuine non-JSON action, or explicit
`missing_bindings` for an actually undefined proposed interface. Keep known
bindings even when another interface is missing.

A contract name is a reference label; it does not add a wrapper property to the
JSON example. Field paths start at the contract value: the `request` definition
below describes `original_question` directly, not `request.original_question`.

This is an excerpt of a flow, not a complete flow document. The example request
is illustrative, schema-valid input; it does not claim an observed call or
supported catalog selections. Required catalog dimensions are supplied even when
empty. Defaults may be omitted from a full input but must be documented in fields.

```json
{
  "contract_definitions": {
    "request": {"model": "retrieval_needs_request", "schema": "kernel/schemas/leafcutter.retrieval_needs_request.v1.schema.json"}
  },
  "steps": [{
    "id": "prepare-request", "order": 1, "label": "Prepare the question",
    "description": "The caller supplies a question and the catalog of meanings it may be read against.",
    "actor_kind": "human",
    "io_contracts": {
      "consumes": [{"contract": "request", "fields": [
        {"path": "/original_question", "types": ["string"], "required": true},
        {"path": "/catalog", "types": ["object"], "required": true},
        {"path": "/context", "types": ["array"], "required": false, "default": []}
      ]}],
      "produces": [],
      "examples": [{"contract": "request", "mode": "full", "origin": "illustrative",
        "label": "Complete callable request", "value": {
          "original_question": "Which tests apply?",
          "catalog": {"entity_types": {}, "target_ids": {}, "required_fields": {}, "document_types": {}, "relationships": {}}
        }}]
    }
  }]
}
```

Definition `authority` may be `runtime`, `source_reviewed` or
`illustrative_design`. Models default to runtime authority. A documentation
schema transcribed from TypeScript, Python dictionaries or workflow JavaScript
must say `source_reviewed` and provide a nonblank `note` naming its source and
manual-review boundary. A mock or proposed schema says `illustrative_design`
and explains its design-only scope in `note`. These labels are visible in Atlas;
a schema passing validation does not prove automatic parity with non-model code.

An undefined proposal can carry this metadata (it is not an implemented DTO):

```json
{"missing_bindings": [{
  "name": "Proposed planner input",
  "direction": "produces",
  "reason": "The design names the planning stage but does not define its serialized input yet.",
  "source": "docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json"
}]}
```

That object is a node's `io_contracts`, or `missing_bindings` can accompany checked
`consumes`, `produces` and `examples`. The source must exist and contain text under
`docs/product-truth/` or `docs/analysis/`. Name, reason and source must contain
non-whitespace text. The report lists every gap separately; it is not counted as
a checked field or example. Existing defined contracts cannot be waived this way.

Field `path` uses a JSON pointer; `*` selects an array item or map value. The empty
path denotes the whole JSON value. `required` describes the immediate containing
object. Wildcards describe each present item/value; they never require an array
item or map entry to exist, and the renderer states that distinction. `types` names actual JSON types, including `null` where permitted. Every
known deterministic default must be documented exactly. List/dict factories are
resolved without running arbitrary factories; dynamic defaults have no fixed
value claim. An arbitrary object transport field can add `applies: "output"` to
name a separately defined payload schema. Its transport type stays `object`.

Examples name a bound input/output contract. `full` validates the complete value;
`projection` removes only required-field constraints at schema locations, retaining
types, enums, unknown-key rules and other constraints. The visible projection
label says that omitted required/defaulted fields remain in the linked contract.
`origin` is `observed`, `illustrative` or `reconstructed`. Observed examples require
`source: {"path": "reports/receipt.json", "pointer": "/request"}`. Full values must
match that source exactly; projected values must match its selected fields, and
the full source is also validated. Applied schemas validate present example
payloads, including the full source of an observed projection.

Schemas resolve only inside `docs/product-truth/schemas/`, `kernel/schemas/` or
`config/`. References inside a schema stay in that document; network and other
external references are rejected. Receipts resolve only in `reports/` or
`docs/product-truth/`. Paths and symlinks must remain within the repository and
allowed root. Runtime `model` names come from the explicit allowlist in
`product_truth_contract_sources.py`; authored import paths are forbidden. A
model-plus-schema definition also checks committed-schema parity. Full model
examples run Pydantic validation, including custom model validators. Projections
alone do not establish those runtime invariants. Request-bound comparisons
between separate objects and semantic answer quality are not established by
this documentation gate; the runtime submission validator remains authoritative.

The generator maintains the compatibility `consumes`/`produces` labels; do not
edit those generated copies. It writes no contract text into any `description`
(it did until 2026-10-09, behind a `Contract fields and examples (generated)`
marker). The validator compares the labels with the canonical renderer and
rejects drift.

Atlas uses the same authored metadata for contract headings, field tables and
separate JSON examples. For valid structured metadata, the drawer shows the
step's description once and omits the compatibility badges. Legacy
or metadata unusable by the display guard keeps the readable fallback; that fallback does not
waive repository validation. This display choice adds no new authored fields or
runtime contract.

All existing flows have been migrated. The checker requires metadata on every
existing and new step/branch: no legacy identity or node exemptions remain. It
reports checked flows, nodes, fields, examples and explicit missing bindings; the
compatibility legacy count is zero. The
retrieval-needs runtime marker pins its nine wire steps, required models and
complete request/output examples regardless of kind, source, status or
realization flags. Empty installed consumer stores do not acquire this
repository-specific requirement.

Before requesting review:

1. Search and extend the existing journey; preserve IDs, approvals and AC links.
2. Read each actual input/output source and trace mappings between boundaries.
   One conceptual phase does not imply a new serialized envelope.
3. Document exact paths, transport types, immediate-container requiredness and
   every known default. Use `applies` for separately validated object payloads.
4. Provide coherent input/output examples. Label full versus projection and
   observed versus reconstructed/illustrative; link observed JSON receipts.
5. Check all branches too. Distinguish rejected input, pending work, failed work
   and successful results with unresolved needs. Mark real design gaps explicitly.
6. Regenerate the compatibility labels and indexes, then run the existing
   validator. Review both the reported limits and the Atlas presentation. A pass
   is neither proof of semantic correctness nor AC approval.

## Validator run outcome

After validation reaches its reporting stage, `validate_product_truth.py` prints
one JSON object as its **last** stdout line (independent of logging). This report
uses a different vocabulary from the [per-example classifier outcome](../how-to/product-truth-schema-reference.md#classifier-eval--classifier-evalschemajson).
Early dependency failures and refused `--tighten` requests exit before emitting
the standard final JSON; they must not be read as successful validation.

The following is an illustrative **projection**, not a complete stdout payload.
See the [complete documentation schema](schemas/product-truth-validation-outcome.schema.json)
and [actual output constructor](scripts/product_truth_outcome.py) for all fields.
The schema is source-reviewed documentation, not automatic source-code parity.

```json
{"outcome": "checked-and-sound", "examined": 14, "unreadable": []}
```

| Field | Type | Notes |
|---|---|---|
| `outcome` | enum | `checked-and-sound` (every journey read and no problems found) \| `nothing-examined` (zero journeys were read) \| `degraded` (at least one journey exists but could not be read — see `unreadable`) \| `failed` (a real validation failure was found). |
| `examined` | int | Count of journeys the run actually read. |
| `unreadable` | string[] | Store-relative path of each journey file that could not be parsed (empty when nothing was unreadable). |
| `resolved_labels` | int | How many journey labels (one component each, plus tags) resolved against `docs/acceptance-criteria/index.yaml` and the tag shape (UXP-700e-3). `0` for a record with no labels. |
| `bounds` | object | One entry per declared size bound (`product_truth_bounds.BOUNDS`), keyed by bound name: `measured` (artifacts measured against it), `exceeded`, `holdouts` (artifacts still on a shape version older than the bound's), and `enforcement` — `warning-period` while any holdout remains, `blocking` once none does. Derived from the artifacts on every run; no date or flag changes it (UXP-700e-1, UXP-700e-1-ii). |

`--tighten BOUND` asks the validator to hold a bound as blocking. While any
artifact is still on an older shape version, the request is refused: the run
exits `1` and a `REFUSED:` line names the holdouts. Once none remains, the run
proceeds, and any artifact over the bound fails it.

The exit code is `0` for every outcome except `failed` — one malformed journey
file degrades the run and is named in `unreadable`, but does not stop it
(the project's fail-open convention; see
[Traceability guardrails, Hole 7](../explanation/traceability-guardrails.md#the-holes)
and
[GE-120](../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml)).
The per-file read that can produce `degraded` lives once in
`generate_product_truth.py::load_flows()`, shared by the generator and this
validator, so both callers skip-and-continue on the same file the same way.

## Related guidance

- [Authoring workflow](../how-to/authoring-product-truth-artifacts.md) — search, extend, register and review.
- [Artifact schema reference](../how-to/product-truth-schema-reference.md) — flow, mock data, mockup and classifier shapes.
- [Checker outcome meaning](../reference/product-truth-checker-outcomes.md) — what a validation result licenses you to conclude.
