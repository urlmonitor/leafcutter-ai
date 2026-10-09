"""Canonical compatibility labels derived from checked contract metadata.

GOAL: Keep each node's consumes/produces labels derived from its io_contracts,
    shared by the generator (writer) and the checker (drift gate).
BUSINESS CONTEXT: A correct hidden schema must not leave misleading visible
    labels. Contract detail is NOT rendered into any text field: a step's
    `description` is one authored sentence of what happens, and Atlas renders
    fields, examples, authority and missing bindings from io_contracts itself
    (dec-7b1dcfd47f85cf0a).
ARCHITECTURE: Pure rendering; no I/O.
"""
import json


def render_contract_labels(flow, node):
    """Return the (consumes, produces) compatibility labels for one documented node."""
    io = node["io_contracts"]
    labels = {"consumes": [], "produces": []}
    if "not_applicable" in io:
        return labels["consumes"], labels["produces"]
    for direction in labels:
        for binding in io.get(direction, []):
            definition = flow.get("contract_definitions", {}).get(binding["contract"], {})
            name = definition.get("model", binding["contract"])
            for field in binding["fields"]:
                state = "each present item/value" if field["path"].endswith("/*") else "required" if field["required"] else "optional"
                if "default" in field:
                    state += "; default " + json.dumps(field["default"], ensure_ascii=False)
                if "applies" in field:
                    state += "; applies " + field["applies"] + " schema"
                labels[direction].append(name + field["path"] + ": " + "|".join(field["types"]) + " (" + state + ")")
    return labels["consumes"], labels["produces"]


def apply_contract_presentation(flow):
    """Regenerate the compatibility labels of every documented node; touch no text field."""
    for node in flow.get("steps", []) + flow.get("branches", []):
        if "io_contracts" in node:
            node["consumes"], node["produces"] = render_contract_labels(flow, node)


# DECISION HISTORY
# ================================================================================
# - 2026-10-09 [python-coder]: Stopped appending a generated "Contract fields and
#   examples" section behind a marker to the step text; render_contract_io became
#   render_contract_labels and returns labels only. The model-source link table went
#   with the text it fed. Atlas renders contract detail from io_contracts.
#   (TICKET-20261009-ProductTruthDescriptionActorKind)
