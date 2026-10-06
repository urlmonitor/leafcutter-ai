"""MODULE: knowledge.native_types.registry
GOAL: Declare the reviewed native readers, labels and compact role descriptions.
BUSINESS CONTEXT: Repository artifacts retain canonical typed ownership.
ARCHITECTURE: Package-owned adapters treat source checkouts exclusively as data.
"""

MODULES = {
    "AcceptanceCriterion": "acceptance_criterion",
    "ADR": "adr",
    "Component": "component",
    "Agent": "agent",
    "Skill": "skill",
    "Ticket": "ticket",
    "Document": "document",
    "RoadmapPhase": "roadmap_phase",
    "GlossaryTerm": "glossary_term",
    "Flow": "flow",
    "Mockup": "mockup",
    "MockData": "mock_data",
    "ChangelogEntry": "changelog_entry",
    "Capability": "capability",
    "Decision": "decision",
}

LABELS = {kind: "AC" if kind == "AcceptanceCriterion" else kind for kind in MODULES}
LABELS.update({"SourceFile": "SourceFile", "Test": "Test", "Lesson": "Lesson"})

# Reviewed package descriptions explain reader roles, never artifact contents.
ROLE_DESCRIPTIONS = {
    "AcceptanceCriterion": "A testable requirement describing an accepted observable outcome.",
    "ADR": "An architecture decision record describing a recorded design choice.",
    "Decision": "An approved canonical decision with recorded provenance.",
    "Flow": "A declared product journey and its ordered interaction steps.",
    "Ticket": "A tracked unit of implementation work.",
    "GlossaryTerm": "An authored definition of project terminology.",
    "Component": "A registered component of the product architecture.",
    "Agent": "A declared agent role and its operating contract.",
    "Skill": "A reusable workflow with its own instructions and resources.",
    "Document": "An authored project document.",
    "RoadmapPhase": "A planned stage of product delivery.",
    "Mockup": "A visual design reference for an intended interface.",
    "MockData": "A declared synthetic data example.",
    "ChangelogEntry": "A recorded change to a released package.",
    "Capability": "A registered executable capability and its contract.",
    "SourceFile": "An implementation source file.",
    "Test": "An executable check of observable behavior.",
    "Lesson": "A recorded reusable learning.",
}


def collect(root, *, kinds=None, validated_acs=None):
    """Load only trusted package readers, treating the checkout as source data."""
    import importlib

    records = []
    seen = set()
    for kind, module in MODULES.items():
        if kinds is not None and kind not in kinds:
            continue
        reader = importlib.import_module("knowledge.native_types." + module)
        extracted = (
            reader.extract(root, validated=validated_acs)
            if kind == "AcceptanceCriterion"
            else reader.extract(root)
        )
        for record in extracted:
            identity = (kind, record.native_id)
            if record.kind != kind or identity in seen:
                raise ValueError(f"duplicate or mismatched native identity: {identity}")
            seen.add(identity)
            records.append(record)
    return records

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
