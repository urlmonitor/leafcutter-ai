"""
MODULE: test_inf_500d_4_iii
GOAL: Tests for AC INF-500d-4-iii -- every per-drive workspace is built pointing at the same enduring
    log location as the project it belongs to.
AC: INF-500d-4-iii (source_ac); design: ADR-069.

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    1. ``build_knowledge_sink_declaration`` (scripts/build_phases_knowledge.py)
       writes ``<output_root>/config/knowledge_sink.json`` with FOUR keys:
       ``operational_log_root`` (abs dir), ``feedback_sink``
       (``<root>/feedback.jsonl``), ``knowledge_emission_sink``
       (``<root>/knowledge_emissions.jsonl``), ``operational_telemetry_stream``
       (``<root>/agent_telemetry.jsonl``). Default root is
       ``<target_root.parent>/debugging/logs`` (byte-identical to today for the
       two pre-existing keys).
    2. ``build.py --log-root <ABS>`` records ``<ABS>`` verbatim as the root. A
       non-absolute value makes build.py exit non-zero, naming the value and
       the word "absolute" or "relative", and writes no declaration.
    3. The DEPLOYED workspace maker (``worktree.py ensure``, run as a separate process) reads
       ``<install>/config/knowledge_sink.json`` of the install that deployed it and builds the
       workspace with ``--log-root <root>`` (``operational_log_root``, else the parent of
       ``knowledge_emission_sink``). When that cannot be read it still answers ok, builds with
       ``--no-log-root`` (the workspace records ``{}``) and prints a stderr WARNING naming the path
       it tried and why. The retired ``setup_ticket_worktree.py`` bootstrap no longer exists.
    4. Location query CLI: the DEPLOYED
       ``<output_root>/scripts/knowledge/sink_resolution.py --print-location
       {root|feedback|telemetry|knowledge}`` -- exit 0 and exactly one absolute
       path on stdout; side-effect free; on absent declaration or missing key
       exit non-zero, nothing on stdout, the expected declaration path on
       stderr.
    5. ``scripts/ci/check_sink_parity.py --target-dir <deployed project>`` also
       fails (stdout/stderr naming the offending key) for a missing or
       relative ``operational_log_root`` / ``feedback_sink``, a file-valued key
       not directly under the root, or ``feedback_sink`` equal to another
       stream.

REAL-ARTIFACT NOTE: the maker tests run the REAL deployed maker (a private copy inside its own install, so
    the install's declaration can be varied) against a real bare hub and project clone; the project's
    declaration is written by the package's own helper. The only stand-in is the fixture project's
    ``scripts/build.py`` (it records its argv and writes the declaration the flags ask for; a real build
    costs ~60s, see CLAUDE.md "Tests must not spawn their own build.py"). The consumers of the declaration
    (location query, feedback writer, guard-root resolver, parity check) are verbatim files copied from the
    shared deployed layout.

Not covered here (kept out for build-cost reasons): the symlinked-workspace no-regression case and the
    NOTE text. The older-build retry lives in test_inf_500d_4_iii_older_worktree_build.py; the reader's
    reason wording in test_inf_500d_4_iii_reader.py.
"""
# @ac-tag: INF-500d-4-iii

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout
from unit_tests.portability import _inf_500d_4_iii_support as sup

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases_knowledge import build_knowledge_sink_declaration  # noqa: E402

_BUILD_PY = _SCRIPTS_DIR / "build.py"
_SINK_RESOLUTION_SRC = _SCRIPTS_DIR / "knowledge" / "sink_resolution.py"
_PARITY_CHECK = _SCRIPTS_DIR / "ci" / "check_sink_parity.py"

_BUILD_TIMEOUT = 400
_QUERY_TIMEOUT = 60

