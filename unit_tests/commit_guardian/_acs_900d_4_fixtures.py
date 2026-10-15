"""
MODULE: unit_tests/commit_guardian/_acs_900d_4_fixtures.py
GOAL: Shared plumbing for the ACS-900d-4 family of tests (a superseded record
    that names existing successors is retired and is not held to the forward
    "is it built and tested now" rules).

Not a test file (does not match test_*.py), so pytest never collects it.

DESIGN
    * Every gate runs as a REAL subprocess against a throwaway git repo whose
      index holds the records under test. The hooks read the index (or the
      store on disk) and ignore argv, so a clean exit proves nothing on its own:
      each scenario therefore pairs the retired record with an ACTIVE twin (the
      control row) that the same hook must still refuse.
    * Hooks are run from the SOURCE copies under templates/scripts/commit_guardian/
      (the files the fix edits). Their ac_store dependency resolves to the
      tracked scripts/ac_store/ through _ac_store_locator, so no build.py is
      needed. The deployed layout is exercised separately in the real-artifact
      test through the session-shared reference layout.
    * Records are written with yaml.safe_dump (never a hand-typed literal).
    * ``seam_runner`` runs a hook with the shared predicate replaced by one that
      always answers "not retired", proving every gate consults that ONE
      definition. It exits 97 with a RUNNER-CANNOT-PATCH marker when
      scripts/ac_store/ac_retirement.py does not exist, so a missing module can
      never be mistaken for a gate that "refused".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_HOOKS = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
AC_STORE_SRC = REPO_ROOT / "scripts" / "ac_store"
VALIDATE_AC_SCHEMA = AC_STORE_SRC / "validate_ac_schema.py"
SCHEMA_SRC = REPO_ROOT / "config" / "ac_store_schema.json"

STORE_REL = Path("docs") / "acceptance-criteria"
GROUP_REL = STORE_REL / "test-component"
SUCCESSOR = "AR-400c-1"
MISSING_SUCCESSOR = "ZZ-999"
TEST_CONTRACT_REFUSAL = "approved code AC must declare a test contract"
HOOK_TIMEOUT = 240
RUNNER_UNPATCHABLE = 97

_DONE_PROOF_LINE = re.compile(
    r"^\[check-done-proof\] ([A-Z]{2,6}(?:-[A-Z]{2,6})?-\d[\w-]*): (.*)$"
)

_RUNNER_SOURCE = """\
import runpy
import sys
from pathlib import Path

hook = Path(sys.argv[1]).resolve()
sys.argv = [str(hook), *sys.argv[2:]]
sys.path.insert(0, str(hook.parent))
sys.path.insert(0, {ac_store!r})
sys.path.insert(0, {repo_root!r})
try:
    import ac_retirement
except ImportError as exc:
    print(f"RUNNER-CANNOT-PATCH: {{exc}}")
    sys.exit({unpatchable})


def _never_retired(*_args, **_kwargs):
    return False


ac_retirement.is_retired = _never_retired
try:
    from scripts.ac_store import ac_retirement as _package_copy
except ImportError:
    pass
else:
    _package_copy.is_retired = _never_retired
