"""
MODULE: _inf_500d_4_ix_test_support
GOAL: Shared constants, helpers, fixture and stand-in factories for the AC INF-500d-4-ix tests
    (test_inf_500d_4_ix.py and test_inf_500d_4_ix_drift.py). Test-support only: no test lives here.
AC: INF-500d-4-ix (source_ac). The contract these helpers serve is described in the docstring of
    test_inf_500d_4_ix.py.
"""
# @ac-tag: INF-500d-4-ix

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
from pathlib import Path

import pytest

_COPIES_MODULE = "unit_tests.feedback._usable_stream_parity_copies"
_GUARD_FILE = "inline_work_guard.jsonl"

COPIES = ("emit_event", "inline_work_guard", "plan_feature_telemetry", "building_epics_probe", "epic_supervisor_probe")
GUARD = "inline_work_guard"
TELEMETRY_COPIES = tuple(c for c in COPIES if c != GUARD)

ROW_NAMES = (
    "no_declaration_file",
    "empty_object",
    "unparseable_json",
    "no_operational_log_root",
    "relative_operational_log_root",
    "stream_missing",
    "stream_relative",
    "stream_outside_root",
    "stream_two_levels_under_root",
    "valid_log_dir_present",
    "valid_log_dir_missing_conventional",
    "valid_log_dir_missing_flat",
    "valid_enduring_root_vanished_conventional",
    "valid_enduring_root_vanished_flat",
)
VANISHED_ROWS = frozenset({"valid_enduring_root_vanished_conventional", "valid_enduring_root_vanished_flat"})
# The telemetry stream is usable exactly when the declaration is valid AND the enduring root is live.
TELEMETRY_USABLE = frozenset({"valid_log_dir_present", "valid_log_dir_missing_conventional", "valid_log_dir_missing_flat"})
# Option A: the guard keeps its own file directly under the declared root, so it only cares about the ROOT.
GUARD_USABLE = TELEMETRY_USABLE | {"stream_missing", "stream_relative", "stream_outside_root", "stream_two_levels_under_root"}

_LAYOUT_FILES = {
    "emit_event": ".leafcutter/skills/agent-telemetry/scripts/emit_event.py",
    "inline_work_guard": ".leafcutter/hooks/inline_work_guard.py",
    "plan_feature": ".leafcutter/workflows/plan-feature.js",
    "building_epics": ".leafcutter/skills/building-epics/SKILL.md",
    "epic_supervisor": ".leafcutter/agents/epic-supervisor.md",
    "sink_resolution": ".leafcutter/scripts/knowledge/sink_resolution.py",
}
_PROBE_MARK = "pre-drive-reachability-check"


def _expected_usable(copy: str) -> frozenset[str]:
    return GUARD_USABLE if copy == GUARD else TELEMETRY_USABLE


def _parity():
    """Import the helper module lazily so its absence is a per-test red, not a collection error."""
    return importlib.import_module(_COPIES_MODULE)


def _private_layout(shared: object, dest: Path) -> Path:
    """A private verbatim copy of the shared layout (symlinks kept); the shared one is never touched."""
    shutil.copytree(Path(str(shared)), dest, symlinks=True)
    return dest


def _edit(layout: Path, key: str, old: str, new: str) -> None:
    path = layout / _LAYOUT_FILES[key]
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture: {old!r} is not in the deployed {_LAYOUT_FILES[key]}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def _remove_probe_block(layout: Path, key: str) -> None:
    """Delete the fenced bash block that carries the pre-drive probe (the snippet is gone, the rest stays)."""
    path = layout / _LAYOUT_FILES[key]
    text = path.read_text(encoding="utf-8")
    stripped, count = re.subn(rf"[ \t]*```bash\n[ \t]*# {_PROBE_MARK}\n.*?```\n", "", text, count=1, flags=re.DOTALL)
    assert count == 1 and _PROBE_MARK not in stripped, f"fixture: could not remove the probe block from {path}"
    path.write_text(stripped, encoding="utf-8")


def _tree_digest(root: Path) -> str:
    """One digest over every path, symlink target and file content below *root* (symlinks not followed)."""
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = Path(dirpath) / name
            digest.update(str(path.relative_to(root)).encode())
            if path.is_symlink():
                digest.update(os.readlink(path).encode())
            elif path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def _state(tree: Path) -> dict[str, str]:
    """Every path under *tree* -> its content digest (directories: ``dir``); catches a new file AND an appended one."""
    seen = {str(tree): "dir"}
    for dirpath, dirnames, filenames in os.walk(tree):
        for name in dirnames:
            seen[os.path.join(dirpath, name)] = "dir"
        for name in filenames:
            path = Path(dirpath) / name
            seen[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "other"
    return seen


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _hook_payload(project: Path) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(project / "x.py")}})


