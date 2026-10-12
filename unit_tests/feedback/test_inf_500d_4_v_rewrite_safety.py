"""
MODULE: test_inf_500d_4_v_rewrite_safety
GOAL: RED test for review-fix defect M-5 -- a failed rewrite of the feedback sink must not lose the records.
AC: INF-500d-4-v (readers/rewriters of the declared sink are safe next to a parallel drive's appends); ADR-069.

THE DEFECT: ``feedback_reader.replace_entries`` does ``fh.seek(0); fh.truncate(); fh.write(...)``. The truncation is
    committed before the first byte of the new content is written, so an I/O error part-way through (disk full, a
    quota, a killed filesystem) leaves a truncated or empty sink: every report the drive-after-drive history held is
    gone. The sink lives in the ENDURING root precisely because it is the only copy.

THE CONTRACT: when the rewrite fails part-way, the original records are still recoverable. EITHER the sink is
    byte-for-byte intact, OR a backup copy of the original sits beside the sink and the error NAMES it. (How the
    rewrite is made safe -- temp file + rename, or a backup before the truncate -- is the implementation's choice;
    keeping the inode so a waiting appender still appends to the same file is a separate property it may keep.)
    A rewrite that does NOT fail still replaces the content (the control), so "intact" cannot be had by never
    writing.

HOW THE FAILURE IS INJECTED (real, and independent of how replace_entries writes): ``RLIMIT_FSIZE`` is lowered, in a
    fresh subprocess that ignores SIGXFSZ, to a size the new content exceeds and the original does not. The kernel
    then fails the write with EFBIG part-way through -- through ``fh.write``, ``os.write``, a temp file or a copy
    alike. The REAL deployed ``feedback_reader`` is driven exactly the way ``resolve_feedback.py`` drives it
    (``exclusive_sink`` -> ``load_entries`` -> ``replace_entries``), over a sink the REAL producer filled.
"""
# @ac-tag: INF-500d-4-v

from __future__ import annotations

import json
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h

_SEEDED = 3
_LIMIT = 24_000       # bytes: above the original sink (~1.5 KB), below the rewritten one
_BIG_NOTE = "x" * 120_000

_DRIVER = """
import json, resource, signal, sys
from pathlib import Path
feedback_dir, sink, limit = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)       # EFBIG as an OSError, not a killed process
sys.path.insert(0, feedback_dir)
import feedback_reader
outcome = "returned"
try:
    with feedback_reader.exclusive_sink(sink) as fh:
        entries = feedback_reader.load_entries(fh, sink)
        entries[0]["resolution_note"] = "x" * 120000          # a rewrite that grows the file past the limit
        if limit:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
        feedback_reader.replace_entries(fh, sink, entries)
except SystemExit as exc:
    outcome = "SystemExit:%s" % (exc.code,)
except OSError as exc:
    outcome = "OSError:%s" % (exc,)
print(json.dumps({"outcome": outcome}))
"""


def _fresh_sink(base: Path) -> tuple[Path, Path, Path, bytes]:
    """A declared install and a sink filled by the real producer. Returns ``(project, out_root, sink, original_bytes)``."""
    root = base / "enduring" / "logs"
    root.mkdir(parents=True)
    project = base / "wt"
    project.mkdir()
    out_root = h.deploy_install(project)
    h.declare(out_root, root)
    sink = root / "feedback.jsonl"
    tmpdir = base / "tmpdir"
    tmpdir.mkdir()
    h.seed_reports(out_root, project, tmpdir, sink, _SEEDED, tag="precious",
                   category="subagent-quality", phase="ticket-supervisor")
    original = sink.read_bytes()
    assert len(original) < _LIMIT < len(original) + len(_BIG_NOTE), "fixture: the limit must separate old from new"
    return project, out_root, sink, original


def _drive(out_root: Path, project: Path, tmpdir: Path, sink: Path, limit: int):
    return h.run_code(_DRIVER, [str(out_root / "scripts" / "feedback"), str(sink), str(limit)], project, tmpdir)


def _ids(path: Path) -> list[str]:
    return [json.loads(line)["feedback_id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_a_rewrite_that_fails_part_way_leaves_the_original_records_recoverable(tmp_path):
    # covers: INF-500d-4-v
    # angle: failure
    """A write error after the rewrite began: the sink is byte-for-byte intact, or a backup of the original sits
    beside it and the error names that backup. The no-failure control replaces the content as asked."""
    project, out_root, sink, original = _fresh_sink(tmp_path)
    tmpdir = tmp_path / "tmpdir"
    before = h.snapshot(sink.parent)

    proc = _drive(out_root, project, tmpdir, sink, _LIMIT)

    assert proc.returncode == 0, f"the driver itself failed (fixture): {proc.stderr!r}"
    outcome = json.loads(proc.stdout)["outcome"]
    assert outcome.startswith("SystemExit:2") or outcome.startswith("OSError"), (
        f"fixture: the injected write failure must surface as the reader's write error, got {outcome!r}: {proc.stderr!r}")
    assert "Cannot write" in proc.stderr or "No space" in proc.stderr or "too large" in proc.stderr, (
        f"the failure must be reported on stderr: {proc.stderr!r}")

    intact = sink.read_bytes() == original if sink.is_file() else False
    if not intact:
        new_files = [Path(p) for p in h.snapshot(sink.parent) - before if Path(p).is_file()]
        backups = [p for p in new_files if p.read_bytes() == original]
        assert backups, (
            "the rewrite failed AFTER truncating the sink and left no copy of the original records: "
            f"sink now holds {sink.stat().st_size if sink.is_file() else 'nothing'} bytes (was {len(original)}); "
            f"new files beside it: {sorted(p.name for p in new_files)}")
        assert any(str(p) in proc.stderr for p in backups), (
            f"the error must NAME the backup so the operator can find it: backups={[str(p) for p in backups]} "
            f"stderr={proc.stderr!r}")
    else:
        assert _ids(sink) == _ids_from_bytes(original), "an intact sink must still parse to the same records"

    # Control: the same drive with no failure injected really rewrites -- 'intact' is not 'never written'.
    control_base = tmp_path / "control"
    control_base.mkdir()
    c_project, c_out, c_sink, _c_original = _fresh_sink(control_base)
    ok = _drive(c_out, c_project, control_base / "tmpdir", c_sink, 0)
    assert json.loads(ok.stdout)["outcome"] == "returned", ok.stderr
    rewritten = [json.loads(line) for line in c_sink.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rewritten) == _SEEDED and rewritten[0]["resolution_note"] == _BIG_NOTE, (
        "the control rewrite must replace the content (and keep every record)")


def _ids_from_bytes(data: bytes) -> list[str]:
    return [json.loads(line)["feedback_id"] for line in data.decode("utf-8").splitlines() if line.strip()]
