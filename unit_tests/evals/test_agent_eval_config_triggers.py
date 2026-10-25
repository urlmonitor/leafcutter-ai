"""
MODULE: test_agent_eval_config_triggers
GOAL: Prove, against the REAL scripts/evals/agent_eval_config.json, that each agent's eval
    is triggered by its own files, and NOT by the sandbox's transitive contract
    dependencies. Commit 974fa757f (#1009) had added those dependencies: AC YAML, analysis
    docs, kernel/knowledge/integrations code, kernel schemas, config/ and reports/. As a
    result the informational agent-eval gate fired on most PRs. The owner decided on
    2026-10-06 to narrow the closures back to each agent's own surface.

    Deterministic: pure glob matching through eval_selector.compute_affected, with no git
    and no model.

Target: scripts/evals/agent_eval_config.json (via scripts/evals/eval_selector.py)
Ticket: TICKET-20261006-AgentEvalGateHonestAboutCredentials (AC-3)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALS_DIR = _REPO_ROOT / "scripts" / "evals"
sys.path.insert(0, str(_EVALS_DIR))
import eval_selector  # noqa: E402

_TRIGGERS = eval_selector.agent_triggers(eval_selector.load_config(_EVALS_DIR / "agent_eval_config.json"))
_ALL_AGENTS = ["flow-author", "mock-data-author", "pt-classifier", "restructuring-specialist", "test-runner", "test-writer"]

# One representative path per root that 974fa757f added and the owner decision removed.
_OUTSIDE_OWN_FILES = [
    "docs/acceptance-criteria/testing-quality/TQ-200-per-agent-eval-coverage/TQ-200b-3.yaml",
    "docs/analysis/2026-09-25-jev-test-triage-evaluation.md",
    # Nested on purpose: the removed `kernel/**/*.py`-style globs need a subdirectory.
    "kernel/adapters/claude_code/install.py",
    "knowledge/adapters/git_source.py",
    "integrations/retrieval_needs_probe.py",
    "kernel/schemas/leafcutter.decision_report.v1.schema.json",
    "config/ac_store_schema.json",
    "reports/BO-2200-implementation-audit-2026-08-10.md",
]

_OWN_FILES = {
    "templates/agents/flow-author.md": ["flow-author"],
    "docs/product-truth/evals/flow-author/eval.jsonl": ["flow-author"],
    "docs/product-truth/scripts/product_truth_contracts.py": ["flow-author"],
    "templates/agents/mock-data-author.md": ["mock-data-author"],
    "docs/product-truth/evals/mock-data-author/eval.jsonl": ["mock-data-author"],
    "templates/agents/pt-classifier.md": ["pt-classifier"],
    "templates/agents/restructuring-specialist.md": ["restructuring-specialist"],
    "scripts/evals/sets/restructuring-specialist.jsonl": ["restructuring-specialist"],
    "scripts/evals/artifact_dependencies.py": ["flow-author", "mock-data-author"],
    "scripts/evals/cli_envelope.py": _ALL_AGENTS,
    "scripts/evals/run_agent_eval.py": _ALL_AGENTS,
}


def test_the_config_still_declares_the_three_agents() -> None:
    """Guard: the assertions below are about these agents, so they must all be configured (six since TQ-200d-4 added test-runner).

    The name predates the fourth agent (restructuring-specialist, INF-800f-1). It is kept so
    the contract-shrinking guard and the test's history stay continuous; it checks every agent.
    """
    assert sorted(_TRIGGERS) == _ALL_AGENTS


def test_test_writer_is_declared_local_only_with_its_template_as_a_trigger() -> None:
    # covers: TQ-200d-1
    # angle: failure
    """Local-only: declared with its own template as a trigger, yet the selector CLI never reports it affected.

    compute_affected stays a pure glob match (so triggers still list test-writer above); the exclusion
    lives in the selector's CLI path.
    """
    config = eval_selector.load_config(_EVALS_DIR / "agent_eval_config.json")
    entry = config["agents"]["test-writer"]
    assert entry["local_only"] is True
    assert "templates/agents/test-writer.md" in entry["triggers"]
    for changed in ("templates/agents/test-writer.md", "scripts/evals/run_agent_eval.py"):
        out = subprocess.run(
            [sys.executable, str(_EVALS_DIR / "eval_selector.py"), "--changed-files", changed],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "test-writer" not in json.loads(out)["affected"]


@pytest.mark.parametrize("changed", _OUTSIDE_OWN_FILES)
def test_change_outside_the_agents_own_files_triggers_no_agent(changed: str) -> None:
    # covers: TQ-200b-3
    # angle: criterion
    """A PR that touches only this file affects no agent, so the gate fast-passes."""
    split = eval_selector.compute_affected([changed], _TRIGGERS)
    assert split["affected"] == [], f"{changed} still triggers {split['matched']}"


@pytest.mark.parametrize(("changed", "expected"), sorted(_OWN_FILES.items()))
def test_the_agents_own_files_still_trigger_them(changed: str, expected: list[str]) -> None:
    # covers: TQ-200b-3
    # angle: criterion
    """Each agent's own template, eval set and scorer still trigger it, and the harness triggers all."""
    split = eval_selector.compute_affected([changed], _TRIGGERS)
    assert split["affected"] == expected


@pytest.mark.parametrize("changed", ["templates/agents/test-runner.md", "scripts/evals/sets/test-runner.jsonl"])
def test_the_test_runners_own_files_trigger_only_it(changed: str) -> None:
    # covers: TQ-200d-4
    # angle: criterion
    """TQ-200d-4: the test runner's template and set trigger test-runner (a pure glob match; local_only is applied by the CLI)."""
    split = eval_selector.compute_affected([changed], _TRIGGERS)
    assert split["affected"] == ["test-runner"]