print("RUNNER-PATCHED")
runpy.run_path(str(hook), run_name="__main__")
"""


# ---------------------------------------------------------------------------
# Process plumbing
# ---------------------------------------------------------------------------


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment without inherited hook-test seams or git plumbing variables."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "HOOK_"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.update(extra or {})
    return env


def run(argv: list, cwd: Path, extra_env: dict[str, str] | None = None):
    """Run *argv* with cwd *cwd*; never raises on a non-zero exit."""
    return subprocess.run(
        [str(a) for a in argv],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=HOOK_TIMEOUT,
        env=_clean_env(extra_env),
    )


def git_ok(repo: Path, *args: str):
    """Run git in *repo* and fail loudly (a harness error, not a red test)."""
    proc = run(["git", *args], repo)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc


def out(proc) -> str:
    """Combined stdout and stderr of a completed process."""
    return f"{proc.stdout}\n{proc.stderr}"


def mentions(text: str, ac_id: str) -> bool:
    """True when *ac_id* appears in *text* as a whole id (not as a prefix of a longer one)."""
    return re.search(rf"(?<![\w-]){re.escape(ac_id)}(?![\w-])", text) is not None


def done_proof_refusals(proc) -> dict[str, str]:
    """Map ac id -> reason for every ``[check-done-proof] <id>: <reason>`` line."""
    found: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        match = _DONE_PROOF_LINE.match(line.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


def lines_naming(proc, *needles: str) -> list[str]:
    """Output lines that contain every one of *needles* as whole ids/phrases."""
    return [
        ln
        for ln in out(proc).splitlines()
        if all(mentions(ln, n) if re.fullmatch(r"[A-Z][\w-]*", n) else n in ln for n in needles)
    ]


# ---------------------------------------------------------------------------
# Repo + record builders
# ---------------------------------------------------------------------------


def make_repo(root: Path) -> Path:
    """A git repo with the real AC schema, an empty AC group and an empty tests dir."""
    root.mkdir(parents=True, exist_ok=True)
    git_ok(root, "init", "-q", "-b", "main")
    git_ok(root, "config", "user.email", "fixture@example.invalid")
    git_ok(root, "config", "user.name", "Fixture")
    git_ok(root, "config", "commit.gpgsign", "false")
    (root / "config").mkdir()
    shutil.copyfile(SCHEMA_SRC, root / "config" / "ac_store_schema.json")
    # check_ac_parent_covered_by finds ac_parent_id.py under <project>/scripts/ac_store
    # when run from a source checkout; a real project has it there, so the fixture does too.
    (root / "scripts" / "ac_store").mkdir(parents=True)
    shutil.copyfile(AC_STORE_SRC / "ac_parent_id.py", root / "scripts" / "ac_store" / "ac_parent_id.py")
    (root / "tests").mkdir()
    (root / GROUP_REL).mkdir(parents=True)
    return root


def ac_record(ac_id: str, **overrides) -> dict:
    """A schema-valid, approved, done, leaf code AC; *overrides* replace any field."""
    record: dict = {
        "id": ac_id,
        "title": f"Retirement fixture {ac_id}",
        "component": "ac-store",
        "components": ["ac_store", "commit_guardian"],
        "readiness": "approved",
        "priority": "high",
        "level": "L2",
        "status": "active",
        "req_status": "draft",
        "work_status": "done",
        "criteria": (
            "Given a fixture record\n"
            "When the commit gates run\n"
            "Then the fixture is judged as the test requires\n"
        ),
        "change_target": "code",
        "assigned_agent": "python-coder",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    record.update(overrides)
    return record


def retired_record(ac_id: str, successors=(SUCCESSOR,), **overrides) -> dict:
    """A record retired by supersession; successors default to the real AR-400c-1 id."""
    return ac_record(
        ac_id, status="superseded_by", superseded_by=list(successors), **overrides
    )


def active_twin(record: dict) -> dict:
    """The control row: identical to *record* except status active, superseded_by null."""
    return {**record, "status": "active", "superseded_by": None}


def with_test_contract(record: dict, *, required_false: bool = False) -> dict:
    """*record* plus a valid one-entry test_spec (and test_required false on request)."""
    entry = {
        "name": "test_fixture_entry",
        "target_dir": "unit_tests/commit_guardian/",
        "framework": "pytest",
        "type": "unit",
        "angle": "criterion",
        "description": "fixture entry",
        "covers": [record["id"]],
    }
    extra: dict = {"test_spec": [entry]}
    if required_false:
        extra["test_required"] = False
    return {**record, **extra}


def write_record(repo: Path, record: dict, group: Path = GROUP_REL) -> Path:
    """Serialise *record* with yaml.safe_dump into the repo's AC group."""
    path = repo / group / f"{record['id']}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def write_successor(repo: Path) -> Path:
    """The existing, active successor record every retirement points at."""
    return write_record(repo, ac_record(SUCCESSOR, work_status="todo"))


