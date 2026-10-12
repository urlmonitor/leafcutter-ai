"""Test infrastructure for TQ-600a-13-xvi (the post-merge fix proof). Not a test: underscore-named.

* ``ProofRun`` -- the shared workflow-step executor whose ``actions/checkout`` emulation knows TWO sources: a checkout
  without ``ref`` is the default branch's tree (``project_dir``), one whose ``ref`` is the pull request's head SHA is
  the head tree. It honours ``path:`` and ``sparse-checkout:``, records every checkout (which job, which ref, which
  path, whether credentials persist) and writes the ``.git/config`` a real checkout leaves behind, with the token's
  ``extraheader`` only when ``persist-credentials`` is not false.
* ``driven`` -- a context manager that serves a red / did-not-complete / green post-merge history and an open
  ``post-merge-red`` notice from the recording fake, seeds the red run's REAL verdict artifact, writes the pull request
  event with ``json.dump``, stages a default-branch tree and a head tree, and executes the two jobs of
  ``post-merge-fix-proof.yml`` verbatim (``Prepare fix proof`` then ``Post-merge fix proof``) over real child pytest
  sessions. Every lane test writes a witness line when it really runs, so a test says what executed, not what exited.
"""

from __future__ import annotations

import configparser
import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ._comment_harness import notice_description
from ._hold_harness import DNC_JOBS, OBSERVER, RED_JOBS, make_run
from ._notice_fakes import REPO, SERVER, import_production, make_verdict
from ._workflow_conditions import _expand
from ._workflow_jobs import REPO_ROOT, JobResult, WorkflowRun, find_job, load_workflow

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-fix-proof.yml"
MODULE = REPO_ROOT / "scripts" / "ci" / "post_merge_fix_proof.py"
PREPARE, PROVE = "Prepare fix proof", "Post-merge fix proof"
HEAD_SHA, RED_HEAD = "9" * 40, "7" * 40
NOTICE, PR_NUMBER = 12, 42
LANE_SELECTION = "manual and not timing_ratio"
X_ID, Y_ID = "tests/test_lane.py::test_x_fails_until_fixed", "tests/test_lane.py::test_y_fails_until_fixed"
FORGED_MARK = "HEAD PROOF ALWAYS PASSES"
FORGED_PROOF = f"import sys\nprint({FORGED_MARK!r})\nsys.exit(0)\n"
FORGED_STATUS = '\n\ndef _status(report):\n    return "passed"\n'  # a head copy of the report plugin that calls every test passed
MAIN_PLUGIN = "scripts.suite_performance.pytest_manual_deselect"  # a real ``-p scripts.*`` plugin, as main's pytest.ini names several
MAIN_ADDOPTS = f'-m "not manual and not timing_ratio" -p {MAIN_PLUGIN}'
FORGED_PLUGINS = {  # what a head can put at the path main's ini plugin resolves to when the head is first on sys.path
    "xfail": "import pytest\n\n\ndef pytest_collection_modifyitems(config, items):\n    for item in items:\n        item.add_marker(pytest.mark.xfail(reason='forged', strict=False))\n",
    "shrink": "def pytest_collection_modifyitems(config, items):\n    kept = [i for i in items if 'x_fails' not in i.nodeid]\n    config.hook.pytest_deselected(items=[i for i in items if i not in kept])\n    items[:] = kept\n",
}
LANE_TEST = '''import os
from pathlib import Path

import pytest

STATE = Path(os.environ["LANE_STATE_DIR"])


def _witness(name):
    with (STATE / "ran.log").open("a", encoding="utf-8") as handle:
        handle.write(name + "\\n")


@pytest.mark.manual
def test_a_always_passes():
    _witness("a")
    assert True


@MANUAL
def test_x_fails_until_fixed():
    _witness("x")
    assert @X_OK@


@MANUAL
def test_y_fails_until_fixed():
    _witness("y")
    assert @Y_OK@


@pytest.mark.manual
def test_other_lane_test():
    _witness("other")
    assert @OTHER_OK@


@pytest.mark.manual
@pytest.mark.timing_ratio
def test_ratio_always_fails():
    _witness("ratio")
    assert False
'''
SHARED_PLUGIN = "scripts.suite_performance.pytest_shared_reference_layout"
ROOT_PROBE_TEST = f'''import os
from pathlib import Path

import pytest

STATE = Path(os.environ["LANE_STATE_DIR"])


@pytest.mark.manual
def test_root_probe(request):
    plugin = request.config.pluginmanager.get_plugin("{SHARED_PLUGIN}")
    assert plugin is not None, "main's shared-layout plugin is not loaded"
    producer = plugin.get_or_produce_shared_layout.__globals__
    with (STATE / "ran.log").open("a", encoding="utf-8") as handle:
        handle.write("probe\\n")
    head = os.path.realpath(os.getcwd())
    assert os.path.realpath(plugin._WORKTREE_ROOT) == head, f"plugin root {{plugin._WORKTREE_ROOT}} is not the head {{head}}"
    assert os.path.realpath(producer["_WORKTREE_ROOT"]) == head, f"producer root {{producer['_WORKTREE_ROOT']}} is not the head {{head}}"
'''
DEFAULT_ONLY_TEST = (
    'import os\nfrom pathlib import Path\n\n\ndef test_default_only_fails():\n'
    '    with (Path(os.environ["LANE_STATE_DIR"]) / "ran.log").open("a", encoding="utf-8") as handle:\n'
    '        handle.write("default\\n")\n    assert False\n'
)