_BASELINES: dict[str, object] = {}  # shared layout path -> its one parity report (the layout fixture is function-scoped)


@pytest.fixture
def baseline_report(shared_reference_layout):
    """ONE run of the parity check over the untouched deployed layout, shared by the read-only assertions."""
    layout = str(shared_reference_layout)
    if layout not in _BASELINES:
        parity = _parity()
        _BASELINES[layout] = parity.run_parity(Path(layout), parity.build_rows())
    return _BASELINES[layout]


# case id -> (file key, old text, new text, drifted copy, rows that copy must now disagree on)
_DRIFTS = {
    "building_epics_hardcodes_the_debugging_layout": (
        "building_epics",
        'HOLDER="$(dirname "$LOG_DIR")"; [ "$(basename "$HOLDER")" != debugging ] || HOLDER="$(dirname "$HOLDER")"',
        'HOLDER="$(dirname "$(dirname "$LOG_DIR")")"',
        "building_epics_probe", {"valid_enduring_root_vanished_flat"}),
    "epic_supervisor_hardcodes_the_debugging_layout": (
        "epic_supervisor",
        'HOLDER="$(dirname "$LOG_DIR")"; [ "$(basename "$HOLDER")" != debugging ] || HOLDER="$(dirname "$HOLDER")"',
        'HOLDER="$(dirname "$(dirname "$LOG_DIR")")"',
        "epic_supervisor_probe", {"valid_enduring_root_vanished_flat"}),
    "plan_feature_drops_the_holder_check": (
        "plan_feature",
        '[ -d \\"$HOLDER\\" ] && mkdir -p \\"$LOG_DIR\\" || exit 1;',
        'mkdir -p \\"$LOG_DIR\\" || exit 1;',
        "plan_feature_telemetry", VANISHED_ROWS),
    "emit_event_accepts_a_stream_below_the_root": (
        "emit_event", "if Path(stream).parent != Path(root):", "if False:",
        "emit_event", {"stream_outside_root", "stream_two_levels_under_root"}),
    "inline_work_guard_drops_the_holder_check": (
        "inline_work_guard", "if not holder.is_dir():", "if False:",
        "inline_work_guard", VANISHED_ROWS),
    "the_canonical_rule_itself_really_changes": (
        "sink_resolution", "if Path(values[key]).parent != Path(values[_ROOT_KEY]):", "if False:",
        "emit_event", {"stream_outside_root", "stream_two_levels_under_root"}),
}


def _unextractable_plan_feature(layout: Path) -> None:
    _edit(layout, "plan_feature", "const cmd = _buildRepoRootResolutionSnippet(target) + ", "const cmdRemoved = _buildRepoRootResolutionSnippet(target) + ")


_MISSING_COPIES = {
    "emit_event": lambda layout: (layout / _LAYOUT_FILES["emit_event"]).unlink(),
    "inline_work_guard": lambda layout: (layout / _LAYOUT_FILES["inline_work_guard"]).unlink(),
    "plan_feature_telemetry": _unextractable_plan_feature,
    "building_epics_probe": lambda layout: _remove_probe_block(layout, "building_epics"),
    "epic_supervisor_probe": lambda layout: _remove_probe_block(layout, "epic_supervisor"),
}

_STAND_IN_ROWS = ("no_declaration_file", "valid_log_dir_present")


def _stand_in_writer(parity, printf_text, target, *, report_as=None):
    """A stand-in shell copy: appends *printf_text* to ``target(installed)`` (None: writes nothing) via bash and is
    judged by the same rule as the real shell copies. ``report_as(installed)`` swaps the location it claims."""
    def run(installed):
        where = target(installed)
        command = ":" if where is None else (
            f"mkdir -p {shlex.quote(str(where.parent))} && printf {shlex.quote(printf_text)} >> {shlex.quote(str(where))}")
        verdict = parity.shell_verdict(installed, command, "stand_in")
        if report_as is None or not verdict.usable:
            return verdict
        return parity.Verdict(True, report_as(installed), verdict.detail)
    return run


_STAND_INS = {
    "two_lines": lambda parity: _stand_in_writer(parity, "one\\ntwo\\n", lambda i: i.stream),
    "wrong_file": lambda parity: _stand_in_writer(
        parity, "one\\n", lambda i: None if i.stream is None else i.stream.parent / "elsewhere.jsonl"),
    "location_only_drift": lambda parity: _stand_in_writer(
        parity, "one\\n", lambda i: i.stream, report_as=lambda i: i.stream.parent / "elsewhere.jsonl"),
}
