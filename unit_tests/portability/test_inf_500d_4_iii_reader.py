"""
MODULE: test_inf_500d_4_iii_reader
GOAL: Pure-unit tests for the stdlib-only module ``templates/scripts/worktree_log_root.py`` (not yet written):
    the reader of the project install's recorded log root and the one-retry build runner the workspace
    maker calls (AC INF-500d-4-iii, ADR-069 section 3; architect-review of ticket 17).
BUSINESS CONTEXT: The retired bootstrap read ``operational_log_root`` (else the parent of
    ``knowledge_emission_sink``) from the project's declaration and handed it to the workspace's build,
    warning loudly when it could not. The maker now does this with the install that deployed it. The
    deployed proofs (test_inf_500d_4_iii*.py) cover the whole path; these pin the reader's rules and the
    warning's wording without a subprocess maker.

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    * ``inherited_log_root_args(install_root) -> (flags, warning)``: reads
      ``<install_root>/config/knowledge_sink.json``. A readable absolute root gives
      ``(["--log-root", root], None)``; anything else gives ``(["--no-log-root"], text)`` with
      ``text == "WARNING: no enduring log root readable from <path> (<why>); logs written in this
      workspace will not survive its removal."`` where ``<path>`` is exactly that declaration path.
      ``<why>`` is the failure's own text; a relative root says it is "not an absolute path"; a
      declaration with neither key names ``knowledge_emission_sink``. Never raises, never writes.
    * ``run_with_inherited_log_root(cmd, flags, **run_kwargs)``: runs ``cmd + flags`` once; only when
      flags were given AND the run exits 2 AND its stderr says ``unrecognized arguments`` it runs
      ``cmd`` again without them, after printing a WARNING (to stderr) naming the rejected flag and
      that the workspace has no durable log root. Returns the last ``CompletedProcess``.
"""
# @ac-tag: INF-500d-4-iii

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import re
import sys
from pathlib import Path

from unit_tests.portability import _inf_500d_4_iii_support as sup

_TEMPLATES_SCRIPTS = Path(__file__).resolve().parents[2] / "templates" / "scripts"
_WARNING = re.compile(r"^WARNING: no enduring log root readable from (?P<path>.+?) \((?P<why>.+)\); "
                      r"logs written in this workspace will not survive its removal\.$")

_CHILD = '''\
import json, os, sys
with open(os.environ["CHILD_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
mode = os.environ["CHILD_MODE"]
if mode == "old" and any(a in ("--log-root", "--no-log-root") for a in sys.argv[1:]):
    sys.stderr.write("build.py: error: unrecognized arguments: " + " ".join(sys.argv[1:]) + "\\n")
    sys.exit(2)
if mode == "always2":
    sys.stderr.write("build.py: error: unrecognized arguments: --whatever\\n")
    sys.exit(2)
if mode == "other2":
    sys.stderr.write("build.py: error: the target directory is unusable\\n")
    sys.exit(2)
if mode == "fail1":
    sys.stderr.write("build.py: error: unrecognized arguments: --log-root\\n")
    sys.exit(1)
'''


def _wlr():
    """The module under test, imported from the template source (stdlib-only, no deploy needed)."""
    if str(_TEMPLATES_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_TEMPLATES_SCRIPTS))
    return importlib.import_module("worktree_log_root")


def _declaration_path(install: Path) -> Path:
    return install / "config" / "knowledge_sink.json"


def _unreadable(install: Path):
    """Run the reader on *install*, assert the fail-closed shape, return the warning's ``why``."""
    flags, warning = _wlr().inherited_log_root_args(install)
    assert list(flags) == ["--no-log-root"], flags
    found = _WARNING.match(warning or "")
    assert found, f"warning does not keep the retired wording: {warning!r}"
    assert found.group("path") == str(_declaration_path(install)), f"warning must name the path tried: {warning!r}"
    assert found.group("why").strip(), warning
    return found.group("why")


def test_absolute_root_is_passed_verbatim_and_nothing_is_warned(tmp_path):
    # covers: INF-500d-4-iii
    # angle: criterion
    """A declaration written by the package's own helper hands its operational_log_root through unchanged."""
    root = tmp_path / "enduring" / "logs"
    sup.write_real_declaration(tmp_path, root)
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    flags, warning = _wlr().inherited_log_root_args(tmp_path)
    assert (list(flags), warning) == (["--log-root", str(root)], None)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == before, "the reader wrote something"


