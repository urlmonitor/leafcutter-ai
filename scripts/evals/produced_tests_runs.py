"""
MODULE: scripts/evals/produced_tests_runs.py
GOAL: Everything the produced-tests mode EXECUTES in a row sandbox: building the git
    sandbox, running produced tests under pytest, and scoring the test half of a row by
    running the shared wrong-version runner against the produced test.
BUSINESS CONTEXT: TQ-200d-1-i. A test that says it catches a wrong version and does not
    (incident 1: the branch ran 0 times) can only be failed by RUNNING it against that
    wrong version. The verdict therefore comes from wrong_version_runner.run_runner, the
    same runner the build routes use, never from a judge and never from the report.
ARCHITECTURE: Sibling of produced_tests_mode.py (row loop) and produced_tests_scoring.py
    (assertion registry). ``run_runner`` is bound as a module attribute so a test can wrap it.
    The sandbox is its own git repository: its base commit is the fixture project as copied
    (fixed/ and altered/ are held back from the copy), the AC record and the produced tests
    are written after it, the fix is installed in the working tree, and the runner is called
    with base_ref set to the base commit (never HEAD). The runner's recovery journal lives
    under the sandbox's own git dir. Nothing is read from or written to the repository.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - parses the junit file our own pytest run wrote
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from produced_tests_transcript import TRANSCRIPT_NAME, BashCall, bash_calls

_ORCHESTRATION = Path(__file__).resolve().parents[1] / "build_orchestration"
if str(_ORCHESTRATION) not in sys.path:
    sys.path.insert(0, str(_ORCHESTRATION))
from wrong_version_runner import run_runner  # noqa: E402

logger = logging.getLogger("run_agent_eval")

GIT_OPTS = ["-c", "user.name=eval", "-c", "user.email=eval@example.invalid", "-c", "commit.gpgsign=false",
            "-c", "core.autocrlf=false", "-c", f"core.hooksPath={os.devnull}"]
COVERS_RE = re.compile(r"#\s*covers:\s*(\S+)")
TESTS_DIR = "tests"
PYTEST_TIMEOUT = 180
FILES_DIR = "files"
SANDBOX_NAME = "sandbox"
EVIDENCE_DIR = "leafcutter"
# Variables that point git at a repository other than the sandbox (a pre-commit hook sets some of them).
GIT_REDIRECT_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_PREFIX", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES")


class SandboxError(Exception):
    """Raised when a row sandbox cannot be built or a command in it cannot run."""


def scrubbed_env(**extra: str) -> dict[str, str]:
    """The ONE environment every sandbox subprocess gets: the caller's, without the git redirect variables (H-1)."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECT_VARS}
    env.update(extra)
    return env


@contextmanager
def scrubbed_environ() -> Iterator[None]:
    """Remove the git redirect variables from os.environ for the in-process runner call; restore them in finally."""
    saved = {k: os.environ.pop(k) for k in GIT_REDIRECT_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def hold_back_dirs(specs: list[dict]) -> set[str]:
    """Top-level entries of the fixture the agent must never see: the fixed, altered and mutant copies."""
    paths = [s[k] for s in specs for k in ("fixed", "altered") if s.get(k)]
    paths += [m for s in specs for m in s.get("mutants", [])]
    return {Path(p).parts[0] for p in paths}


@dataclass
class RowContext:
    """What one row's assertions are checked against."""

    sandbox: Path
    work_dir: Path
    fixture_dir: Path
    base_sha: str
    report: str = ""
    test_files: dict[str, Path] = field(default_factory=dict)
    calls: list[BashCall] | None = None  # Bash calls of the agent's transcript; None when none was recorded


def git(sandbox: Path, *args: str) -> str:
    """Run git in *sandbox* and return stdout. I/O boundary: a failure raises SandboxError."""
    cmd = ["git", *GIT_OPTS, "-C", str(sandbox), *args]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60, env=scrubbed_env())  # noqa: S603
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("sandbox git %s failed: %s", " ".join(args), exc)
        msg = f"sandbox git {' '.join(args)} failed: {exc}"
        raise SandboxError(msg) from exc
    return done.stdout