def write_covering_test(repo: Path, ac_id: str) -> Path:
    """A real, passing test file carrying ``# covers: <ac_id>``."""
    slug = re.sub(r"\W", "_", ac_id).lower()
    path = repo / "tests" / f"test_{slug}.py"
    path.write_text(
        f"def test_{slug}():\n    # covers: {ac_id}\n    assert True\n", encoding="utf-8"
    )
    return path


def commit_base(repo: Path, exclude: tuple[Path, ...] = ()) -> None:
    """Commit everything on disk except *exclude* (repo-relative paths)."""
    pathspecs = [".", *[f":(exclude){p.as_posix()}" for p in exclude]]
    git_ok(repo, "add", "-A", "--", *pathspecs)
    git_ok(repo, "commit", "-q", "--no-verify", "--allow-empty", "-m", "base store")


def stage(repo: Path, *paths: Path) -> None:
    """``git add`` the given paths so they are in the index."""
    git_ok(repo, "add", "--", *[str(p) for p in paths])


def commit_staged(repo: Path, message: str = "retire") -> None:
    """Commit the index (hooks disabled) so ci-changed has a base...HEAD diff."""
    git_ok(repo, "commit", "-q", "--no-verify", "-m", message)


def stage_scenario(repo: Path, staged: list[dict], *, base_extra: list[dict] = ()) -> list[Path]:
    """Base-commit the successor + *base_extra*; write and stage the *staged* records.

    Returns the staged files' paths. Records in *staged* are NOT in the base commit.
    """
    write_successor(repo)
    for record in base_extra:
        write_record(repo, record)
    staged_paths = [write_record(repo, record) for record in staged]
    commit_base(repo, exclude=tuple(p.relative_to(repo) for p in staged_paths))
    stage(repo, *staged_paths)
    return staged_paths


# ---------------------------------------------------------------------------
# Composite (parent + children) scenarios
# ---------------------------------------------------------------------------

PARENT_ID = "RT-200a"
KIDS = ("RT-200a-1", "RT-200a-2", "RT-200a-3")
# state -> (is_retired, work_status, has_covering_test, successors)
_KID_STATES = {
    "live_done": (False, "done", True, ()),
    "live_todo": (False, "todo", False, ()),
    "retired_todo": (True, "todo", False, (SUCCESSOR,)),
    "retired_done": (True, "done", True, (SUCCESSOR,)),
    "bad_retired_todo": (True, "todo", False, (MISSING_SUCCESSOR,)),
}


def kid_record(kid_id: str, state: str) -> dict:
    """The child record for one of the named composite-scenario states."""
    retired, work_status, _, successors = _KID_STATES[state]
    common = {"work_status": work_status, "depends_on": [PARENT_ID]}
    if retired:
        return retired_record(kid_id, successors=successors, **common)
    return ac_record(kid_id, **common)


def composite_scenario(repo: Path, states: tuple[str, str, str], *, parent_cover: bool = False) -> Path:
    """Base-commit the kids (and their covering tests); stage a done parent over them.

    Args:
        repo: A repo from :func:`make_repo`.
        states: One state name per entry of :data:`KIDS`.
        parent_cover: Also commit a covering test naming the parent itself.

    Returns:
        The staged parent file's path.
    """
    write_successor(repo)
    for kid_id, state in zip(KIDS, states, strict=True):
        write_record(repo, kid_record(kid_id, state))
        if _KID_STATES[state][2]:
            write_covering_test(repo, kid_id)
    if parent_cover:
        write_covering_test(repo, PARENT_ID)
    parent = write_record(
        repo, ac_record(PARENT_ID, level="L1", work_status="done", covered_by=list(KIDS))
    )
    commit_base(repo, exclude=(parent.relative_to(repo),))
    stage(repo, parent)
    return parent


