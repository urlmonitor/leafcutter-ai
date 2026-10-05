"""Canonical, plain-text contract presentation shared by generator and checker.

GOAL: Keep Atlas badges and readable JSON derived from checked contract metadata.
BUSINESS CONTEXT: A correct hidden schema must not leave misleading visible text.
ARCHITECTURE: Pure rendering; existing authored narrative precedes a fixed generated marker.
"""
import json

MODEL_SOURCES = {
    "decision_request": "kernel/contracts/payloads.py",
    "decision_report": "kernel/contracts/payloads.py",
    "research_request": "kernel/contracts/payloads.py",
    "options_request": "kernel/contracts/payloads.py",
    "options": "kernel/contracts/payloads.py",
    "synthesis_request": "kernel/contracts/payloads.py",
    "findings": "kernel/contracts/payloads.py",
    "human_answer": "kernel/contracts/payloads.py",
    "goal_request": "kernel/contracts/payloads.py",
    "evidence_bundle": "kernel/contracts/evidence.py",
    "query_descriptor": "knowledge/query_models.py", "query_candidate": "knowledge/query_models.py",
    "jev_batch": "kernel/providers/base.py", "jev_result": "kernel/providers/base.py",
    "choice_answer": "kernel/providers/base.py",
    "knowledge_request": "knowledge/contracts.py", "knowledge_result": "knowledge/contracts.py",
    "projection_snapshot": "knowledge/contracts.py", "answer_requirements": "knowledge/answer_models.py",
    "answer_assessment": "knowledge/answer_models.py",
    "decision": "kernel/contracts/decision.py", "provider_answer": "kernel/contracts/decision.py",
    "option": "kernel/contracts/decision.py", "criterion": "kernel/contracts/decision.py",
    "option_ranking": "kernel/contracts/decision.py", "evidence": "kernel/contracts/evidence.py",
    "enriched_context": "kernel/contracts/context.py", "human_question": "kernel/contracts/interaction.py",
    "decision_record": "kernel/memory/models.py", "decision_index_entry": "kernel/memory/index.py",
    "decision_query": "kernel/memory/port.py",
    "retrieval_needs_request": "kernel/contracts/retrieval_needs.py",
    "retrieval_needs_output": "kernel/contracts/retrieval_needs.py",
    "task_input": "kernel/contracts/task.py", "scope": "kernel/contracts/task.py", "actor": "kernel/contracts/task.py",
    "host_work_request": "kernel/contracts/interaction.py", "interaction_submission": "kernel/contracts/interaction.py",
    "submission_record": "kernel/persistence/base.py", "capability_invocation": "kernel/contracts/work.py",
    "capability_result": "kernel/contracts/capability.py", "run_envelope": "kernel/contracts/run.py",
    "work_item": "kernel/contracts/work.py",
}

MARKER = "\n\nContract fields and examples (generated)\n"


def render_contract_io(flow, node):
    """Return consumes labels, produces labels, and canonical generated human detail."""
    io = node["io_contracts"]
    if "not_applicable" in io:
        return [], [], "No JSON handoff: " + io["not_applicable"]
    labels = {}
    lines = []
    for direction in ("consumes", "produces"):
        labels[direction] = []
        lines.append(direction.capitalize() + ":")
        for binding in io.get(direction, []):
            definition = flow.get("contract_definitions", {}).get(binding["contract"], {})
            name = definition.get("model", binding["contract"])
            authority = definition.get("authority", "runtime" if "model" in definition else "schema_only")
            if authority in ("source_reviewed", "illustrative_design"):
                lines.append("  " + ("SOURCE-REVIEWED DOCUMENTATION" if authority == "source_reviewed" else "ILLUSTRATIVE DESIGN") + ": " + definition["note"])

            for field in binding["fields"]:
                state = "each present item/value" if field["path"].endswith("/*") else "required" if field["required"] else "optional"
                if "default" in field:
                    state += "; default " + json.dumps(field["default"], ensure_ascii=False)
                if "applies" in field:
                    state += "; applies " + field["applies"] + " schema"
                label = name + field["path"] + ": " + "|".join(field["types"]) + " (" + state + ")"
                labels[direction].append(label)
                lines.append("  " + label)
            link = definition.get("schema")
            if link:
                lines.append("  Schema: [" + binding["contract"] + "](" + link + ")")
            elif "model" in definition:
                lines.append("  Runtime contract: [" + definition["model"] + "](" + MODEL_SOURCES[definition["model"]] + ")")
        if not labels[direction]:
            lines.append("  No checked JSON binding documented in this direction.")
    for gap in io.get("missing_bindings", []):
        lines.extend(["", "PROPOSED - missing JSON binding (" + gap["direction"] + "): " + gap["name"],
                      gap["reason"], "Design source: [" + gap["source"] + "](" + gap["source"] + ")"])
    for example in io.get("examples", []):
        qualifier = "complete payload" if example["mode"] == "full" else "selected fields only; full required/defaulted fields in linked contract"
        lines.extend(["", example["label"] + " — " + example["contract"] + "; " + example["origin"] + "; " + qualifier + ":",
                      json.dumps(example["value"], ensure_ascii=False, indent=2)])
        if "source" in example:
            source = example["source"]
            lines.append("Receipt: [" + source["path"] + "](" + source["path"] + ")" + source["pointer"])
    return labels["consumes"], labels["produces"], "\n".join(lines)


def apply_contract_presentation(flow):
    """Regenerate only documented nodes; keep authored prose before the exact marker."""
    for node in flow.get("steps", []) + flow.get("branches", []):
        if "io_contracts" not in node:
            continue
        consumes, produces, detail = render_contract_io(flow, node)
        node["consumes"], node["produces"] = consumes, produces
        node["human"] = node.get("human", "").split(MARKER, 1)[0].rstrip() + MARKER + detail
