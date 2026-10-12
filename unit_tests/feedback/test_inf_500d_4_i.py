"""
MODULE: test_inf_500d_4_i
GOAL: RED tests for AC INF-500d-4-i -- when the enduring location cannot be
    determined, the report sink says so (loudly, once, non-zero, nothing on
    stdout, nothing created anywhere) rather than quietly using the disposable
    one; and when the declaration is usable the sink lands in the declared
    location whether or not version control exists.
AC: INF-500d-4-i (source_ac); depends on INF-500d-4-iii (declaration, ADR-069).

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    1. The deployed ``submit_feedback.py``, with no ``--jsonl``, takes its sink
       from ``feedback_sink`` in ``<output_root>/config/knowledge_sink.json``
       (read relative to its own deployed location, never via the ``__file__``
       walk for ``.claude/``, the current directory, or git).
    2. When that declaration is absent, unreadable, unparseable, lacks
       ``feedback_sink`` or ``operational_log_root``, holds a non-absolute value,
       or is stale (the enduring project root it records no longer exists), the
       script exits non-zero, prints NOTHING on stdout, prints exactly ONE stderr
       line naming the expected declaration path and which condition failed, and
       creates no file or directory anywhere (no sink, no directory above it, no
       sidecar id file, nothing under the current directory).
    3. It may create only the final log directory beneath a project root that
       already exists (the ordinary first write); it never creates the root.
    4. With a usable declaration it needs no git and no repository: the sink
       line names the declared file.
    5. ``emit_hook_finding.emit_finding`` stays failure-isolated: it returns
       ``False`` rather than raising, and the reason it surfaces is a refusal
       naming the declaration, never a "written" success.

REAL-ARTIFACT NOTE: every run is the REAL deployed script as a subprocess in a
    temp deployed layout; the declaration is written by the real build helper
    (and round-tripped to build the malformed variants). No build.py is spawned
    and nothing mocks the write.
"""
# @ac-tag: INF-500d-4-i

from __future__ import annotations

import re
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h

_SINK_PREFIX = "[submit_feedback] sink: "
_SIDECAR_GREP = re.compile(r"sidecar:[^ ]*feedback_id_[0-9]*.txt")

_EMIT_DRIVER = (
    "import importlib.util, json, sys\n"
    "spec = importlib.util.spec_from_file_location('ehf', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['ehf'] = m\n"
    "spec.loader.exec_module(m)\n"
    "try:\n"
    "    ret = m.emit_finding(hook_name='check_probe', outcome='warn',\n"
    "                         note='inf-500d-4-i probe', tags=['probe'])\n"
    "except BaseException as exc:\n"
    "    print('RAISED ' + type(exc).__name__)\n"
    "    sys.exit(3)\n"
    "print('RETURNED ' + json.dumps(ret))\n"
)


def _worktree(base: Path, name: str = "wt", *, git: bool = True) -> tuple[Path, Path, Path]:
    """A worktree-shaped project with a deployed layout; returns (project, out_root, cwd)."""
    project = base / name
    project.mkdir(parents=True)
    out_root = h.deploy_install(project, git=git)
    cwd = project / "work"
    cwd.mkdir()
    return project, out_root, cwd


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _assert_refusal(proc, declaration: Path, reason: str) -> None:
    assert proc.returncode != 0, f"refusal must be non-zero; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert proc.stdout == "", f"nothing may be printed on stdout (a caller would capture it as the id): {proc.stdout!r}"
    lines = h.stderr_lines(proc)
    assert len(lines) == 1, f"exactly one stderr line expected, got {lines!r}"
    assert str(declaration) in lines[0], f"the line must name the expected declaration {declaration}: {lines[0]!r}"
    assert re.search(reason, lines[0], re.IGNORECASE), f"the line must say which condition failed ({reason!r}): {lines[0]!r}"