_FILE_KEYS = ("feedback_sink", "knowledge_emission_sink", "operational_telemetry_stream")
_STREAM_FILES = {
    "feedback": "feedback.jsonl",
    "telemetry": "agent_telemetry.jsonl",
    "knowledge": "knowledge_emissions.jsonl",
}
_WARNING = re.compile(r"WARNING: no enduring log root readable from (.+?) \((.+)\); logs written in this "
                      r"workspace will not survive its removal\.")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _seed_skills_config(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "skills_config.json").write_text(
        json.dumps({"_comment": "minimal config for INF-500d-4-iii tests"}), encoding="utf-8"
    )


def _declaration(output_root: Path) -> dict:
    path = output_root / "config" / "knowledge_sink.json"
    assert path.is_file(), f"expected a declaration at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_declaration(output_root: Path, data: dict) -> Path:
    path = output_root / "config" / "knowledge_sink.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _full_declaration(root: Path) -> dict:
    return {
        "operational_log_root": str(root),
        "feedback_sink": str(root / "feedback.jsonl"),
        "knowledge_emission_sink": str(root / "knowledge_emissions.jsonl"),
        "operational_telemetry_stream": str(root / "agent_telemetry.jsonl"),
    }


def _query(output_root: Path, name: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-B",
         str(output_root / "scripts" / "knowledge" / "sink_resolution.py"),
         "--print-location", name],
        capture_output=True, text=True, timeout=_QUERY_TIMEOUT, cwd=str(cwd), env=env, check=False,
    )


def _snapshot(*roots: Path) -> set[str]:
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
            for name in (*dirnames, *filenames):
                seen.add(os.path.join(dirpath, name))
    return seen

@pytest.fixture(scope="module")
def inherited_worktree(tmp_path_factory):
    """A workspace the deployed maker made from a project install whose recorded root is R."""
    base = tmp_path_factory.mktemp("inf500d4iii_inherit")
    root = base / "enduring" / "logs"
    install, maker = sup.project_install(base)
    sup.write_real_declaration(install, root)
    run = sup.ensure_workspace(base, "inherit", maker)
    if run["workspace"] is not None:
        sup.copy_deployed_consumers(run["workspace"])
    return {"install": install, "wt": run["workspace"], "root": root, "run": run, "base": base}


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_declaration_names_one_absolute_root_for_every_log(tmp_path):
    # covers: INF-500d-4-iii
    # angle: criterion
    """Declaration carries operational_log_root + feedback_sink; all absolute; file keys sit under the root."""
    output_root = tmp_path / "proj" / ".leafcutter"
    build_knowledge_sink_declaration(output_root, {}, False, True)
    data = _declaration(output_root)
    assert "operational_log_root" in data, f"no operational_log_root in {sorted(data)}"
    assert "feedback_sink" in data, f"no feedback_sink in {sorted(data)}"
    for key, value in data.items():
        assert Path(value).is_absolute(), f"{key}={value!r} is not absolute"
    root = Path(data["operational_log_root"])
    for key in _FILE_KEYS:
        assert Path(data[key]).parent == root, f"{key} not directly under {root}"
    assert len({data[k] for k in _FILE_KEYS}) == 3, "file-valued keys must be distinct"