_DRIVER_SOURCE = """\
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, {ac_store!r})
from _done_proof_composite import _collect_all_covered_ids, _unproven_composite_children
from _done_proof_phase_helpers import _build_ac_status_map
from done_proof import _resolve_all_child_ids

store, tests, parent = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
data = yaml.safe_load(parent.read_text(encoding="utf-8"))
print(json.dumps({{
    "precommit": _unproven_composite_children(data, store, _collect_all_covered_ids(tests)),
    "ci": _resolve_all_child_ids(data["covered_by"], _build_ac_status_map(store)),
}}))
"""


def composite_verdicts(repo: Path, parent: Path) -> dict:
    """Run both composite rollup functions in a fresh process and return their results.

    ``precommit`` is ``_unproven_composite_children`` (the pre-commit rollup);
    ``ci`` is ``_resolve_all_child_ids`` (the CI rollup's leaf list).
    """
    driver = repo.parent / f"{repo.name}_composite_driver.py"
    driver.write_text(_DRIVER_SOURCE.format(ac_store=str(AC_STORE_SRC)), encoding="utf-8")
    proc = run([sys.executable, driver, repo / STORE_REL, repo / "tests", parent], repo)
    assert proc.returncode == 0, f"composite driver failed: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# Gate runners (all real subprocesses)
# ---------------------------------------------------------------------------


def seam_runner(tmp_dir: Path) -> Path:
    """Write the predicate-patching runner into *tmp_dir* and return its path."""
    path = tmp_dir / "seam_runner.py"
    path.write_text(
        _RUNNER_SOURCE.format(
            ac_store=str(AC_STORE_SRC),
            repo_root=str(REPO_ROOT),
            unpatchable=RUNNER_UNPATCHABLE,
        ),
        encoding="utf-8",
    )
    return path


def _hook(script: Path, args: list, repo: Path, runner: Path | None, hooks_dir: Path):
    target = script if script.is_absolute() else hooks_dir / script
    argv = [sys.executable, *([runner] if runner else []), target, *args]
    return run(argv, repo)


def done_proof(
    repo: Path,
    mode: str = "precommit",
    *,
    base: str | None = None,
    runner: Path | None = None,
    hooks_dir: Path = TEMPLATE_HOOKS,
):
    """check_done_proof.py in *mode* against the repo's store and tests dir."""
    args = ["--mode", mode, "--ac-root", repo / STORE_REL, "--test-root", repo / "tests"]
    if base:
        args += ["--base", base]
    return _hook(Path("check_done_proof.py"), args, repo, runner, hooks_dir)


def schema_hook(repo: Path, *, runner: Path | None = None, hooks_dir: Path = TEMPLATE_HOOKS):
    """check_ac_schema.py over the staged files."""
    return _hook(Path("check_ac_schema.py"), [], repo, runner, hooks_dir)


def parent_hook(repo: Path, *, hooks_dir: Path = TEMPLATE_HOOKS):
    """check_ac_parent_covered_by.py over the staged files."""
    return _hook(Path("check_ac_parent_covered_by.py"), [], repo, None, hooks_dir)


def limits_hook(repo: Path, *, hooks_dir: Path = TEMPLATE_HOOKS):
    """check_ac_limits.py over the staged files."""
    return _hook(Path("check_ac_limits.py"), [], repo, None, hooks_dir)


def validate_schema(repo: Path, *paths: Path):
    """scripts/ac_store/validate_ac_schema.py (the 'AC store valid' CI check) on *paths*."""
    return _hook(VALIDATE_AC_SCHEMA, [*paths], repo, None, TEMPLATE_HOOKS)


def run_all_done_proof_paths(repo: Path, *, runner: Path | None = None) -> dict:
    """Pre-commit on the index, then commit it, then ci-changed and full ci.

    Returns ``{"precommit": proc, "ci_changed": proc, "ci": proc}``.
    """
    results = {"precommit": done_proof(repo, runner=runner)}
    commit_staged(repo)
    results["ci_changed"] = done_proof(repo, "ci-changed", base="HEAD~1", runner=runner)
    results["ci"] = done_proof(repo, "ci", runner=runner)
    return results
