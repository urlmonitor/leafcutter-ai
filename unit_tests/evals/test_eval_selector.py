"""
MODULE: test_eval_selector
GOAL: TDD test-first proof for the eval trigger-selector + freshness core
    specified by TQ-200b-3 (affected-eval selection from a change) and
    TQ-200b-4 (missing/stale eval result is a HARD FAILURE, never a skip).

    These tests are deterministic and require NO model / LLM call: they exercise
    the selector's affected-set computation and its freshness gate against
    fixtures on disk (a fake repo + fake eval config + fake result files).

Target module: scripts/evals/eval_selector.py
Covers:
  - affected computation: agent-specific trigger vs shared harness vs unrelated.
  - freshness: matching shas => fresh; changed / added / removed trigger => stale;
    no result => missing.
  - --check exit codes: all-fresh => 0; affected + missing => 3; affected + stale
    => 3; unaffected agents never fail and are reported as unaffected/skipped.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALS_DIR = _REPO_ROOT / "scripts" / "evals"
_SELECTOR = _EVALS_DIR / "eval_selector.py"

# Import the module under test for its pure helpers (used to build the exact
# trigger_shas a result file must record to be FRESH). If eval_selector.py does
# not exist yet the ImportError propagates and every test here is RED — the
# valid test-first state before implementation.
sys.path.insert(0, str(_EVALS_DIR))
import eval_selector  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — a self-contained fake repo with a fake eval config + trigger files
# ---------------------------------------------------------------------------
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """Build a fake repo root with two agents whose triggers include an
    agent-specific template, the shared harness, and a recursive glob dir."""
    root = tmp_path / "repo"
    # Agent-specific templates.
    _write(root / "templates/agents/agent-a.md", "prompt A v1\n")
    _write(root / "templates/agents/agent-b.md", "prompt B v1\n")
    # Shared harness + config (a change here affects ALL agents).
    _write(root / "scripts/evals/run_agent_eval.py", "# harness v1\n")
    # Recursive glob directory contents.
    _write(root / "docs/shared/one.md", "shared one\n")
    _write(root / "docs/shared/sub/two.md", "shared two\n")
    # Unrelated file.
    _write(root / "README.md", "readme\n")

    config = {
        "agents": {
            "agent-a": {
                "triggers": [
                    "templates/agents/agent-a.md",
                    "docs/shared/**",
                    "scripts/evals/run_agent_eval.py",
                    "scripts/evals/agent_eval_config.json",
                ]
            },
            "agent-b": {
                "triggers": [
                    "templates/agents/agent-b.md",
                    "docs/shared/**",
                    "scripts/evals/run_agent_eval.py",
                    "scripts/evals/agent_eval_config.json",
                ]
            },
        }
    }
    _write(root / "scripts/evals/agent_eval_config.json", json.dumps(config, indent=2))
    return root


def _config_path(root: Path) -> Path:
    return root / "scripts/evals/agent_eval_config.json"


def _results_dir(root: Path) -> Path:
    return root / "scripts/evals/results"


def _run_selector(root: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(_SELECTOR),
        "--repo-root",
        str(root),
        "--config",
        str(_config_path(root)),
        "--results-dir",
        str(_results_dir(root)),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def _write_fresh_result(root: Path, agent: str) -> None:
    """Write results/<agent>.json whose trigger_shas exactly match the current
    resolved trigger files for that agent (so it is FRESH by construction)."""
    config = eval_selector.load_config(_config_path(root))
    triggers = eval_selector.agent_triggers(config)[agent]
    shas = eval_selector.resolve_trigger_shas(root, triggers)
    result_path = _results_dir(root) / f"{agent}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({"agent": agent, "trigger_shas": shas}, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# affected computation (TQ-200b-3)
# ---------------------------------------------------------------------------
def test_affected_agent_specific_template(fake_repo: Path) -> None:
    proc = _run_selector(fake_repo, "--changed-files", "templates/agents/agent-a.md")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["affected"] == ["agent-a"]
    assert out["unaffected"] == ["agent-b"]
    assert out["matched"]["agent-a"] == ["templates/agents/agent-a.md"]


def test_affected_shared_harness_marks_all(fake_repo: Path) -> None:
    proc = _run_selector(fake_repo, "--changed-files", "scripts/evals/run_agent_eval.py")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["affected"] == ["agent-a", "agent-b"]
    assert out["unaffected"] == []


def test_affected_unrelated_marks_none(fake_repo: Path) -> None:
    proc = _run_selector(fake_repo, "--changed-files", "README.md")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["affected"] == []
    assert out["unaffected"] == ["agent-a", "agent-b"]
    assert out["matched"] == {}


def test_affected_recursive_glob_dir(fake_repo: Path) -> None:
    proc = _run_selector(fake_repo, "--changed-files", "docs/shared/sub/two.md")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["affected"] == ["agent-a", "agent-b"]
    assert out["matched"]["agent-a"] == ["docs/shared/**"]


# ---------------------------------------------------------------------------
# freshness pure logic (TQ-200b-4)
# ---------------------------------------------------------------------------
def test_freshness_matching_is_fresh() -> None:
    shas = {"a": "1", "b": "2"}
    assert eval_selector.freshness(shas, dict(shas)) == "fresh"


def test_freshness_missing_result_is_missing() -> None:
    assert eval_selector.freshness({"a": "1"}, None) == "missing"


def test_freshness_changed_sha_is_stale() -> None:
    assert eval_selector.freshness({"a": "1"}, {"a": "9"}) == "stale"


def test_freshness_added_file_is_stale() -> None:
    # current has an extra resolved file the recorded result never saw.
    assert eval_selector.freshness({"a": "1", "b": "2"}, {"a": "1"}) == "stale"


def test_freshness_removed_file_is_stale() -> None:
    # recorded referenced a file that no longer resolves.
    assert eval_selector.freshness({"a": "1"}, {"a": "1", "b": "2"}) == "stale"


# ---------------------------------------------------------------------------
# --check exit codes (TQ-200b-4)
# ---------------------------------------------------------------------------
def test_check_all_fresh_exit0(fake_repo: Path) -> None:
    _write_fresh_result(fake_repo, "agent-a")
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "templates/agents/agent-a.md"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "fresh"


def test_check_missing_result_exit3(fake_repo: Path) -> None:
    # agent-a affected, NO result file at all -> hard failure, never a pass.
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "templates/agents/agent-a.md"
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "missing"


def test_check_stale_changed_trigger_exit3(fake_repo: Path) -> None:
    _write_fresh_result(fake_repo, "agent-a")
    # Mutate a trigger file AFTER recording the result -> stale.
    (fake_repo / "templates/agents/agent-a.md").write_text("prompt A v2\n", encoding="utf-8")
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "templates/agents/agent-a.md"
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "stale"


def test_check_stale_added_file_in_glob_exit3(fake_repo: Path) -> None:
    _write_fresh_result(fake_repo, "agent-a")
    # Add a NEW file inside the recursive glob dir after recording -> stale.
    _write(fake_repo / "docs/shared/three.md", "shared three\n")
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "docs/shared/three.md"
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "stale"


def test_check_stale_removed_file_in_glob_exit3(fake_repo: Path) -> None:
    _write_fresh_result(fake_repo, "agent-a")
    # Remove a file the result recorded -> stale.
    (fake_repo / "docs/shared/sub/two.md").unlink()
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "docs/shared/sub/two.md"
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "stale"


def test_check_multiple_offenders_all_reported(fake_repo: Path) -> None:
    # Shared harness change affects BOTH agents; neither has a result -> both
    # missing, both reported (not just the first), exit 3.
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "scripts/evals/run_agent_eval.py"
    )
    assert proc.returncode == 3, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "missing"
    assert out["status"]["agent-b"] == "missing"


def test_check_unaffected_never_fails(fake_repo: Path) -> None:
    # agent-a affected + fresh; agent-b unaffected and has NO result file.
    # The unaffected agent's missing result must NOT cause failure.
    _write_fresh_result(fake_repo, "agent-a")
    proc = _run_selector(
        fake_repo, "--check", "--changed-files", "templates/agents/agent-a.md"
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout)
    assert out["status"]["agent-a"] == "fresh"
    # agent-b is reported as unaffected/skipped, not failed.
    assert "agent-b" in out["unaffected"]
    assert out["status"].get("agent-b") in (None, "unaffected", "skipped")


# ---------------------------------------------------------------------------
# --diff-base git path (typed try/except around the git call)
# ---------------------------------------------------------------------------
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def test_diff_base_detects_changed_agent(fake_repo: Path) -> None:
    _git(fake_repo, "init", "-q")
    _git(fake_repo, "config", "user.email", "t@t.t")
    _git(fake_repo, "config", "user.name", "t")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "base")
    # Modify only agent-a's template (unstaged working-tree change).
    (fake_repo / "templates/agents/agent-a.md").write_text("prompt A v2\n", encoding="utf-8")
    proc = _run_selector(fake_repo, "--diff-base", "HEAD")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["affected"] == ["agent-a"]


def test_diff_base_bad_ref_is_exit2(fake_repo: Path) -> None:
    _git(fake_repo, "init", "-q")
    _git(fake_repo, "config", "user.email", "t@t.t")
    _git(fake_repo, "config", "user.name", "t")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "base")
    proc = _run_selector(fake_repo, "--diff-base", "no-such-ref-xyz")
    assert proc.returncode == 2, proc.stdout + proc.stderr
