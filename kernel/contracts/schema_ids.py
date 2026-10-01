"""
MODULE: kernel.contracts.schema_ids
GOAL: The stable protocol ids of the registered payload schemas.
BUSINESS CONTEXT: Named payloads must have registered schemas (Rev 3 section 7.11); capability
    descriptors, requests and submissions refer to them only by these ids.
ARCHITECTURE: Leaf module with no imports so registry and contract models can validate schema
    ids without importing the payload models (which would create import cycles).
"""

GOAL_REQUEST = "leafcutter.goal_request.v1"
DECISION_REQUEST = "leafcutter.decision_request.v1"
DECISION_REPORT = "leafcutter.decision_report.v1"
RESEARCH_REQUEST = "leafcutter.research_request.v1"
RETRIEVAL_REQUEST = "leafcutter.retrieval_request.v1"
EVIDENCE_BUNDLE = "leafcutter.evidence_bundle.v1"
OPTIONS_REQUEST = "leafcutter.options_request.v1"
OPTIONS = "leafcutter.options.v1"
SYNTHESIS_REQUEST = "leafcutter.synthesis_request.v1"
FINDINGS = "leafcutter.findings.v1"
HUMAN_QUESTION_REQUEST = "leafcutter.human_question_request.v1"
HUMAN_ANSWER = "leafcutter.human_answer.v1"

KNOWN_SCHEMA_IDS: frozenset[str] = frozenset({
    GOAL_REQUEST, DECISION_REQUEST, DECISION_REPORT, RESEARCH_REQUEST, RETRIEVAL_REQUEST,
    EVIDENCE_BUNDLE, OPTIONS_REQUEST, OPTIONS, SYNTHESIS_REQUEST, FINDINGS,
    HUMAN_QUESTION_REQUEST, HUMAN_ANSWER,
})

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Split from schema_catalog to break the models-import cycle;
#   a test asserts the catalog keys equal KNOWN_SCHEMA_IDS. (#KernelBootstrapV0/P1)
# ====================================================================
