"""
MODULE: unit_tests/evals/test_tq200d1_review_isolation
GOAL: RED review-fix tests for TQ-200d-1: H-1 (scoring never touches a git repo named by the
    caller's GIT_* environment), H-6 (a live row exports everything the agent committed or
    wrote, with relative paths, and scores it) and M-2 (expected_field is honoured).
Target: scripts/evals/produced_tests_mode.py, produced_tests_scoring.py, produced_tests_runs.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import unit_tests.evals._tq200d1_helpers as h

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
EMPTY_PROJECT = h.REPO_ROOT / "scripts/evals/sets/test-writer/projects/empty-window"
EXPORTED = [
    "tests/conftest.py",
    "tests/fixtures/a/x.json",
    "tests/window_helpers.py",
    "unit_tests/x/test_y.py",
    "tests/test_buy_volume_window.py",
]
MAIN_TEST = '''import sys
from pathlib import Path

sys.path.insert(0, "@ROOT@/scripts")
for _p in (Path(__file__).resolve().parents[0], Path(__file__).resolve().parents[1]):
    sys.path.insert(0, str(_p))
import support_mod
from buy_volume_window import buy_volumes
from window_helpers import count_non_null


def test_every_row_in_the_window_has_non_negative_buy_volume(window):
    # covers: TQ-9302
    values = buy_volumes(window)
    processed = len(values)
    non_null = sum(1 for value in values if value is not None)
    assert processed == 3
    assert non_null == 3
    assert count_non_null(values) == support_mod.EXPECTED
    assert all(value >= 0 for value in values)
'''
CONFTEST = (
    "import json\nfrom pathlib import Path\n\nimport pytest\n\n\n@pytest.fixture\ndef window():\n"
    "    return json.loads((Path(__file__).parent / 'fixtures' / 'a' / 'x.json').read_text())\n"
)
NESTED = (
    'import sys\n\nsys.path.insert(0, "@ROOT@/scripts")\nimport support_mod\n\n\n'
    "def test_support_value():\n    # covers: TQ-9302\n    assert support_mod.EXPECTED == 3\n"
)
AGENT_FILES = {
    "tests/conftest.py": CONFTEST,
    "tests/fixtures/a/x.json": '[{"buy_volume": 4.0}, {"buy_volume": 0.0}, {"buy_volume": 2.5}]\n',
    "tests/window_helpers.py": "def count_non_null(values):\n    return sum(1 for v in values if v is not None)\n",
    "unit_tests/x/test_y.py": NESTED,
    "tests/test_buy_volume_window.py": MAIN_TEST,
}


def _clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo: Path, *args: str) -> None:
    subprocess.run([*GIT, "-C", str(repo), *args], check=True, capture_output=True, env=_clean_env())


def _dummy_repo(root: Path) -> Path:
    """A real repo with one commit and one staged-but-uncommitted file."""
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "a.txt")
    _git(root, "commit", "-q", "-m", "first")
    (root / "b.txt").write_text("staged\n", encoding="utf-8")
    _git(root, "add", "b.txt")
    return root


def _snapshot(repo: Path) -> dict[str, bytes]:
    """Bytes of the index, HEAD, refs, reflogs and the working files (objects are append-only noise)."""
    snap = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo)
        if path.is_file() and rel.parts[:2] != (".git", "objects"):
            snap[rel.as_posix()] = path.read_bytes()
    return snap


@pytest.mark.parametrize("mode", ["index_file", "git_dir_and_work_tree"])
def test_scoring_leaves_a_repo_named_by_git_env_untouched(tmp_path, monkeypatch, mode):
    # covers: TQ-200d-1-i
    # angle: failure
    # Catches: sandbox git / the wrong-version runner inherit GIT_INDEX_FILE, GIT_DIR or GIT_WORK_TREE
    # and stage, commit or reset in the caller's repository.
    repo = _dummy_repo(tmp_path / "dummy")
    before = _snapshot(repo)
    if mode == "index_file":
        monkeypatch.setenv("GIT_INDEX_FILE", str(repo / ".git" / "index"))
    else:
        monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(repo))
    row = h.real_row("refresh")
    record = h.score(row, h.gold_dir(row), tmp_path / "score")
    monkeypatch.undo()
    assert _snapshot(repo) == before, "scoring changed the caller's repository"
    assert record["score"]["passed"] is True, record["score"]


def _fake_agent(committed: bool):
    """An agent invoker that writes its test, helpers, conftest and fixtures, and optionally commits."""

    def invoke(*args, **kwargs):
        box = Path(kwargs.get("sandbox") or args[4])
        for rel, text in AGENT_FILES.items():
            target = box / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text.replace("@ROOT@", box.as_posix()), encoding="utf-8")
        if committed:
            _git(box, "add", "-A")
            _git(box, "commit", "-q", "-m", "agent work")
        return "# Report\nThe check counts the processed rows and the non-NULL values.\n"

    return invoke


@pytest.mark.parametrize("committed", [True, False], ids=["committed", "uncommitted"])
def test_live_row_exports_every_changed_file_and_scores_the_produced_test(tmp_path, monkeypatch, committed):
    # covers: TQ-200d-1
    # angle: reachability
    # Catches: export reads only uncommitted `test_*.py` files by basename, so a committing agent exports
    # nothing and helpers, conftest, fixtures and nested tests never reach the scoring sandbox.
    mode, runs = h.module("produced_tests_mode"), h.module("produced_tests_runs")
    harness = h.module("run_agent_eval")
    repo = tmp_path / "repo"
    shutil.copytree(EMPTY_PROJECT, repo / "proj", ignore=shutil.ignore_patterns("__pycache__"))
    (repo / "proj" / "scripts").mkdir()
    (repo / "proj" / "scripts" / "support_mod.py").write_text("EXPECTED = 3\n", encoding="utf-8")
    specs = h.real_row("empty")["expected"]["assertions"]
    row = {"id": "live-empty", "input": "write the check", "expected": {"negative": False, "fixture": "proj", "assertions": specs}}
    cfg = {"expected_field": "expected", "model": "m", "tools": "Read", "support_scripts": []}
    monkeypatch.setattr(harness, "invoke_agent_writer", _fake_agent(committed))
    seen = []
    real_pytest = runs.run_pytest

    def spy(ctx, names):
        seen.append({rel: (ctx.sandbox / rel).is_file() for rel in EXPORTED})
        return real_pytest(ctx, names)

    monkeypatch.setattr(runs, "run_pytest", spy)
    record = mode.score_one(row, cfg, "root={{config.output_root}}", repo, harness, score_gold=False, timeout=60)
    assert "error" not in record, record.get("error")
    assert seen, "no produced test was ever run"
    assert all(seen[0].values()), f"files missing from the scoring sandbox: {seen[0]}"
    by_kind = {a["kind"]: a for a in record["score"]["assertions"]}
    assert by_kind["counts_rows_and_non_null"]["passed"] is True, by_kind
    assert by_kind["produced_test_green"]["passed"] is True, by_kind["produced_test_green"]
    assert record["score"]["passed"] is True, record["score"]


def test_score_one_honours_expected_field_of_the_agent_config():
    # covers: TQ-200d-1
    # angle: boundary
    # Catches: score_row reads a hard-coded row["expected"] although agent_cfg names another field.
    mode, harness = h.module("produced_tests_mode"), h.module("run_agent_eval")
    row = h.real_row("empty")
    renamed = {"id": row["id"], "input": row["input"], "wanted": row["expected"]}
    record = mode.score_one(renamed, {"expected_field": "wanted"}, "", h.REPO_ROOT, harness, score_gold=True, timeout=60)
    assert "error" not in record, record.get("error")
    assert record["score"]["passed"] is True, record["score"]
    assert len(record["score"]["assertions"]) == len(row["expected"]["assertions"])
