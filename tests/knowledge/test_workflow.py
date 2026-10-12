"""
MODULE: test_workflow
GOAL: The merge workflow calls the trusted standalone writer with immutable input.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from pathlib import Path

import yaml


def test_merge_workflow_is_canonical_secret_gated_and_uses_standalone_sync():
    # covers: KM-400e-5
    # angle: reachability
    """Test merge workflow is canonical secret gated and uses standalone sync."""
    path = Path(__file__).resolve().parents[2] / ".github/workflows/knowledge-sync.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["on"]["push"]["branches"] == ["main"]
    job = workflow["jobs"]["sync"]
    assert "KNOWLEDGE_SYNC_ENABLED" in job["if"]
    assert job["concurrency"]["cancel-in-progress"] == "false"
    body = "\n".join(step.get("run", "") for step in job["steps"])
    assert "python -m knowledge sync" in body
    assert '"$SOURCE_REVISION"' in body
    assert "merge-base --is-ancestor" in body
    assert "LEAFCUTTER_NEO4J_WRITER_PASSWORD" in job["env"]
    assert "python -m kernel" not in body


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
