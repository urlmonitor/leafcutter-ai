"""Finite, reviewed native-type reader registry, not executable source configuration."""

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
