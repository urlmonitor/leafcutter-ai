"""
MODULE: unit_tests/workflows/_inf700a5_fixtures.py
GOAL: Shared real-artifact fixtures for the INF-700a-5 family's RED test
    baseline (INF-700a-5, INF-700a-5-i, INF-700a-5-ii, INF-700a-5-iii).

WHY THIS EXISTS: every AC in this family is about durability ACROSS a real
    git publication boundary — "written" only counts once a write reaches a
    MERGED tree, and a working directory that is later removed must not be
    the only place a learning ever existed. A test that fakes the git layer
    (a plain directory standing in for "the merged tree", an in-memory flag
    standing in for "published") can pass on exactly the implementation
    these ACs reject. So this fixture module drives REAL `git` subprocesses
    — a real install repo, a real working-directory clone on its own
    branch, a real local-path `git pull` to merge — rather than mocking any
    of it (repo convention: "Real-artifact behavioral spot-check before
    declaring done", project CLAUDE.md).

    Sink records are produced by the REAL `scripts/knowledge/emit_knowledge.py`
    CLI (Fixture Authenticity Rule, test-writer §2h.2) rather than
    hand-typed JSON lines, using the real declared vocabulary at
    config/entry_kind_vocabulary.json.

NOT YET IMPLEMENTED (this is the point of a RED baseline):
    `scripts/knowledge/completion_routing.py` does not exist. Every test
    that uses `load_completion_routing()` fails with FileNotFoundError until
    python-coder creates it. The contract this fixture (and the test files
    built on it) establishes for that module:

        stage_completion(*, sink_path, state_path, working_dir, dry_run=False) -> dict
            Wraps harvest_learnings.harvest(), resolving each record's
            `destination` field to an ABSOLUTE path under `working_dir`
            (closing the "no explicit working-directory parameter" gap
            INF-700a-5's it_requirements name) and writing the learning text
            there. Deliberately does NOT persist anything to `state_path`
            yet — confirmation is a separate, later call (see
            confirm_routed below), because a mark written at routing time
            would be true before the driver's own publication has actually
            reached a merged tree (INF-700a-5's bookkeeping-must-not-
            outlive-publication clause). Returns:
                {
                  "read": int, "written": int, "unwritten": int,
                  "case": "completed" | "could_not_complete" | "did_not_run",
                  "manifest": [str, ...],     # absolute working_dir paths written
                  "record_ids": [str, ...],   # hashes to pass to confirm_routed
                }

        confirm_routed(*, state_path, record_ids) -> None
            Persists record_ids as processed. Called by the driver ONLY
            after its own commit carrying the manifest paths has reached
            the merged tree — never at staging time.

        unconfirmed_writes_report(*, working_dir, install_root, manifest,
                                   record_ids, state_path) -> list[dict]
            Read-only, non-mutating. For each manifest path, compares the
            working_dir content against install_root's; for any whose text
            is absent from install_root, returns
            {"destination": <path relative to working_dir>, "text": ...,
             "eligible": <True iff state_path does not yet mark the
             corresponding record_id processed>}.

        emission_backlog(*, sink_path, read_hashes) -> dict
            Read-only, non-mutating (INF-700a-5-ii's "must not route").
            Re-reads sink_path and returns
            {"present": int, "read": int, "difference": int,
             "waiting": [{"text":..., "destination":...}, ...]}
            for every eligible (text-bearing) record whose hash is not in
            read_hashes.

        claim_and_confirm_routed(*, state_path, record_ids, lock_path=None,
                                  arbitration_enabled=True) -> list[str]
            Atomically merges record_ids into state_path, returning the
            subset this call newly claimed. With arbitration disabled, both
            of two concurrent callers can claim the same id (the
            reachability negative control INF-700a-5-iii's test_spec
            requires).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMPLETION_ROUTING_PATH = _REPO_ROOT / "scripts" / "knowledge" / "completion_routing.py"
_EMIT_KNOWLEDGE_PATH = _REPO_ROOT / "scripts" / "knowledge" / "emit_knowledge.py"
_VOCAB_PATH = _REPO_ROOT / "config" / "entry_kind_vocabulary.json"

_GIT_IDENTITY = [
    "-c",
    "user.name=inf700a5-test-fixture",
    "-c",
    "user.email=inf700a5-test-fixture@example.invalid",
]


def load_completion_routing() -> types.ModuleType:
    """Load scripts/knowledge/completion_routing.py by path.

    Deliberately does NOT catch the failure: the module does not exist yet,
    so this raises FileNotFoundError (via spec.loader.exec_module) — the
    intended RED signal for every test built on this fixture. Loaded by
    path (not `import scripts.knowledge.completion_routing`) because
    `scripts/` is not a package (no __init__.py) — same convention as
    unit_tests/test_bp_900g_9.py and harvest_learnings.py's own
    `_load_required_sibling_module`.
    """
    spec = importlib.util.spec_from_file_location(
        "inf700a5_completion_routing_under_test", _COMPLETION_ROUTING_PATH
    )
    if spec is None or spec.loader is None:
        raise FileNotFoundError(
            f"could not build a module spec for {_COMPLETION_ROUTING_PATH} "
            "(expected: not yet implemented — this is the RED baseline)"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *_GIT_IDENTITY, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}: {exc.stdout} {exc.stderr}"
        ) from exc


def init_install_repo(root: Path, destinations: dict[str, str]) -> Path:
    """Create a real git repo at *root* representing "the merged tree" — an
    install with one initial commit on `main` seeding each of *destinations*
    (relative path -> initial content).
    """
    root.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-b", "main"], root)
    for rel_path, content in destinations.items():
        dest = root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        _run_git(["add", rel_path], root)
    _run_git(["commit", "-m", "seed install with tracked destinations"], root)
    return root


def clone_working_dir(install_root: Path, dest: Path, branch: str) -> Path:
    """Clone *install_root* into *dest* on a new *branch* — a real,
    independent working directory for one isolated unit of work."""
    _run_git(["clone", str(install_root), str(dest)], dest.parent)
    _run_git(["checkout", "-b", branch], dest)
    return dest


def commit_paths(working_dir: Path, paths: list[str], message: str) -> None:
    """Stage exactly *paths* (never `git add -A` — mirrors the commit
    agent's own by-name staging contract, templates/agents/commit.md) and
    commit them inside *working_dir*."""
    for rel_path in paths:
        _run_git(["add", rel_path], working_dir)
    _run_git(["commit", "-m", message], working_dir)


def merge_into_install(install_root: Path, working_dir: Path, branch: str) -> None:
    """Simulate the completion path's publication: merge *branch* from the
    real *working_dir* clone into *install_root*'s `main` — a real git
    merge across two independent repos, exactly as a PR merge or a
    fast-forward push would land the branch's commit in the merged tree."""
    _run_git(["pull", "--no-edit", str(working_dir), branch], install_root)


def emit(
    sink_path: Path,
    *,
    agent: str,
    component: str,
    destination: str,
    entry_kind: str,
    text: str,
) -> None:
    """Append one real `knowledge_captured` event to *sink_path* via the
    REAL emit_knowledge.py CLI (Fixture Authenticity Rule) — never a
    hand-typed JSON line."""
    result = subprocess.run(
        [
            sys.executable,
            str(_EMIT_KNOWLEDGE_PATH),
            "--agent",
            agent,
            "--component",
            component,
            "--destination",
            destination,
            "--entry-kind",
            entry_kind,
            "--text",
            text,
            "--sink",
            str(sink_path),
            "--vocabulary",
            str(_VOCAB_PATH),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"emit_knowledge.py fixture call failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
