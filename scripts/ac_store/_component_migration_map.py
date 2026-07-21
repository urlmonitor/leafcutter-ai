"""
_component_migration_map.py — Side-effect-free kebab-to-underscore component id mapping.

MODULE: generate_ticket_from_ac (supporting data module)
GOAL: Expose the canonical kebab→underscore MIGRATION_MAP dict without any
      logging configuration, external imports, or other module-level side effects.
BUSINESS CONTEXT: The ticket generator (generate_ticket_from_ac.py) normalises
      ``components`` LIST values in AC YAML to their components.json graph ids.
      This module holds the static mapping table so the generator can import it
      without triggering the logging.basicConfig side effect present in the
      sibling migrate_component_vocab.py script.
ARCHITECTURE: Plain data module — no imports, no logging, no side effects.
      Loaded at generator import time via importlib.util.spec_from_file_location
      so that a SyntaxError or load failure degrades gracefully (fallback to {})
      rather than making the generator un-importable.

DECISION HISTORY:
    TKT-500f-18 (2026-07-21): Created to replace the exec-based load of
    migrate_component_vocab.py in _load_migration_map(). The sibling script
    calls logging.basicConfig(level=INFO) at module level (line 51), which
    reconfigures the root logger as a side effect of importing the generator.
    This module contains only the dict literal — no side effects.
"""

MIGRATION_MAP: dict[str, str] = {
    "build-pipeline": "build_pipeline",
    "ac-store": "ac_store",
    "testing-quality": "testing_quality",
    "knowledge-management": "knowledge_management",
    "guardrail-engine": "commit_guardian",
    "ticket-creation": "ticket_creation_pipeline",
    "finalize": "finalize",
    "build-orchestration": "build_orchestration",
    "infrastructure": "infrastructure",
    "ux-prototyping": "ux_prototyping",
    "persona-management": "persona_management",
    "stakeholder-delivery": "stakeholder_delivery",
    "ac-driven-dev": "ac_driven_dev",
}
