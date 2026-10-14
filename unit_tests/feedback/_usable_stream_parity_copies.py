"""
MODULE: _usable_stream_parity_copies
GOAL: Compare every copy of the usable-stream / stale-root rule with the canonical
    ``sink_resolution`` rule on a table of declaration rows, and fail naming the copy
    and the row when one drifts or cannot be found or run (AC INF-500d-4-ix).
BUSINESS CONTEXT: The rule exists in six places: ``sink_resolution`` (canonical),
    ``emit_event._declared_stream`` and ``inline_work_guard._resolve_audit_path``
    (standard-library inline copies), the shell the plan-feature workflow dispatches,
    and the pre-drive reachability probes in ``building-epics`` and ``epic-supervisor``.
    Each copy is right about the value it computes, so they drift silently; this check
    feeds all of them the same declarations.
ARCHITECTURE: Test-support module (also a program: ``python <this file> <layout_dir>``).
    Every file is read from a DEPLOYED layout directory, never the source tree. The row
    table and its cheap installs live in ``_usable_stream_parity_rows``; the errors,
    ``Verdict`` and the run helpers in ``_usable_stream_parity_core``; the memoised
    canonical rule in ``_usable_stream_parity_canonical``; the report in
    ``_usable_stream_parity_report`` (all re-exported here). Shell copies are EXECUTED
    with bash and read by what they do (exit status plus whether the declared stream
    gained exactly one line), never by their text; the inline copies are loaded in a
    fresh interpreter, and so is the canonical rule. Independent (copy, row) pairs run
    on a thread pool; the canonical verdict of a row is computed once per rule content.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import shutil
import sys
import tempfile
import textwrap
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.feedback import _inf_500d_4_helpers as h  # noqa: E402
from unit_tests.feedback._usable_stream_parity_canonical import canonical_verdict  # noqa: E402
from unit_tests.feedback._usable_stream_parity_core import (  # noqa: E402
    CopyNotFoundError,
    CopyRunError,
    ParityError,
    Verdict,
    python_verdict,
    run_bash,
    run_command,
    tree_state,
    write_verdict,
)
from unit_tests.feedback._usable_stream_parity_report import (  # noqa: E402
    Disagreement,
    LocationMismatch,
    ParityReport,
)
from unit_tests.feedback._usable_stream_parity_rows import InstalledRow, Row, build_rows  # noqa: E402

__all__ = [
    "COPY_NAMES", "CopyNotFoundError", "CopyRunError", "Disagreement", "InstalledRow", "LocationMismatch",
    "ParityError", "ParityReport", "Row", "Verdict", "build_rows", "canonical_verdict", "load_copies",
    "load_copy", "main", "run_parity", "shell_verdict",
]

COPY_NAMES = (
    "emit_event", "inline_work_guard", "plan_feature_telemetry",
    "building_epics_probe", "epic_supervisor_probe",
)
GUARD = "inline_work_guard"
GUARD_FILE = "inline_work_guard.jsonl"
_WORKERS = 8
_PROBE_MARK = "pre-drive-reachability-check"
_PROBE_RE = re.compile(
    rf"^[ \t]*```bash[ \t]*\n[ \t]*# {_PROBE_MARK}[ \t]*\n(?P<body>.*?)^[ \t]*```",
    re.DOTALL | re.MULTILINE,
)
_PROBE_TAIL = (
    "\nprintf 'PROBE_SINK_OK=%s\\nPROBE_SINK_PATH=%s\\n' \"${SINK_OK:-}\" \"${SINK_PATH:-}\"\n"
)
# deployed file of each copy, relative to the layout directory
_COPY_FILES = {
    "emit_event": ".leafcutter/skills/agent-telemetry/scripts/emit_event.py",
    "inline_work_guard": ".leafcutter/hooks/inline_work_guard.py",
    "plan_feature_telemetry": ".leafcutter/workflows/plan-feature.js",
    "building_epics_probe": ".leafcutter/skills/building-epics/SKILL.md",
    "epic_supervisor_probe": ".leafcutter/agents/epic-supervisor.md",
}
_INLINE_FUNCTIONS = {"emit_event": "_declared_stream", "inline_work_guard": "_resolve_audit_path"}
_INLINE_PROBE = """
import importlib.util, json, sys
from pathlib import Path
function, script, declaration = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("copy_under_test", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
call = getattr(module, function)
found, why = call(declaration) if function == "_declared_stream" else call()
print(json.dumps({"location": str(found) if found is not None else None, "detail": why}))
"""
_PLAN_FEATURE_RESPONSES = {
    "stage-0-triage": {"route": "strategic", "existing_acs": [], "parent_l1_id": None,
                       "rationale": "route straight past the covered-route gate"},
    "worktree-setup": {"output": json.dumps({"worktree_path": "/tmp/parity-authoring-worktree",
                                             "ac_store_path": "/tmp/parity-authoring-worktree/ac"}),
                       "exit_code": 0},
    "pt-classify": {"outcome": "mock-data-only", "component": "test-comp",
                    "dispatch": ["mock-data-author"]},
    "pt-store-check": {"output": "absent", "exit_code": 0},
    "pt-telemetry": {"exit_code": 0},
}


# ---------------------------------------------------------------------------
# the copies
# ---------------------------------------------------------------------------

CopyRunner = Callable[[InstalledRow], Verdict]


def shell_verdict(installed: InstalledRow, command: str, label: str) -> Verdict:
    """Run *command* with bash in the row's project and read what it did (see ``write_verdict``)."""
    before = tree_state(installed.tree, installed.stream)
    proc = run_bash(command, installed.project, label)
    after = tree_state(installed.tree, installed.stream)
    return write_verdict(before, after, installed.stream, proc.returncode, proc.stderr)


def _emit_event_program(installed: InstalledRow, function: Verdict) -> Verdict:
    """Run the real emit_event.py on the row; usable only if it appended exactly one line to the declared stream."""
    script = installed.out_root / _COPY_FILES["emit_event"].split("/", 1)[1]
    before = tree_state(installed.tree, installed.stream)
    proc = run_command([sys.executable, "-B", str(script), *h.emit_args()], installed.project, "emit_event")
    after = tree_state(installed.tree, installed.stream)
    program = write_verdict(before, after, installed.stream, proc.returncode, proc.stderr)
    stray = program.stray or (program.usable and not function.usable)
    usable = function.usable and program.usable
    detail = program.detail or function.detail
    if program.usable and not function.usable:
        detail = f"the program wrote a line the rule refuses ({function.detail or 'no reason given'})"
    return Verdict(usable, function.location if usable else None, detail, stray)


def _inline_copy(name: str, path: Path, text: str) -> CopyRunner:
    function = _INLINE_FUNCTIONS[name]
    if f"def {function}" not in text:
        reason = f"{path} has no {function}"
        raise CopyNotFoundError(name, reason)
    relative = Path(_COPY_FILES[name]).relative_to(".leafcutter")

    def run(installed: InstalledRow) -> Verdict:
        declaration = installed.out_root / "config" / "knowledge_sink.json"
        script = installed.out_root / relative
        verdict = python_verdict([_INLINE_PROBE, function, str(script), str(declaration)], installed.tree, name)
        return _emit_event_program(installed, verdict) if name == "emit_event" else verdict
    return run


@functools.lru_cache(maxsize=1)
def _permission_args() -> tuple[tuple[str, object], ...]:
    """The workspace-setup permission verdict the workflow harness derives from a source-tree script.

    It is about the agent, not about the copy under test, and a deployed layout outside a repository
    would be refused; derived once per process (it runs a preflight script).
    """
    unit_tests = str(_REPO_ROOT / "unit_tests")
    if unit_tests not in sys.path:
        sys.path.insert(0, unit_tests)
    import _workflow_engine_harness as harness  # noqa: PLC0415
    script = _REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
    return tuple(harness._default_args_for_script(script).items())


_COMMANDS: dict[str, str] = {}


def _plan_feature_command(name: str, path: Path, text: str) -> str:
    """The shell command the workflow's own control flow composes for its telemetry dispatch.

    Extracted once per distinct workflow text (each extraction runs node).
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest in _COMMANDS:
        return _COMMANDS[digest]
    args = {**dict(_permission_args()), "run_id": "usable-stream-parity"}  # also puts the harness on sys.path
    import _workflow_engine_harness as harness  # noqa: PLC0415
    try:
        result = harness.run_workflow_under_e2(path, timeout=30, label_responses=_PLAN_FEATURE_RESPONSES, args=args)
    except (OSError, ValueError) as exc:
        reason = f"the workflow {path} could not be run: {exc}"
        raise CopyNotFoundError(name, reason) from exc
    calls = [call for call in result.agent_calls if call.label == "pt-telemetry"]
    match = re.search(r"^Run: (.+)$", calls[0].prompt, re.MULTILINE) if calls else None
    if result.error or match is None:
        reason = (f"no telemetry command could be extracted from {path} "
                  f"({result.error or 'no pt-telemetry dispatch'})")
        raise CopyNotFoundError(name, reason)
    _COMMANDS[digest] = match.group(1)
    return _COMMANDS[digest]


def _shell_copy(name: str, command: str) -> CopyRunner:
    return lambda installed: shell_verdict(installed, command, name)


def _probe_body(name: str, path: Path, text: str) -> str:
    match = _PROBE_RE.search(text)
    body = textwrap.dedent(match.group("body")) if match else ""
    if not any(line.strip() and not line.strip().startswith("#") for line in body.splitlines()):
        reason = f"no `# {_PROBE_MARK}` command in {path}"
        raise CopyNotFoundError(name, reason)
    return body


def _probe_copy(name: str, body: str) -> CopyRunner:
    script = body + _PROBE_TAIL

    def run(installed: InstalledRow) -> Verdict:
        proc = run_bash(script, installed.project, name)
        found = dict(line.split("=", 1) for line in proc.stdout.splitlines()
                     if line.startswith("PROBE_SINK_") and "=" in line)
        if "PROBE_SINK_OK" not in found:
            reason = f"the probe printed no verdict: {proc.stderr.strip()[:200]}"
            raise CopyRunError(name, reason)
        usable, sink = found["PROBE_SINK_OK"] == "1", found.get("PROBE_SINK_PATH", "")
        return Verdict(usable, Path(sink) if usable and sink else None, proc.stderr.strip()[:200])
    return run


def load_copy(layout_dir: Path, name: str) -> CopyRunner:
    """Return the runner of copy *name* from the deployed layout, or raise ``CopyNotFoundError``."""
    if name not in _COPY_FILES:
        reason = f"not one of the known copies {COPY_NAMES}"
        raise CopyNotFoundError(name, reason)
    path = Path(layout_dir) / _COPY_FILES[name]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        reason = f"cannot read {path}: {exc}"
        raise CopyNotFoundError(name, reason) from exc
    if name in _INLINE_FUNCTIONS:
        return _inline_copy(name, path, text)
    if name == "plan_feature_telemetry":
        return _shell_copy(name, _plan_feature_command(name, path, text))
    return _probe_copy(name, _probe_body(name, path, text))


def load_copies(layout_dir: Path) -> dict[str, CopyRunner]:
    """Every deployed copy, in ``COPY_NAMES`` order; the first one that cannot be found raises."""
    return {name: load_copy(layout_dir, name) for name in COPY_NAMES}


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def _compare_pair(name: str, run: CopyRunner, row: Row, layout: Path, judge: Callable[..., Verdict],
                  base: Path) -> tuple[Verdict | None, Verdict | None, str | None]:
    """One (copy, row) on a fresh install: (copy verdict, canonical verdict, error naming the culprit)."""
    try:
        installed = row.materialize(base / name / row.name, layout)
    except (ParityError, OSError) as exc:
        return None, None, f"the install of row {row.name} could not be built (for {name}): {exc}"
    try:
        answer = judge(installed, GUARD_FILE) if name == GUARD else judge(installed)
    except ParityError as exc:
        return None, None, f"the canonical rule could not be run on row {row.name} (compared with {name}): {exc}"
    try:
        return run(installed), answer, None
    except ParityError as exc:
        return None, None, f"{name} could not be run on row {row.name}: {exc}"


def _load_requested(layout: Path, copies: dict[str, CopyRunner] | None,
                    only: Iterable[str] | None) -> tuple[dict[str, CopyRunner], list[str]]:
    wanted = list(only) if only is not None else None
    if copies is not None:
        return {n: r for n, r in copies.items() if wanted is None or n in wanted}, []
    loaded: dict[str, CopyRunner] = {}
    errors: list[str] = []
    for name in (COPY_NAMES if wanted is None else wanted):
        try:
            loaded[name] = load_copy(layout, name)
        except CopyNotFoundError as exc:
            errors.append(str(exc))
    return loaded, errors


def run_parity(layout_dir: Path, rows: list[Row], canonical: Callable[..., Verdict] | None = None,
               copies: dict[str, CopyRunner] | None = None, only: Iterable[str] | None = None) -> ParityReport:
    """Run every copy on every row (each pair on a fresh install) against the canonical rule.

    ``only`` restricts the run to the named copies (a drift case needs just the drifted copy).
    Independent pairs run concurrently; the report is assembled in copy-then-row order.
    """
    layout = Path(layout_dir)
    judge = canonical or (lambda installed, filename=None: canonical_verdict(layout, installed, filename))
    runners, errors = _load_requested(layout, copies, only)
    report = ParityReport({}, {}, errors)
    base = Path(tempfile.mkdtemp(prefix="usable-stream-parity-"))
    try:
        with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
            jobs = [(name, row.name, pool.submit(_compare_pair, name, run, row, layout, judge, base))
                    for name, run in runners.items() for row in rows]
            for name, row_name, job in jobs:
                verdict, answer, error = job.result()
                if error is not None:
                    if error not in report.errors:
                        report.errors.append(error)
                    continue
                report.verdicts[(name, row_name)] = verdict
                report.canonical_verdicts[(name, row_name)] = answer
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return report


def main(argv: list[str] | None = None) -> int:
    """Run the parity check on the layout named by the one argument; exit 0 iff it is ok."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: _usable_stream_parity_copies.py <layout_dir>", file=sys.stderr)
        return 2
    try:
        report = run_parity(Path(args[0]), build_rows())
    except ParityError as exc:
        print(f"usable-stream parity could not run: {exc}", file=sys.stderr)
        return 1
    print(report.summary())
    if not report.ok:
        print(report.message(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 11:00 [python-coder]: Created the parity check; split rows and core out to stay under the file-size limit. (#TICKET-INF-500d-4-ix)
# - 2026-10-14 16:00 [python-coder]: Verdict is exit status + exactly one line in the declared stream; location mismatches fail; failures name canonical / row install; memoised canonical, cached plan-feature command, thread pool, copies subset. (#TICKET-INF-500d-4-ix)
