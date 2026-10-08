"""Disposable on-disk stores for contract CLI, CI and pre-commit seam checks.

GOAL: Exercise real producers and consumers without modifying the user's checkout.
BUSINESS CONTEXT: A helper-only pass cannot prove an automatic gate is effective.
ARCHITECTURE: Copy real scripts/schemas and serialize a tiny independent flow fixture.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TRUTH = ROOT / "docs/product-truth"
FIXTURE = ROOT / "tests/fixtures/product_truth_contracts/request.json"
HOOK_ID = "check-product-truth-validate"


def run(argv, root, timeout=15, env=None, input_text=None):
    """Run a real entry point; preserve output for assertion diagnostics."""
    process_env = os.environ.copy()
    process_env["PYTHONDONTWRITEBYTECODE"] = "1"
    process_env["PYTHONUTF8"] = "1"
    process_env["PYTHONIOENCODING"] = "utf-8"
    process_env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + process_env["PATH"]
    if env:
        process_env.update(env)
    return subprocess.run(
        argv, cwd=root, env=process_env, input=input_text,
        text=True, encoding="utf-8", capture_output=True, timeout=timeout,
    )


def assert_success(result):
    """Raise with the complete subprocess failure, never hide setup drift."""
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)


def write_json(path, value):
    """Serialize real JSON bytes in a disposable repository."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_store(root):
    """Generate a self-consistent store through the real canonical generator."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pt = root / "docs/product-truth"
    shutil.copytree(TRUTH / "scripts", pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TRUTH / "schemas", pt / "schemas")
    for folder in ("flows/fixture", "mock-data", "mockups", "classifier"):
        (pt / folder).mkdir(parents=True, exist_ok=True)
    (root / "docs/acceptance-criteria").mkdir(parents=True)
    (pt / "classifier/eval.jsonl").write_text("", encoding="utf-8")
    write_json(root / "config/request.schema.json", data["schema"])
    write_json(pt / "flows/fixture/query.flow.json", data["flow"])
    write_json(pt / "index.json", data["index"])
    assert_success(run(
        [sys.executable, str(pt / "scripts/generate_product_truth.py"), "--quiet"], root
    ))
    return pt


def canonical_hook():
    """Read the actual canonical registration, not a hand-written replacement."""
    path = ROOT / "templates/scripts/commit_guardian/commit_guardian.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return next(h for h in manifest["hooks_manifest"]["hooks"] if h["id"] == HOOK_ID)


def prepare_git_hook(root):
    """Install only the real local hook into a throwaway Git fixture, with no commit."""
    hook = canonical_hook()
    deployed = root / ".leafcutter/scripts/commit_guardian"
    deployed.mkdir(parents=True)
    for filename in ("run_hook.py", "check_outcome.py"):
        shutil.copy2(ROOT / "templates/scripts/commit_guardian" / filename, deployed / filename)
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_precommit import _render_hook_yaml, _resolve_template_vars
    resolved = _resolve_template_vars([hook], {"output_root": ".leafcutter"})[0]
    rendered = "repos:\n  - repo: local\n    hooks:\n" + _render_hook_yaml(resolved) + "\n"
    actual = yaml.safe_load(rendered)["repos"][0]["hooks"][0]
    if actual["files"] != hook["files"]:
        raise AssertionError("Hook rendering changed the canonical trigger")
    (root / ".pre-commit-config.yaml").write_text(rendered, encoding="utf-8")
    assert_success(run(["git", "init", "--quiet"], root))
    assert_success(run(["git", "add", "--all"], root))
    tree = run(["git", "write-tree"], root)
    assert_success(tree)
    identity = {
        "GIT_AUTHOR_NAME": "Contract fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Contract fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    commit = run(["git", "commit-tree", tree.stdout.strip()], root, env=identity, input_text="Fixture\n")
    assert_success(commit)
    assert_success(run(["git", "update-ref", "HEAD", commit.stdout.strip()], root))


def all_bytes(root):
    """Read-only checks compare exact file bytes, excluding nothing."""
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