def build_sandbox(fixture_dir: Path, sandbox: Path, hold_back: set[str], support: tuple[tuple[Path, str], ...] = ()) -> str:
    """Copy the fixture project into *sandbox*, commit it as the base and return the base sha.

    Top-level entries named in *hold_back* (the fixed and altered copies) are not copied, so the
    agent never sees the wrong version. *support* is ``(source dir, sandbox-relative dir)`` pairs of
    scripts the template names; they join the base commit so they never read as changed code.
    """
    try:
        shutil.copytree(fixture_dir, sandbox, ignore=lambda _d, names: [n for n in names if n in hold_back or n == "__pycache__"])
        for source, rel in support:
            shutil.copytree(source, sandbox / rel, ignore=shutil.ignore_patterns("__pycache__"))
    except OSError as exc:
        logger.warning("cannot copy fixture %s: %s", fixture_dir, exc)
        msg = f"cannot copy fixture {fixture_dir}: {exc}"
        raise SandboxError(msg) from exc
    git(sandbox, "init", "-q")
    git(sandbox, "add", "-A")
    git(sandbox, "commit", "-q", "--allow-empty", "-m", "base: the fixture project as copied")
    return git(sandbox, "rev-parse", "HEAD").strip()


def remove_tree(path: Path) -> None:
    """Remove a sandbox, clearing the read-only bit git sets on object files (Windows)."""
    def _writable(func, target, _exc):  # noqa: ANN001
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_writable)
    else:
        shutil.rmtree(path, onerror=_writable)


def _register_test(ctx: RowContext, target: Path) -> None:
    """Record a produced test file under its base name (its sandbox-relative path when that name is taken)."""
    key = target.name if target.name not in ctx.test_files else target.relative_to(ctx.sandbox).as_posix()
    ctx.test_files[key] = target


def place_evidence(output_dir: Path, ctx: RowContext) -> None:
    """Copy ``<output_dir>/leafcutter/**`` into ``<sandbox git dir>/leafcutter``, where the template writes it (TQ-200d-2).

    The to-run-later file lives under the git dir so it never reads as a changed project file.
    """
    source = output_dir / EVIDENCE_DIR
    if source.is_dir():
        git_dir = Path(git(ctx.sandbox, "rev-parse", "--absolute-git-dir").strip())
        shutil.copytree(source, git_dir / EVIDENCE_DIR, dirs_exist_ok=True)


def place_outputs(output_dir: Path, ctx: RowContext) -> None:
    """Put the recorded output into the sandbox and read the report.

    A gold output is flat ``*.py.recorded`` files that land in ``tests/``. A live output keeps every
    file the agent added or changed under ``files/`` at its relative path; those are replayed at the
    same paths, so helpers, conftest files, fixtures and nested tests keep resolving.
    """
    tests = ctx.sandbox / TESTS_DIR
    tests.mkdir(exist_ok=True)
    for recorded in sorted(output_dir.glob("*.py.recorded")):
        target = tests / recorded.name[: -len(".recorded")]
        shutil.copyfile(recorded, target)
        _register_test(ctx, target)
    replay = output_dir / FILES_DIR
    for source in sorted(p for p in replay.rglob("*") if p.is_file()):
        target = ctx.sandbox / source.relative_to(replay)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if target.name.startswith("test_") and target.suffix == ".py":
            _register_test(ctx, target)
    place_evidence(output_dir, ctx)
    report = output_dir / "report.md"
    ctx.report = report.read_text(encoding="utf-8") if report.is_file() else ""
    transcript = output_dir / TRANSCRIPT_NAME
    ctx.calls = bash_calls(transcript.read_text(encoding="utf-8")) if transcript.is_file() else None


def run_pytest(ctx: RowContext, names: list[str], env_extra: dict[str, str] | None = None) -> dict:
    """Run the named produced test files under pytest in the sandbox; return the parsed junit cases.

    A case status is passed, failure, error or skipped. A skipped or xfail(run=False) test is
    ``skipped`` and an unexpectedly passing xfail is a failure (xfail_strict), so neither is green.
    """
    junit = ctx.work_dir / "junit.xml"
    junit.unlink(missing_ok=True)
    files = [ctx.test_files[n].relative_to(ctx.sandbox).as_posix() for n in names]
    cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-o", "xfail_strict=true", "-q", "--junitxml", str(junit), *files]
    env = scrubbed_env(PYTHONDONTWRITEBYTECODE="1", **(env_extra or {}))
    try:
        done = subprocess.run(cmd, cwd=ctx.sandbox, capture_output=True, text=True, timeout=PYTEST_TIMEOUT, env=env, check=False)  # noqa: S603
        root = ET.parse(junit).getroot() if junit.is_file() else None  # noqa: S314
    except (subprocess.TimeoutExpired, OSError, ET.ParseError) as exc:
        logger.warning("produced-test pytest run failed: %s", exc)
        msg = f"pytest in the sandbox did not finish: {exc}"
        raise SandboxError(msg) from exc
    cases = []
    for case in (root.iter("testcase") if root is not None else []):
        bad = next((c for c in case if c.tag in ("failure", "error", "skipped")), None)
        text = "" if bad is None else f"{bad.get('message') or ''}\n{bad.text or ''}"
        cases.append({"name": case.get("name", ""), "status": "passed" if bad is None else bad.tag, "text": text})
    return {"returncode": done.returncode, "cases": cases, "output": (done.stdout or "")[-400:]}


