"""MODULE: projection
GOAL: Hold canonical-to-Neo4j projection adapters.
BUSINESS CONTEXT: Git remains authoritative and the graph is rebuildable.
ARCHITECTURE: Independent of the kernel and its runtime state.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Isolate ingestion ownership. (#TICKET-KM-400a-1)
"""
