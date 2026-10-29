"""
MODULE: unit_tests/commit_guardian/_bo2500a8_support.py
GOAL: Shared helpers of the BO-2500a-8 test tree (agreement roll-up, BO-2500a-8-i reason required,
    BO-2500a-8-v duplicate reason): records written through yaml.safe_dump, a temp tree holding the
    real schema, and the two real hooks run as subprocesses.
BUSINESS CONTEXT: The authoring check (check_ac_schema.py) and the done gate (check_done_proof.py)
    must agree on whether a test-free declaration carries a reason. Every verdict here comes from
    running the real hook, never from calling a validator function in-process.
ARCHITECTURE: Test-support module (no test_ prefix, not collected). Pure helpers; the only I/O is a
    temp tree, git for the staged path, and one subprocess per verdict.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
AC_HOOK = REPO / "templates" / "scripts" / "commit_guardian" / "check_ac_schema.py"
DONE_HOOK = REPO / "templates" / "scripts" / "commit_guardian" / "check_done_proof.py"
SCHEMA = REPO / "config" / "ac_store_schema.json"

ABSENT = object()  # the test_rationale key is left out of the record
SENTENCE = "Docs-only change; no executable behaviour to test."
STORED_ID = "DK-210b-3"

# (label, value) - one test_required-false record per boundary reason (BO-2500a-8).
REASON_CASES: list[tuple[str, Any]] = [
    ("absent", ABSENT),
    ("null", None),
    ("empty", ""),
    ("spaces", "   "),
    ("tab_newline", "\t\n"),
    ("non_breaking_space", " "),
    ("zero_width_space", "​"),
    ("number", 5),
    ("list", ["a reason"]),
    ("sentence", SENTENCE),
]


def reason_present(value: Any) -> bool:
    """The shared rule: a reason is present iff it is a str that is non-empty after strip()."""
    return isinstance(value, str) and bool(value.strip())


def record(ac_id: str, *, rationale: Any = ABSENT, test_required: Any = False, readiness: str = "draft",
           change_target: str = "docs", work_status: str = "todo", **extra: Any) -> dict[str, Any]:
    """A schema-valid AC record skeleton; only the test declaration varies."""
    code = change_target == "code"
    data: dict[str, Any] = {
        "id": ac_id,
        "title": f"Fixture record {ac_id}",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "status": "active",
        "readiness": readiness,
        "priority": "medium",
        "level": "L3",
        "work_status": work_status,
        "change_target": change_target,
        "assigned_agent": "python-coder" if code else "documentation-expert",
        "criteria": "Given a fixture record\nWhen the hook evaluates it\nThen only the test declaration varies\n",
        "it_requirements": "A plain string implementation note.",
        "depends_on": [], "covered_by": [], "implemented_by": [], "superseded_by": None,
    }
    if test_required is not ABSENT:
        data["test_required"] = test_required
    if rationale is not ABSENT:
        data["test_rationale"] = rationale
    data.update(extra)
    return data


def write_record(root: Path, data: dict[str, Any], sub: str = "build-orchestration") -> Path:
    """Write `data` with yaml.safe_dump under root/docs/acceptance-criteria/<sub>/ and copy the schema."""
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA, root / "config" / "ac_store_schema.json")
    folder = root / "docs" / "acceptance-criteria" / sub
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("HOOK_ROOT", "HOOK_TEST_STAGED_FILES")}
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", **extra})
    return env


def run_authoring(root: Path, staged: list[Path]) -> subprocess.CompletedProcess:
    """check_ac_schema.py as a subprocess, HOOK_ROOT set, `staged` named through HOOK_TEST_STAGED_FILES."""
    env = _env(HOOK_ROOT=str(root), HOOK_TEST_STAGED_FILES=os.pathsep.join(str(p) for p in staged))
    return subprocess.run([sys.executable, str(AC_HOOK)], env=env, cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


def git_init(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True, text=True)


def git_add(root: Path, *paths: Path) -> None:
    rel = [str(p.relative_to(root)) for p in paths]
    subprocess.run(["git", "-C", str(root), "add", *rel], check=True, capture_output=True, text=True)


def run_authoring_git(root: Path) -> subprocess.CompletedProcess:
    """check_ac_schema.py the way the pre-commit hook runs it: cwd in the repo, staged by git add."""
    return subprocess.run([sys.executable, str(AC_HOOK)], env=_env(), cwd=str(root), capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


def run_done_gate(root: Path) -> subprocess.CompletedProcess:
    """check_done_proof.py --mode precommit as a subprocess, cwd in the git repo that stages the record."""
    return subprocess.run([sys.executable, str(DONE_HOOK), "--mode", "precommit", "--test-root", str(root)],
                          env=_env(), cwd=str(root), capture_output=True, text=True, encoding="utf-8",
                          timeout=120)


def authoring_and_done_verdicts(root: Path, ac_id: str, rationale: Any) -> tuple[int, int]:
    """(authoring exit, done-gate exit) for one test-free record carrying `rationale`.

    The same record is written twice in one git repo: work_status todo for the authoring hook, then
    work_status done (staged, no covers tag anywhere) for the done gate.
    """
    git_init(root)
    path = write_record(root, record(ac_id, rationale=rationale))
    git_add(root, path)
    authoring = run_authoring(root, [path]).returncode
    path = write_record(root, record(ac_id, rationale=rationale, work_status="done"))
    git_add(root, path)
    return authoring, run_done_gate(root).returncode


def messages(stderr: str) -> list[str]:
    """The refusal messages of a hook run: the text after '<file>.yaml: ' on each failure line.

    The file path also carries the record id, so a test that wants the MESSAGE to name a record must
    read this and not the whole stderr.
    """
    return [ln.split(".yaml: ", 1)[1] for ln in stderr.splitlines() if ".yaml: " in ln]
