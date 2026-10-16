"""Real fixture formatting is explicit, scoped and separate from correctness checks."""
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.background_worker.execution_boundary import ExecutorError
from scripts.background_worker.project_checks import run_checks
from ._background_worker_live_fixture import fixture, git


def test_explicit_formatter_fixes_whitespace_is_idempotent_and_tests_still_gate(tmp_path):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, _, original_tests = fixture(tmp_path)
    target = repo / "labels.py"
    target.write_text("def normalize_label(value):\n    return ' '.join(value.split())\n    \n")
    before = subprocess.run(["git", "diff", "--check"], cwd=repo, capture_output=True)
    assert before.returncode != 0
    checks = json.loads((repo / "worker-checks.json").read_text())["checks"]
    checker = (repo / "tools/format_labels.py").read_bytes()
    def check(workspace, argv, **kwargs):
        return subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=30)
    engine = SimpleNamespace(settings={"checks": checks},
                             store=SimpleNamespace(get_settings=lambda: {"enabled": True}),
                             local=SimpleNamespace(check=check))
    evidence = run_checks(engine, repo, timeout=60)
    assert evidence[0]["inspected"] == 1 and evidence[1]["inspected"] == 2
    assert not git(repo, "diff", "--check")
    formatted = target.read_bytes()
    run_checks(engine, repo, timeout=60)
    assert target.read_bytes() == formatted
    assert (repo / "tests/test_labels.py").read_text() == original_tests
    assert (repo / "tools/format_labels.py").read_bytes() == checker
    target.write_text("def normalize_label(value):\n    return 'wrong'\n    \n")
    with pytest.raises(ExecutorError) as caught:
        run_checks(engine, repo, timeout=60)
    assert caught.value.evidence["returncode"] != 0
    assert "failed" in caught.value.evidence["stdout"]
    assert not git(repo, "diff", "--check")


def test_formatter_rejects_missing_or_empty_target(tmp_path):
    # covers: ACD-1300g-2
    repo, _, _ = fixture(tmp_path)
    target = repo / "labels.py"
    for exists in (True, False):
        target.write_text("") if exists else target.unlink()
        result = subprocess.run([sys.executable, "tools/format_labels.py"], cwd=repo,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode != 0
        assert "leafcutter_check" not in result.stdout