def all_green(outcome: dict) -> bool:
    """True when pytest collected at least one test and every one passed (a skip is not a pass)."""
    return bool(outcome["cases"]) and all(c["status"] == "passed" for c in outcome["cases"])


def first_problem(outcome: dict) -> str:
    """Why *outcome* is not green: the first non-passing case's first line, or that nothing was collected."""
    for case in outcome["cases"]:
        if case["status"] != "passed":
            lines = case["text"].strip().splitlines()
            return f"{case['status']}: {lines[0][:160] if lines else case['name']}"
    return "no test collected"


def tagged_tests(files: dict[str, Path]) -> list[tuple[str, str]]:
    """Return ``(ac id, test function)`` for every ``# covers:`` tagged test function."""
    found: list[tuple[str, str]] = []
    for path in files.values():
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                tag = COVERS_RE.search("\n".join(lines[node.lineno - 1 : node.end_lineno]))
                if tag:
                    found.append((tag.group(1), node.name))
    return found


def write_ac_records(ac_root: Path, tagged: list[tuple[str, str]], wrong_version: str, module: str) -> None:
    """Write one AC record per tagged id; each test_spec entry carries the row's must_catch (OQ-4)."""
    ac_root.mkdir(parents=True, exist_ok=True)
    for ac_id in sorted({a for a, _ in tagged}):
        entries = [{"name": fn, "type": "unit", "angle": "discrimination", "must_catch": [wrong_version],
                    "in_scope_files": [module], "description": f"{fn} must fail under: {wrong_version}"}
                   for a, fn in tagged if a == ac_id]
        record = {"id": ac_id, "title": "eval sandbox record", "level": "L3", "test_spec": entries}
        (ac_root / f"{ac_id}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")


def write_manifest(work_dir: Path, spec: dict, fixture_dir: Path) -> Path:
    """Write the alterations manifest: the named wrong version, prepared from the fixture's altered copy."""
    module = spec["module"]
    altered = work_dir / "alterations" / module
    altered.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture_dir / spec["altered"], altered)
    entry = {"name": spec["wrong_version"], "status": "prepared", "files": [{"path": module, "altered_copy": str(altered)}]}
    manifest = work_dir / "alterations" / "manifest.json"
    manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
    return manifest


def judge_verdict(verdict: dict, wrong_version: str, tagged: list[tuple[str, str]]) -> tuple[bool, str]:
    """Judge a runner verdict: passed only on gate_passed and a caught row from a produced test."""
    names = {fn for _, fn in tagged}
    rows = verdict.get("results", [])
    caught = [r for r in rows if r.get("result") == "caught" and r.get("wrong_version") == wrong_version
              and r.get("test", "").rsplit("::", 1)[-1] in names]
    if verdict.get("gate_passed") and caught:
        return True, f"caught '{wrong_version}' by {caught[0]['test'].rsplit('::', 1)[-1]} (runner gate_passed)"
    details = [f"{r.get('result')}: {r.get('detail')}" for r in rows if r.get("result") != "caught"]
    reason = verdict.get("reason") or verdict.get("outcome") or "no reason given"
    return False, f"not caught by the runner ({reason}); " + "; ".join(details)


def wrong_version_run(ctx: RowContext, spec: dict) -> dict:
    """Score the test half: install the fix, then run the produced test against the wrong version."""
    tagged = tagged_tests(ctx.test_files)
    if not tagged:
        return {"passed": False, "detail": "no '# covers: <AC-ID>' tagged test in the output, so there is nothing to run", "verdict": {}}
    module = spec["module"]
    write_ac_records(ctx.sandbox / "ac_store", tagged, spec["wrong_version"], module)
    shutil.copyfile(ctx.fixture_dir / spec["fixed"], ctx.sandbox / module)
    manifest = write_manifest(ctx.work_dir, spec, ctx.fixture_dir)
    ids = sorted({a for a, _ in tagged})
    with scrubbed_environ():
        verdict = run_runner(ids, ctx.sandbox / TESTS_DIR, ctx.sandbox / "ac_store", ctx.base_sha, str(manifest))
    passed, detail = judge_verdict(verdict, spec["wrong_version"], tagged)
    return {"passed": passed, "detail": detail, "verdict": verdict}