def test_operational_log_root_wins_over_the_emission_sink_parent(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """When both are present the recorded root is used, not the parent of the emission sink (wrong version)."""
    root, elsewhere = tmp_path / "root" / "logs", tmp_path / "elsewhere" / "logs"
    sup.write_declaration(tmp_path, json.dumps({"operational_log_root": str(root),
                                                "knowledge_emission_sink": str(elsewhere / "knowledge_emissions.jsonl")}))
    flags, warning = _wlr().inherited_log_root_args(tmp_path)
    assert (list(flags), warning) == (["--log-root", str(root)], None)


def test_legacy_declaration_gives_the_parent_of_the_emission_sink(tmp_path):
    # covers: INF-500d-4-iii
    # angle: boundary
    """A pre-feature (two-key) declaration is accepted: ADR-069 section 3, as the retired bootstrap did."""
    root = tmp_path / "enduring" / "logs"
    sup.write_declaration(tmp_path, json.dumps({"knowledge_emission_sink": str(root / "knowledge_emissions.jsonl"),
                                                "operational_telemetry_stream": str(root / "agent_telemetry.jsonl")}))
    flags, warning = _wlr().inherited_log_root_args(tmp_path)
    assert (list(flags), warning) == (["--log-root", str(root)], None)


def test_relative_root_is_refused_with_the_reason_named(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """A relative recorded root never reaches the build; the warning says it is not an absolute path."""
    sup.write_declaration(tmp_path, json.dumps({"operational_log_root": "debugging/logs"}))
    assert "not an absolute path" in _unreadable(tmp_path)


def test_relative_legacy_sink_is_refused(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """The parent of a relative emission sink is relative too: refused, not resolved against any directory."""
    sup.write_declaration(tmp_path, json.dumps({"knowledge_emission_sink": "debugging/logs/knowledge_emissions.jsonl"}))
    assert "not an absolute path" in _unreadable(tmp_path)


def test_declaration_with_neither_key_names_the_missing_key(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """Keyless declaration: warned, and the reason names the key the fallback needed."""
    sup.write_declaration(tmp_path, json.dumps({"feedback_sink": str(tmp_path / "feedback.jsonl")}))
    assert "knowledge_emission_sink" in _unreadable(tmp_path)


def test_absent_declaration_is_warned_with_the_path_tried(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """No declaration at all: fail-closed with the path named (never derived from the install's location)."""
    _unreadable(tmp_path)


def test_a_directory_in_place_of_the_declaration_is_warned(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """The declaration path is a directory (unreadable): typed OSError, warned, never raised."""
    _declaration_path(tmp_path).mkdir(parents=True)
    _unreadable(tmp_path)


def test_unparseable_and_non_object_declarations_are_warned(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """Garbage text, a JSON list and a non-string root each end in the same warning, never an exception."""
    problems = []
    for name, text in (("garbage", "{not json"), ("list", "[]"), ("number_root", json.dumps({"operational_log_root": 5}))):
        sup.write_declaration(tmp_path, text)
        try:
            _unreadable(tmp_path)
        except AssertionError as exc:
            problems.append(f"[{name}] {exc}")
    assert problems == [], "\n".join(problems)


def _child(tmp_path: Path, mode: str):
    script = tmp_path / "child.py"
    script.write_text(_CHILD, encoding="utf-8")
    log = tmp_path / "calls.jsonl"
    env = {**os.environ, "CHILD_LOG": str(log), "CHILD_MODE": mode}
    return [sys.executable, str(script), "--target-dir", "x"], env, log


def _run(tmp_path: Path, mode: str, flags: list[str]):
    cmd, env, log = _child(tmp_path, mode)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        proc = _wlr().run_with_inherited_log_root(cmd, flags, capture_output=True, text=True, check=False, env=env)
    calls = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
    return proc, calls, err.getvalue()


def test_a_build_that_rejects_the_flag_is_retried_once_without_it_and_warned(tmp_path):
    # covers: INF-500d-4-iii
    # angle: failure
    """Exit 2 + 'unrecognized arguments' with flags: exactly one retry without them, a WARNING naming the flag."""
    proc, calls, err = _run(tmp_path, "old", ["--log-root", "/abs/logs"])
    assert proc.returncode == 0, proc
    assert calls == [["--target-dir", "x", "--log-root", "/abs/logs"], ["--target-dir", "x"]], calls
    assert "WARNING" in err and "--log-root" in err and re.search(r"durable|survive", err), err


def test_a_build_that_accepts_the_flag_runs_once_without_a_warning(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """Control: success on the first call is not retried and prints nothing (the retry is only for a rejection)."""
    proc, calls, err = _run(tmp_path, "new", ["--log-root", "/abs/logs"])
    assert proc.returncode == 0
    assert calls == [["--target-dir", "x", "--log-root", "/abs/logs"]], calls
    assert err == "", err


def test_exit_2_for_another_reason_or_without_flags_is_not_retried(tmp_path):
    # covers: INF-500d-4-iii
    # angle: discrimination
    """Wrong versions caught: retrying on any exit 2; retrying with no flags; retrying on any 'unrecognized' text."""
    problems = []
    for name, mode, flags in (("other_exit_2", "other2", ["--log-root", "/abs"]), ("no_flags", "always2", []),
                              ("exit_1_with_marker", "fail1", ["--log-root", "/abs"])):
        sub = tmp_path / name
        sub.mkdir()
        proc, calls, err = _run(sub, mode, flags)
        if len(calls) != 1 or proc.returncode == 0:
            problems.append(f"[{name}] must run once and return the failure: calls={calls} rc={proc.returncode}")
    assert problems == [], "\n".join(problems)