def _write(path, text):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        message = f"cannot write {path}: {exc}"
        raise AssertionError(message) from exc


def _ini(path, addopts):
    """pytest.ini written by the real serializer (``configparser``), as the real file is."""
    ini = configparser.ConfigParser(interpolation=None)
    ini["pytest"] = {"strict_markers": "true", "addopts": addopts, "markers": "\nmanual: opt-in lane\ntiming_ratio: timing lane"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            ini.write(handle)
    except OSError as exc:
        message = f"cannot write {path}: {exc}"
        raise AssertionError(message) from exc


# --------------------------------------------------------------------------- the two trees
def lane_source(*, x_ok=True, y_ok=True, other_ok=False, lane_marked=True, swap=False):
    """The lane test module's text (four selected lane tests; ``lane_marked=False`` takes x and y out of the lane).

    ``swap`` deletes the test that fails until fixed and adds a different, passing one in its place: the lane keeps its size.
    """
    source = LANE_TEST.replace("@MANUAL\n", "@pytest.mark.manual\n" if lane_marked else "")
    source = source.replace("test_x_fails_until_fixed", "test_x_replaced_by_a_passing_one") if swap else source
    return source.replace("@X_OK@", str(x_ok)).replace("@Y_OK@", str(y_ok)).replace("@OTHER_OK@", str(other_ok))


def stage_main(dest, addopts=MAIN_ADDOPTS):
    """The default branch: main's pytest.ini, its own four-test lane and the real ``scripts`` (a symlink).

    The lane is what a collect-only of main's correctness lane counts (the baseline a whole-lane proof may not fall under).
    """
    _ini(dest / "pytest.ini", addopts)
    _write(dest / "tests" / "test_lane.py", lane_source())
    _write(dest / "requirements-dev.txt", "")
    try:
        (dest / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)
    except OSError as exc:
        message = f"cannot stage the default branch: {exc}"
        raise AssertionError(message) from exc
    return dest


def stage_head(dest, *, x_ok=True, y_ok=True, other_ok=False, lane_marked=True, forged=False, forged_plugin=None, probe=False, swap=False):
    """A pull request head: the lane tests (fixed or not), a copy of ``scripts/ci``, and optionally a rewritten harness.

    ``forged`` replaces the proof module with an always-pass one, the report plugin with one that reports every test
    passed, and pytest.ini with one whose ``addopts`` collects only (exit 0, nothing executed). ``forged_plugin``
    (``xfail`` | ``shrink``) replaces the ``-p`` plugin main's pytest.ini names with a forging copy: every failure
    becomes xfailed, or the lane test that fails until fixed is dropped from the selection.
    """
    _write(dest / "tests" / "test_lane.py", lane_source(x_ok=x_ok, y_ok=y_ok, other_ok=other_ok, lane_marked=lane_marked, swap=swap))
    if probe:  # ``probe``: a lane test that asserts which root main's shared-layout code builds from
        _write(dest / "tests" / "test_root_probe.py", ROOT_PROBE_TEST)
    _write(dest / "unit_tests" / "test_default_only.py", DEFAULT_ONLY_TEST)
    _write(dest / "requirements-dev.txt", "")
    _ini(dest / "pytest.ini", f'-m "{LANE_SELECTION}" --collect-only' if forged else '-m "not manual and not timing_ratio"')
    try:
        shutil.copytree(REPO_ROOT / "scripts" / "ci", dest / "scripts" / "ci", ignore=shutil.ignore_patterns("__pycache__"))
        if forged_plugin:
            _write(dest / "scripts" / "suite_performance" / "pytest_manual_deselect.py", FORGED_PLUGINS[forged_plugin])
        if forged:
            _write(dest / "scripts" / "ci" / "post_merge_fix_proof.py", FORGED_PROOF)
            plugin = dest / "scripts" / "ci" / "_lane_report_plugin.py"
            _write(plugin, plugin.read_text(encoding="utf-8") + FORGED_STATUS)
    except OSError as exc:
        message = f"cannot stage the head: {exc}"
        raise AssertionError(message) from exc
    return dest


# --------------------------------------------------------------------------- the executor
class ProofRun(WorkflowRun):
    """The executor with a two-source, recording ``actions/checkout``."""

    def __init__(self, workflow_path, default_dir, head_dir, scratch, extra_env, api_url):
        super().__init__(workflow_path, default_dir, scratch, extra_env, api_url)
        self.head_dir = Path(head_dir)
        self.checkouts = []

    def _uses(self, step, ctx, result, workspace):
        if step["uses"].split("@", 1)[0] != "actions/checkout":
            return super()._uses(step, ctx, result, workspace)
        with_ = {k: _expand(v, ctx) for k, v in (step.get("with") or {}).items()}
        ref, path = str(with_.get("ref") or "").strip(), str(with_.get("path") or ".")
        persist = str(with_.get("persist-credentials", "true")).strip().lower() != "false"
        self.checkouts.append({"job": result.job, "ref": ref, "path": path, "sparse": with_.get("sparse-checkout"), "persist": persist})
        if ref not in ("", HEAD_SHA):
            return "failure", f"checkout: the harness knows the default branch and {HEAD_SHA}, not ref {ref!r}", {}
        source, dest = (self.head_dir if ref else self.project_dir), workspace / path
        wanted = [p.strip().strip("/") for p in str(with_.get("sparse-checkout") or "").splitlines() if p.strip()] or [""]
        try:
            for rel in wanted:
                if (source / rel).exists():
                    shutil.copytree(source / rel, dest / rel, symlinks=True, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            config = ["[core]", "\trepositoryformatversion = 0"]
            if persist:  # what a real checkout leaves behind unless told not to
                config += ['[http "https://github.com/"]', f"\textraheader = AUTHORIZATION: basic {ctx.env.get('GITHUB_TOKEN', '')}"]
            _write(dest / ".git" / "config", "\n".join(config) + "\n")
        except (OSError, shutil.Error) as exc:
            return "failure", f"checkout failed: {exc}", {}
        return "success", f"checkout emulated from {'the PR head' if ref else 'the default branch'}: {wanted}", {}


@dataclass
class Proof:
    run: ProofRun
    prepare: JobResult
    prove: JobResult
    red: dict
    state: Path
    events: dict = field(default_factory=dict)  # job id -> observer events (empty unless observed)

    def ran(self):
        """The witness lines the lane tests wrote, sorted: exactly which tests executed (and how many times)."""
        log = self.state / "ran.log"
        return sorted(log.read_text(encoding="utf-8").split()) if log.is_file() else []

    def opened(self, job_id):
        return [e["path"] for e in self.events.get(job_id, []) if e["kind"] == "open"]

    def checkouts_of(self, job_id):
        return [c for c in self.run.checkouts if c["job"] == job_id]


def serve_history(svc, kind):
    """Serve the post-merge history (``red`` / ``dnc`` / ``green``) and an open notice; return the newest run."""
    now = datetime.now(timezone.utc)
    svc.reset()
    if kind == "green":
        newest = make_run(7, "success", hours_ago=1, now=now, head_sha=RED_HEAD)
        runs, jobs = [make_run(6, "success", hours_ago=4, now=now), newest], {}
    else:
        newest = make_run(7, "failure", hours_ago=2, now=now, head_sha=RED_HEAD)
        runs, jobs = [make_run(6, "success", hours_ago=4, now=now), newest], {newest["id"]: DNC_JOBS if kind == "dnc" else RED_JOBS}
    svc.runs, svc.jobs = runs, jobs
    stage = "empty_selection" if kind == "dnc" else None
    text = notice_description(newest["id"], failing=() if kind == "dnc" else (X_ID, Y_ID), stage=stage)
    svc.add_issue(NOTICE, title="Post-merge suite is red", body=text, labels=["post-merge-red"])
    return newest


def verdict_file(kind, run_id):
    """The red run's verdict file from the REAL producer."""
    if kind == "dnc":
        suite = import_production("scripts.ci.post_merge_suite")
        env = {"GITHUB_SHA": RED_HEAD, "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ID": str(run_id), "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER}
        return suite.build_verdict_file({"results": {}, "exitstatus": 5, "ran": 0, "expected": 0, "runner": "r"}, None, env)
    return make_verdict("red" if kind == "red" else "green", run_id=run_id, head_sha=RED_HEAD, failing=(X_ID, Y_ID) if kind == "red" else ())


def _events(base, name):
    return [e for part in sorted(base.glob(f"{name}.*")) for e in json.loads(part.read_text(encoding="utf-8"))]


@contextmanager
def driven(svc, *, body="Fixes #12", kind="red", head=None, observe=False, main_addopts=MAIN_ADDOPTS):
    """Execute ``Prepare fix proof`` then ``Post-merge fix proof`` of the real workflow; yield a :class:`Proof`."""
    if not WORKFLOW.is_file():
        message = f"not implemented: {WORKFLOW.relative_to(REPO_ROOT)}"
        raise AssertionError(message)
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        newest = serve_history(svc, kind)
        state, event = base / "state", base / "event.json"
        state.mkdir()
        payload = {"action": "opened", "number": PR_NUMBER, "repository": {"full_name": REPO},
                   "pull_request": {"number": PR_NUMBER, "body": body, "head": {"sha": HEAD_SHA, "ref": "fix/branch"}, "base": {"ref": "main"}}}
        _write(event, json.dumps(payload))
        env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "pull_request_target", "LANE_STATE_DIR": str(state),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(base / "observer") if observe else ""}
        if observe:
            _write(base / "observer" / "sitecustomize.py", OBSERVER)
        run = ProofRun(WORKFLOW, stage_main(base / "main", main_addopts), stage_head(base / "head", **(head or {})), base / "scratch", env, svc.url)
        written = base / "verdict.json"
        _write(written, json.dumps(verdict_file(kind, newest["id"])))
        run.artifacts.upload("post-merge-verdict", [("post-merge-verdict.json", written)])
        doc = load_workflow(WORKFLOW)
        prepare_id, prove_id = find_job(doc, PREPARE)[0], find_job(doc, PROVE)[0]
        run._base_env["HOLD_OBSERVER_LOG"] = str(base / "obs-prepare.json")
        prepare = run.execute_job(PREPARE)
        run._base_env["HOLD_OBSERVER_LOG"] = str(base / "obs-prove.json")
        prove = run.execute_job(PROVE, needs={prepare_id: prepare})
        proof = Proof(run, prepare, prove, newest, state)
        if observe:
            proof.events = {prepare_id: _events(base, "obs-prepare.json"), prove_id: _events(base, "obs-prove.json")}
        yield proof
