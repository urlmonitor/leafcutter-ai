---
title: "The product-truth validator runs about four times faster, and a flow may carry a review-canvas diagram"
date: "2026-11-25"
time: "14:00"
type: manual
components:
  - ux_prototyping
summary: "product_truth_contracts.py called jsonschema.validate() once per flow node and once per contract definition, and every call re-ran check_schema on the flow schema. It now builds and schema-checks one validator per definition name and raises jsonschema.exceptions.best_match(...) exactly as jsonschema.validate() does, so the errors are unchanged. generate_product_truth.py reads YAML with libyaml's CSafeLoader when PyYAML has it, and with SafeLoader otherwise. On DIAGraph's store (31 flows, 420 nodes, 2283 ACs) the validator went from 15.9 s to 4.1 s and the generator --check from 19.9 s to 2.1 s, with byte-identical output. flow.schema.json also gains an optional, strict top-level diagram block (canvas, nodes, edges) for review canvases. DIAGraph had made both changes in its deployed copy, and every rebuild overwrote them, because the build copies the package's product-truth scripts and schemas over the target."
description: "UXP-300-5 and UXP-300-6 (new L3s under UXP-300). docs/product-truth/scripts/product_truth_contracts.py: cached _flow_schema_source(), cached _metadata_validator(name), and _validate_metadata(instance, name) replace the two jsonschema.validate(..., _metadata_schema(...)) calls. docs/product-truth/scripts/generate_product_truth.py: _load_yaml and write_ac_product_truth use yaml.load with Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader). docs/product-truth/schemas/flow.schema.json: optional diagram property between mock_data_ref and steps. The three files are byte-identical to DIAGraph's (roche-sandbox/dia-graph commit 0965ca48 and its schema), so a DIAGraph rebuild no longer rewrites them. New tests: unit_tests/product_truth/test_uxp_300_5.py (same errors as jsonschema.validate for invalid io_contracts and contract_definition instances, check_schema called once, CSafeLoader used and SafeLoader fallback, python object tags refused) and unit_tests/product_truth/test_uxp_300_6.py (a fixture store whose flow carries a diagram passes the real validator; an undeclared top-level key still fails and is named; diagram members are strict)."
commits:
breaking: false
---

## Entry

Checking the product-truth store on a large project took 16 to 25 seconds. Almost all of that
time went into checking the same schema again for every step. The check now runs once per kind
of step, and the generator uses the faster YAML reader when it is installed. The answers are
the same as before, and the run takes about 4 seconds.

Flows can now also carry an optional `diagram` block for review canvases: a canvas size, nodes
and edges. Every part of the block is checked strictly. Any other unknown key at the top of a
flow is still refused.