def test_absent_declaration_refuses_and_writes_no_file_anywhere(tmp_path):
    # covers: INF-500d-4-i
    # angle: failure
    """No config/knowledge_sink.json: refuse, empty stdout, one stderr line, and the whole temp tree is unchanged."""
    project, out_root, cwd = _worktree(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    before = h.snapshot(tmp_path)

    proc = h.submit(out_root, cwd, tmpdir)

    _assert_refusal(proc, h.declaration_path(out_root), r"absent|not found|does not exist|no such file|no declaration")
    after = h.snapshot(tmp_path)
    assert after == before, f"a refused write must create nothing anywhere; created: {sorted(after - before)}"
    assert not (project / "debugging").exists(), "fell back to the __file__ walk for .claude/ (KI-FC-001's root cause)"
    assert not (cwd / "debugging").exists(), "fell back to a location derived from the current directory"


_BAD_DECLARATIONS = {
    "malformed_json": (r"unreadable|unparse?able|cannot be (?:read|parsed)|malformed|invalid json|could not parse"),
    "zero_byte_file": (r"unreadable|unparse?able|cannot be (?:read|parsed)|malformed|invalid json|could not parse"),
    "declaration_is_a_directory": (r"unreadable|cannot be read|could not read|is a directory|not a file|absent"),
    "not_an_object": (r"unreadable|unparse?able|malformed|missing|lacks|not an object|feedback_sink"),
    "missing_both_keys": (r"missing|lacks|no (?:'|\")?(?:feedback_sink|operational_log_root)"),
    "missing_feedback_sink_only": (r"missing|lacks|feedback_sink"),
    "missing_root_only": (r"missing|lacks|operational_log_root"),
    "relative_values": (r"not absolute|relative"),
    "relative_sink_only": (r"not absolute|relative"),
}


def _apply_bad_declaration(case: str, out_root: Path) -> None:
    path = h.declaration_path(out_root)
    if case == "malformed_json":
        path.write_text('{"feedback_sink": "/x/feedback.jsonl", ', encoding="utf-8")
    elif case == "zero_byte_file":
        path.write_text("", encoding="utf-8")
    elif case == "declaration_is_a_directory":
        path.unlink()
        path.mkdir()
    elif case == "not_an_object":
        path.write_text("[]\n", encoding="utf-8")
    elif case == "missing_both_keys":
        h.rewrite_declaration(out_root, feedback_sink=None, operational_log_root=None)
    elif case == "missing_feedback_sink_only":
        h.rewrite_declaration(out_root, feedback_sink=None)
    elif case == "missing_root_only":
        h.rewrite_declaration(out_root, operational_log_root=None)
    elif case == "relative_values":
        h.rewrite_declaration(out_root, operational_log_root="debugging/logs",
                              feedback_sink="debugging/logs/feedback.jsonl")
    elif case == "relative_sink_only":
        h.rewrite_declaration(out_root, feedback_sink="feedback.jsonl")
    else:  # pragma: no cover - guards a typo in the table above
        raise AssertionError(case)


@pytest.mark.parametrize("case", sorted(_BAD_DECLARATIONS))
def test_unreadable_keyless_or_relative_declaration_each_refuses(tmp_path, case):
    # covers: INF-500d-4-i
    # angle: failure
    """Each unusable declaration refuses like the absent case, naming the condition; nothing is created."""
    project, out_root, cwd = _worktree(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    enduring = tmp_path / "enduring"
    enduring.mkdir()
    h.declare(out_root, enduring / "logs")
    _apply_bad_declaration(case, out_root)
    before = h.snapshot(tmp_path)

    proc = h.submit(out_root, cwd, tmpdir)

    _assert_refusal(proc, h.declaration_path(out_root), _BAD_DECLARATIONS[case])
    after = h.snapshot(tmp_path)
    assert after == before, f"{case}: a refused write must create nothing; created: {sorted(after - before)}"
    assert not (enduring / "logs").exists(), f"{case}: the declared log directory must not be created on a refusal"


def test_stale_declaration_refuses_without_creating_the_enduring_root(tmp_path):
    # covers: INF-500d-4-i
    # angle: boundary
    """A declared root whose project root is gone refuses and creates no directory on the way; a live one still writes."""
    project, out_root, cwd = _worktree(tmp_path)
    tmpdir = _tmpdir(tmp_path)

    gone = tmp_path / "gone_project"
    h.declare(out_root, gone / "debugging" / "logs")
    before = h.snapshot(tmp_path)
    stale = h.submit(out_root, cwd, tmpdir)
    _assert_refusal(stale, h.declaration_path(out_root), r"stale|no longer exists|does not exist")
    assert h.snapshot(tmp_path) == before, "a stale declaration must create nothing"
    assert not gone.exists(), "mkdir(parents=True) on the declared directory turned a stale install into a healthy-looking empty one"

    # Control (the ordinary first write): the project root exists, only the final log directory is missing.
    live = tmp_path / "live_project"
    (live / "debugging").mkdir(parents=True)
    logs = live / "debugging" / "logs"
    h.declare(out_root, logs)
    before_live = h.snapshot(live)
    ok = h.submit(out_root, cwd, tmpdir)
    assert ok.returncode == 0, f"a live root must still accept the first write: {ok.stderr!r}"
    created = h.snapshot(live) - before_live
    assert created == {str(logs), str(logs / "feedback.jsonl")}, f"only the final log directory and the sink may appear: {sorted(created)}"
    assert ok.stdout.strip() in (logs / "feedback.jsonl").read_text(encoding="utf-8")


def test_project_without_version_control_writes_to_the_declared_root(tmp_path):
    # covers: INF-500d-4-i
    # angle: criterion
    """No .git and no git on PATH: a usable declaration still yields a write at the declared, non-workspace sink."""
    project, out_root, cwd = _worktree(tmp_path, git=False)
    tmpdir = _tmpdir(tmp_path)
    enduring = tmp_path / "enduring"
    enduring.mkdir()
    root = enduring / "logs"
    h.declare(out_root, root)
    before = h.snapshot(project)

    proc = h.submit(out_root, cwd, tmpdir, path=h.empty_bin_path(tmp_path))

    assert proc.returncode == 0, f"version control must play no part in resolution: {proc.stderr!r}"
    assert re.match(h.FEEDBACK_ID_RE, proc.stdout.strip()), f"stdout must be the id alone: {proc.stdout!r}"
    sink_lines = [line for line in proc.stderr.splitlines() if line.startswith(_SINK_PREFIX)]
    assert len(sink_lines) == 1, f"exactly one sink line expected: {proc.stderr!r}"
    reported = Path(sink_lines[0][len(_SINK_PREFIX):])
    assert reported == (root / "feedback.jsonl").resolve(), f"sink must be the declared feedback_sink, got {reported}"
    assert project.resolve() not in reported.parents, "the reported sink lies inside the disposable workspace"
    assert proc.stdout.strip() in reported.read_text(encoding="utf-8")
    assert h.snapshot(project) == before, "nothing may be created under the workspace the caller ran from"


def test_plain_checkout_and_worktree_drive_resolve_the_same_sink(tmp_path):
    # covers: INF-500d-4-i
    # angle: seam
    """A plain-checkout declaration and a worktree declaration inheriting its root both name the identical file."""
    tmpdir = _tmpdir(tmp_path)
    main_project = tmp_path / "main"
    main_project.mkdir()
    main_out = h.deploy_install(main_project)
    (main_project / "debugging").mkdir()
    h.declare(main_out)  # the way the build phase writes it for a plain checkout
    recorded_root = Path(h.read_declaration(main_out)["operational_log_root"])

    wt_project = tmp_path / "wt"
    wt_project.mkdir()
    wt_out = h.deploy_install(wt_project)
    h.declare(wt_out, recorded_root)  # the way the bootstrap does it: inherit the recorded root
    (main_project / "work").mkdir()
    (wt_project / "work").mkdir()
    wt_before = h.snapshot(wt_project)

    from_main = h.submit(main_out, main_project / "work", tmpdir, note="plain")
    from_wt = h.submit(wt_out, wt_project / "work", tmpdir, note="worktree")

    sinks = []
    for label, proc in (("plain checkout", from_main), ("worktree", from_wt)):
        assert proc.returncode == 0, f"{label}: {proc.stderr!r}"
        lines = [line for line in proc.stderr.splitlines() if line.startswith(_SINK_PREFIX)]
        assert len(lines) == 1, f"{label}: one sink line expected: {proc.stderr!r}"
        sinks.append(Path(lines[0][len(_SINK_PREFIX):]))
    expected = (recorded_root / "feedback.jsonl").resolve()
    assert sinks == [expected, expected], f"both drives must name the identical absolute file {expected}: {sinks}"
    ids = {from_main.stdout.strip(), from_wt.stdout.strip()}
    assert {r["feedback_id"] for r in h.read_records(expected)} == ids
    assert h.snapshot(wt_project) == wt_before, "the worktree drive created a second, divergent location"


def test_refusal_keeps_the_verdict_path_and_uses_a_legible_reason(tmp_path):
    # covers: INF-500d-4-i
    # angle: discrimination
    """emit_finding against a layout with no declaration returns False (never raises) and surfaces a refusal, not a 'written' reason."""
    project, out_root, cwd = _worktree(tmp_path)
    tmpdir = _tmpdir(tmp_path)
    driver_target = str(out_root / "scripts" / "feedback" / "emit_hook_finding.py")
    before = h.snapshot(tmp_path)

    refused = h.run_code(_EMIT_DRIVER, [driver_target], cwd, tmpdir)

    assert refused.returncode == 0, f"emit_finding must not raise into its caller: {refused.stdout!r} {refused.stderr!r}"
    assert refused.stdout.strip().splitlines() == ["RETURNED false"], f"expected a clean False and no id on stdout: {refused.stdout!r}"
    assert str(h.declaration_path(out_root)) in refused.stderr, f"the reason must name the declaration: {refused.stderr!r}"
    for wrong in (r"written but", r"not captured", r"uncited", r"identifier was not captured", r"sidecar:", re.escape(_SINK_PREFIX)):
        assert not re.search(wrong, refused.stderr, re.IGNORECASE), f"a refusal must not read as 'written' ({wrong!r}): {refused.stderr!r}"
    assert h.snapshot(tmp_path) == before, "the isolated failure still must not have written anywhere"

    # Control: the same entry point succeeds once a declaration exists, so the False above is the declaration's doing.
    enduring = tmp_path / "enduring"
    enduring.mkdir()
    h.declare(out_root, enduring / "logs")
    accepted = h.run_code(_EMIT_DRIVER, [driver_target], cwd, tmpdir)
    assert accepted.stdout.strip().splitlines()[-1] == "RETURNED true", f"{accepted.stdout!r} {accepted.stderr!r}"
    assert len(h.read_records(enduring / "logs" / "feedback.jsonl")) == 1


def test_inf_500d_4_i_reachable_from_entry_point(tmp_path):
    # covers: INF-500d-4-i
    # angle: reachability
    """The signoff recipe (stdout capture, then the sidecar grep) must come out empty on a refusal and populated on success."""
    project, out_root, cwd = _worktree(tmp_path)
    tmpdir = _tmpdir(tmp_path)

    refused = h.submit(out_root, cwd, tmpdir)  # CLI via subprocess, exactly signoff section 2a Call 1

    captured_id = refused.stdout.strip()  # Call 1: read the id from stdout
    recovered = _SIDECAR_GREP.findall(refused.stderr)  # Call 2: the sidecar fallback grep
    assert refused.returncode != 0
    assert captured_id == "", "a refusal must leave the caller with no id, so it records (submit-failed)"
    assert recovered == [], f"the sidecar recovery grep must find nothing after a refusal: {recovered!r}"
    assert not list(tmpdir.glob("feedback_id_*.txt")), "a refusal must not leave a sidecar id file behind"

    # Control: with a declaration the very same recipe recovers a real id, so the empty result above is meaningful.
    enduring = tmp_path / "enduring"
    enduring.mkdir()
    h.declare(out_root, enduring / "logs")
    accepted = h.submit(out_root, cwd, tmpdir)
    assert accepted.returncode == 0, accepted.stderr
    assert len(_SIDECAR_GREP.findall(accepted.stderr)) == 1
    assert re.match(h.FEEDBACK_ID_RE, accepted.stdout.strip())