def test_plain_build_keeps_existing_stream_values_byte_identical(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """No inherited root: pre-existing values unchanged AND the new root key names that same directory."""
    output_root = tmp_path / "proj" / ".leafcutter"
    build_knowledge_sink_declaration(output_root, {}, False, True)
    data = _declaration(output_root)
    logs = tmp_path / "proj" / "debugging" / "logs"
    assert data["knowledge_emission_sink"] == str(logs / "knowledge_emissions.jsonl")
    assert data["operational_telemetry_stream"] == str(logs / "agent_telemetry.jsonl")
    # Passes-today guard: the new key must exist and agree, or this test is vacuous.
    assert data.get("operational_log_root") == str(logs)
    assert data.get("feedback_sink") == str(logs / "feedback.jsonl")


def test_inherited_root_is_recorded_verbatim_and_a_relative_one_is_refused(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """build.py --log-root ABS records it verbatim for every key; a relative one is refused, nothing written."""
    abs_root = tmp_path / "enduring" / "logs"
    good = tmp_path / "good"
    _seed_skills_config(good)
    ok = subprocess.run(
        [sys.executable, str(_BUILD_PY), "--target-dir", str(good), "--log-root", str(abs_root)],
        capture_output=True, text=True, timeout=_BUILD_TIMEOUT, check=False,
    )
    assert ok.returncode == 0, f"build with absolute --log-root failed:\n{ok.stdout[-1500:]}\n{ok.stderr[-1500:]}"
    data = _declaration(good / ".leafcutter")
    assert data.get("operational_log_root") == str(abs_root)
    for key, name in (("feedback_sink", "feedback.jsonl"),
                      ("knowledge_emission_sink", "knowledge_emissions.jsonl"),
                      ("operational_telemetry_stream", "agent_telemetry.jsonl")):
        assert data.get(key) == str(abs_root / name), f"{key} not recorded under inherited root"

    bad = tmp_path / "bad"
    _seed_skills_config(bad)
    refused = subprocess.run(
        [sys.executable, str(_BUILD_PY), "--target-dir", str(bad), "--log-root", "logs-dir/sub"],
        capture_output=True, text=True, timeout=_BUILD_TIMEOUT, check=False,
    )
    combined = refused.stdout + refused.stderr
    assert refused.returncode != 0, "relative --log-root must exit non-zero"
    assert "logs-dir/sub" in combined, "refusal must name the offending value"
    assert re.search(r"absolute|relative", combined, re.IGNORECASE), "refusal must say why"
    assert not (bad / ".leafcutter" / "config" / "knowledge_sink.json").exists(), \
        "a refused build must write no declaration"


def test_maker_workspace_inherits_the_projects_durable_log_root(inherited_worktree):
    # covers: INF-500d-4-iii
    # angle: deployed
    """The maker's ok answer names a workspace whose declaration records the project's root R, every sink directly under it."""
    fx, run = inherited_worktree, inherited_worktree["run"]
    assert (run["answer"].get("status"), run["exit_code"]) == ("ok", 0), run["answer"]
    data = sup.declaration_of(fx["wt"])
    assert data.get("operational_log_root") == str(fx["root"])
    for key, name in (("feedback_sink", "feedback.jsonl"), ("knowledge_emission_sink", "knowledge_emissions.jsonl"),
                      ("operational_telemetry_stream", "agent_telemetry.jsonl")):
        assert data.get(key) == str(fx["root"] / name), f"{key}={data.get(key)!r} not directly under R"
    for key, value in data.items():
        assert not value.startswith(str(fx["wt"])), f"{key} lies under the workspace"
        # a wrong version deriving the root from the project's path lands here
        assert not value.startswith(str(run["project"])), f"{key} derived from the project path"
    assert len(run["calls"]) == 1, f"one build expected, saw {run['calls']}"
    argv = run["calls"][0]
    assert "--no-log-root" not in argv and argv[argv.index("--log-root") + 1] == str(fx["root"]), argv
    assert "no enduring log root" not in run["stderr"], run["stderr"]


def test_unreadable_project_root_builds_with_no_log_root_and_warns(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """Declaration absent or relative: still ok, the workspace records {}, the build got --no-log-root, the warning names path + reason."""
    relative = json.dumps({"operational_log_root": "debugging/logs", "feedback_sink": "debugging/logs/feedback.jsonl"})
    problems: list[str] = []
    for case, text in (("absent", None), ("relative", relative)):
        base = tmp_path / case
        base.mkdir()
        install, maker = sup.project_install(base)
        if text is not None:
            sup.write_declaration(install, text)
        tried = install / "config" / "knowledge_sink.json"
        run = sup.ensure_workspace(base, f"unreadable-{case}", maker)
        if (run["answer"].get("status"), run["exit_code"]) != ("ok", 0) or run["workspace"] is None:
            problems.append(f"[{case}] the answer must stay ok: {run['answer']}")
            continue
        if sup.declaration_of(run["workspace"]) != {}:
            problems.append(f"[{case}] workspace must record the empty declaration: {sup.declaration_of(run['workspace'])}")
        argv = run["calls"][0] if len(run["calls"]) == 1 else []
        if "--no-log-root" not in argv or "--log-root" in argv:
            problems.append(f"[{case}] the single build must carry --no-log-root only: {run['calls']}")
        found = _WARNING.search(run["stderr"])
        if not found or found.group(1) != str(tried) or not found.group(2).strip():
            problems.append(f"[{case}] warning must name {tried} and a reason; stderr:\n{run['stderr'][-1200:]}")
        elif case == "relative" and "absolute" not in found.group(2):
            problems.append(f"[{case}] reason must say the root is not absolute: {found.group(2)!r}")
    assert problems == [], "\n".join(problems)


def test_legacy_two_key_declaration_is_inherited_from_the_parent_of_the_emission_sink(tmp_path):
    # covers: INF-500d-4-iii
    # angle: boundary
    """A pre-feature declaration (no operational_log_root) still hands the build the parent of knowledge_emission_sink."""
    root = tmp_path / "enduring" / "logs"
    install, maker = sup.project_install(tmp_path)
    sup.write_declaration(install, json.dumps({"knowledge_emission_sink": str(root / "knowledge_emissions.jsonl"),
                                               "operational_telemetry_stream": str(root / "agent_telemetry.jsonl")}))
    run = sup.ensure_workspace(tmp_path, "legacy", maker)
    assert (run["answer"].get("status"), run["exit_code"]) == ("ok", 0), run["answer"]
    assert sup.declaration_of(run["workspace"]).get("operational_log_root") == str(root)
    assert "no enduring log root" not in run["stderr"], run["stderr"]


def test_config_and_guard_roots_still_resolve_to_the_worktree(inherited_worktree):
    # covers: INF-500d-4-iii
    # angle: seam
    """In one worktree: config -> its .leafcutter/config, guard root -> its toplevel, log root -> R."""
    fx = inherited_worktree
    wt = fx["wt"]
    out_root = wt / ".leafcutter"
    probe = (
        "import importlib.util, json, sys\n"
        "def load(p, n):\n"
        "    s = importlib.util.spec_from_file_location(n, p)\n"
        "    m = importlib.util.module_from_spec(s); sys.modules[n] = m; s.loader.exec_module(m); return m\n"
        "fb = load(sys.argv[1], 'submit_feedback')\n"
        "rr = load(sys.argv[2], '_resolve_root')\n"
        "print(json.dumps({'config': str(fb._find_config_root().resolve()),"
        " 'guard': str(rr.find_project_root().resolve())}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", probe,
         str(out_root / "scripts" / "feedback" / "submit_feedback.py"),
         str(out_root / "scripts" / "commit_guardian" / "_resolve_root.py")],
        capture_output=True, text=True, timeout=_QUERY_TIMEOUT, cwd=str(wt), check=False,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr[-1500:]}"
    answers = json.loads(proc.stdout.strip().splitlines()[-1])
    assert answers["config"] == str((out_root / "config").resolve())
    assert answers["guard"] == str(wt.resolve())
    logq = _query(out_root, "root", wt)
    assert logq.returncode == 0, f"location query failed: {logq.stderr[-800:]}"
    assert logq.stdout.strip() == str(fx["root"])
    assert len({answers["config"], answers["guard"], logq.stdout.strip()}) == 3


def test_location_query_reports_each_stream_and_creates_nothing(inherited_worktree, tmp_path):
    # covers: INF-500d-4-iii
    # angle: reachability
    """The deployed query prints identical absolute answers from two cwds and creates nothing."""
    fx = inherited_worktree
    out_root = fx["wt"] / ".leafcutter"
    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()
    root_existed = fx["root"].exists()
    before = _snapshot(fx["wt"], other_cwd)
    expected = {"root": str(fx["root"])}
    expected.update({name: str(fx["root"] / fname) for name, fname in _STREAM_FILES.items()})
    for name, want in expected.items():
        first = _query(out_root, name, fx["wt"])
        second = _query(out_root, name, other_cwd)
        for proc in (first, second):
            assert proc.returncode == 0, f"{name}: rc={proc.returncode} stderr={proc.stderr[-500:]}"
            assert proc.stdout.strip() == want, f"{name}: got {proc.stdout!r}, want {want!r}"
            assert len(proc.stdout.strip().splitlines()) == 1
            assert Path(proc.stdout.strip()).is_absolute()
    assert _snapshot(fx["wt"], other_cwd) == before, "query created files or directories"
    assert fx["root"].exists() == root_existed, "query created the log root"


def test_location_query_refuses_when_the_declaration_is_absent(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """No declaration (and a keyless one): non-zero, empty stdout, expected declaration path on stderr."""
    out_root = tmp_path / "out"
    target = out_root / "scripts" / "knowledge"
    target.mkdir(parents=True)
    shutil.copy2(_SINK_RESOLUTION_SRC, target / "sink_resolution.py")
    declaration = out_root / "config" / "knowledge_sink.json"
    proc = _query(out_root, "root", tmp_path)
    assert proc.returncode != 0, "absent declaration must refuse"
    assert proc.stdout == "", f"nothing may be printed on stdout, got {proc.stdout!r}"
    assert str(declaration) in proc.stderr
    # Pre-feature declaration: the feedback key is missing -> same refusal semantics.
    _write_declaration(out_root, {"knowledge_emission_sink": str(tmp_path / "x" / "k.jsonl")})
    keyless = _query(out_root, "feedback", tmp_path)
    assert keyless.returncode != 0
    assert keyless.stdout == ""
    assert str(declaration) in keyless.stderr


@pytest.mark.parametrize("case", ["split", "relative_root", "missing_root", "duplicate_stream"])
def test_sink_parity_check_rejects_a_split_or_relative_log_root(tmp_path, case):
    # covers: INF-500d-4-iii
    # angle: failure
    """Each bad declaration fails check_sink_parity naming the key; the correct one still passes."""
    src = ensure_deployed_layout() / ".leafcutter"
    target = tmp_path / "proj"
    deployed = target / ".leafcutter"
    for rel in (("skills", "signoff"), ("agents",), ("scripts", "knowledge"), ("config",)):
        origin = src.joinpath(*rel)
        if origin.is_dir():
            shutil.copytree(origin, deployed.joinpath(*rel), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__"))
    root = tmp_path / "enduring" / "logs"
    good = _full_declaration(root)
    variants = {
        "split": ({**good, "feedback_sink": str(tmp_path / "elsewhere" / "feedback.jsonl")}, "feedback_sink"),
        "relative_root": ({**good, "operational_log_root": "debugging/logs"}, "operational_log_root"),
        "missing_root": ({k: v for k, v in good.items() if k != "operational_log_root"}, "operational_log_root"),
        "duplicate_stream": ({**good, "feedback_sink": good["operational_telemetry_stream"]}, "feedback_sink"),
    }
    _write_declaration(deployed, good)
    control = subprocess.run([sys.executable, str(_PARITY_CHECK), "--target-dir", str(target)],
                             capture_output=True, text=True, timeout=_QUERY_TIMEOUT, check=False)
    assert control.returncode == 0, f"correct declaration must pass:\n{control.stdout}\n{control.stderr}"
    bad, key = variants[case]
    _write_declaration(deployed, bad)
    proc = subprocess.run([sys.executable, str(_PARITY_CHECK), "--target-dir", str(target)],
                          capture_output=True, text=True, timeout=_QUERY_TIMEOUT, check=False)
    assert proc.returncode == 1, f"{case}: expected failure, rc={proc.returncode}\n{proc.stdout}"
    assert key in proc.stdout + proc.stderr, f"{case}: output must name {key}"
