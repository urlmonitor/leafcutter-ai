"""
MODULE: _inf_500d_3_helpers
GOAL: Shared concurrent-submission helpers for the INF-500d-3-i / -iii test files
    (the id-recovery file of ``submit_feedback.py`` is unique per submission).
BUSINESS CONTEXT: Both files start the REAL ``submit_feedback.py`` of a copied
    layout as separate overlapping processes, each layout with its own declared
    sink and a TMPDIR confined to the test's tmp dir, so the recovery files land
    in a directory the test owns and never in the real shared temporary directory.
ARCHITECTURE: Reuses ``_inf_500d_4_helpers`` (layout, declaration, process
    launch) and ``_inf_500d_4_vi_helpers`` (worktree / enduring root / shell).
    No build.py is spawned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_4_vi_helpers import _enduring, _tmpdir, _worktree

PHASES = ("python-coder", "pr-reviewer", "test-writer", "architect-review")
CATEGORY = "complete"
DIGITS_NAME_RE = re.compile(r"^feedback_id_\d+\.txt$")
ID_RE = re.compile(h.FEEDBACK_ID_RE)


@dataclass
class Layout:
    project: Path
    out_root: Path
    root: Path
    tmpdir: Path

    @property
    def sink(self) -> Path:
        return self.root / "feedback.jsonl"

    def recovery_files(self) -> list[Path]:
        return sorted(p for p in self.tmpdir.iterdir() if p.name.startswith("feedback_id_"))


@dataclass
class Run:
    note: str
    phase: str
    rc: int
    stdout: str
    stderr: str

    @property
    def id(self) -> str:
        return self.stdout.strip()

    @property
    def key(self) -> tuple[str, str, str]:
        return (CATEGORY, self.phase, self.note)


def make_layout(base: Path) -> Layout:
    """A copied deployed install under ``base`` with its own declared sink and confined TMPDIR."""
    root = _enduring(base)
    project, out_root = _worktree(base, "wt", root)
    return Layout(project, out_root, root, _tmpdir(base))


def launch(layout: Layout, count: int, tag: str) -> list[Run]:
    """Start ``count`` real processes back to back (all running at once), then collect each."""
    started = []
    for index in range(count):
        phase, note = PHASES[index % len(PHASES)], f"{tag} {index}"
        args = h.submit_args(note=note, phase=phase, category=CATEGORY)
        started.append((note, phase, h.popen_py(h.submit_script(layout.out_root), args, layout.project, layout.tmpdir)))
    runs = []
    for note, phase, proc in started:
        out, err = proc.communicate(timeout=h.RUN_TIMEOUT)
        runs.append(Run(note, phase, proc.returncode, out, err))
    return runs


def sidecar_lines(run: Run) -> list[str]:
    return [line for line in run.stderr.splitlines() if line.startswith("sidecar:")]


def sidecar_path(run: Run) -> Path:
    """The one path on the ``sidecar:`` stderr line of ``run``."""
    lines = sidecar_lines(run)
    assert len(lines) == 1, f"expected exactly one sidecar line, got {lines!r} in {run.stderr!r}"
    return Path(lines[0].split("sidecar:", 1)[1])


def records(layout: Layout) -> list[dict]:
    return h.read_records(layout.sink)


def same_second_pair(base: Path, tag: str, attempts: int = 8) -> tuple[Layout, list[Run]]:
    """Two submissions (python-coder, pr-reviewer) whose records carry the SAME wall-clock second.

    A pair that straddles a second boundary proves nothing about a same-second collision, so it is
    discarded and re-run in a fresh layout; a run that never lands in one second fails loudly.
    """
    for attempt in range(attempts):
        layout = make_layout(base / f"try{attempt}")
        runs = launch(layout, 2, tag)
        assert all(r.rc == 0 for r in runs), [r.stderr for r in runs]
        if len({r["timestamp"] for r in records(layout)}) == 1:
            return layout, runs
    pytest.fail(f"could not start two submissions inside one wall-clock second in {attempts} attempts")


# A subprocess that freezes every clock, process-id and random source the entry point could build a
# name from, imports the COPIED layout's submit_feedback.py, and runs main() once per argv.
FROZEN_CODE = r"""
import contextlib, datetime as _dt, io, json, os, random, secrets, sys, time, uuid
NOW = 1788000000.0
_Real = _dt.datetime
class _Frozen(_Real):
    @classmethod
    def now(cls, tz=None):
        return _Real.fromtimestamp(NOW, tz)
    @classmethod
    def utcnow(cls):
        return _Real.fromtimestamp(NOW, _dt.timezone.utc).replace(tzinfo=None)
_dt.datetime = _Frozen
time.time = lambda: NOW
time.time_ns = lambda: int(NOW * 1e9)
for _name in ("monotonic", "perf_counter"):
    setattr(time, _name, lambda: 1.0)
for _name in ("monotonic_ns", "perf_counter_ns"):
    setattr(time, _name, lambda: 1)
os.getpid = lambda: 4242
os.urandom = lambda n: bytes([7]) * n
secrets.token_bytes = lambda n=32: bytes([7]) * n
secrets.token_hex = lambda n=32: "07" * n
secrets.token_urlsafe = lambda n=32: "B" * n
secrets.randbelow = lambda n: 0
secrets.randbits = lambda k: 0
random.random = lambda: 0.5
random.getrandbits = lambda k: 5
random.randint = lambda a, b: a
random.randrange = lambda a, b=None, step=1: a if b is not None else 0
random.choice = lambda seq: seq[0]
uuid.uuid4 = lambda: uuid.UUID(int=7)
sys.path.insert(0, sys.argv[1])
import submit_feedback as sf
results = []
for argv in json.loads(sys.argv[2]):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = sf.main(argv)
    results.append({"rc": rc, "stdout": out.getvalue(), "stderr": err.getvalue()})
print(json.dumps(results))
"""
