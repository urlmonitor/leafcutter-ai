"""
MODULE: unit_tests/ac_store/test_acd_300c_4_ii.py
COVERS: ACD-300c-4-ii
GOAL: Red-first specification that an approval write which cannot be read back is restored and fails
    the step: the record's file is left exactly as before, a record written cleanly keeps its approval,
    and the step exits non-zero naming the file and the reason.
ARCHITECTURE: In-process `approve_acs.main(argv)` (cwd = a tmp consumer-style repo) with
    --ids ACD-9990a-1,ACD-9990a-2 --priority high. The write for ACD-9990a-2 is forced to leave invalid
    YAML: every way the step can put bytes into that file (Path.write_text, Path.write_bytes, os.replace
    and Path.replace of a temp file onto it) is wrapped so that NEW content gains a line with a YAML
    syntax error; restoring the original bytes passes through unchanged. The workflow half lives in
    unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_ii.py.
RED STATE: approve_acs.py has no --ids / --priority, so main() exits 2 before any write.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300c_4_fixtures import batch_store  # noqa: E402

_BROKEN = "\nbroken: [unclosed\n"
_TARGET_ID = "ACD-9990a-2"
_CLEAN_ID = "ACD-9990a-1"


def _force_invalid_write(monkeypatch, target: Path, original: bytes) -> None:
    """Make any NEW content written onto `target` unparseable; original bytes pass through."""
    target = target.resolve()
    real_text, real_bytes, real_replace, real_path_replace = Path.write_text, Path.write_bytes, os.replace, Path.replace

    def hits(path) -> bool:
        return Path(path).resolve() == target

    def write_text(self, data, *args, **kwargs):
        if hits(self) and data.encode("utf-8") != original:
            data = data + _BROKEN
        return real_text(self, data, *args, **kwargs)

    def write_bytes(self, data):
        if hits(self) and bytes(data) != original:
            data = bytes(data) + _BROKEN.encode("utf-8")
        return real_bytes(self, data)

    def corrupt_source(src, dst) -> None:
        if hits(dst) and Path(src).read_bytes() != original:
            real_bytes(Path(src), Path(src).read_bytes() + _BROKEN.encode("utf-8"))

    def replace(src, dst, *args, **kwargs):
        corrupt_source(src, dst)
        return real_replace(src, dst, *args, **kwargs)

    def path_replace(self, dst):
        corrupt_source(self, dst)
        return real_path_replace(self, dst)

    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(Path, "replace", path_replace)


def _main(argv: list[str]) -> int:
    import approve_acs  # noqa: PLC0415

    try:
        return approve_acs.main(argv)
    except SystemExit as stop:  # argparse usage error: an exit code, not a crash of the test
        return int(stop.code or 0)


def test_unreadable_write_restores_the_file_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    # covers: ACD-300c-4-ii
    # angle: real_artifact
    """With ACD-9990a-2's approval write forced to produce invalid YAML: its file is read back
    byte-identical to before, ACD-9990a-1 (written and read back cleanly) stays approved, the exit code is
    non-zero, and stderr names the file and the reason it could not be read back."""
    store = batch_store(tmp_path)
    target = store.path(_TARGET_ID)
    before = target.read_bytes()
    monkeypatch.chdir(store.repo_root)
    _force_invalid_write(monkeypatch, target, before)

    code = _main(["--ids", f"{_CLEAN_ID},{_TARGET_ID}", "--priority", "high", "--json"])
    err = capsys.readouterr().err

    assert store.read(_CLEAN_ID)["readiness"] == "approved", f"exit {code}; stderr: {err[-600:]}"
    assert target.read_bytes() == before, "the unreadable write was not restored to its pre-write bytes"
    assert code != 0, err
    assert f"{_TARGET_ID}.yaml" in err, err
    assert re.search(r"parse|read.?back", err, re.IGNORECASE), err


def test_a_failed_record_does_not_leave_later_ids_unprocessed(tmp_path, monkeypatch, capsys):
    # covers: ACD-300c-4-ii
    # angle: failure
    """The failing record comes FIRST in --ids: the later, clean id is still processed and approved, the
    exit code is non-zero, and the --json report names the failed id (`failed`) beside the approved one,
    so the caller learns exactly what was done."""
    import json  # noqa: PLC0415

    store = batch_store(tmp_path)
    target = store.path(_TARGET_ID)
    before = target.read_bytes()
    monkeypatch.chdir(store.repo_root)
    _force_invalid_write(monkeypatch, target, before)

    code = _main(["--ids", f"{_TARGET_ID},{_CLEAN_ID}", "--priority", "high", "--json"])
    captured = capsys.readouterr()

    report = json.loads(captured.out)
    assert code != 0 and target.read_bytes() == before, captured.err
    assert report["approved"] == [_CLEAN_ID] and report.get("failed") == [_TARGET_ID], report
    assert store.read(_CLEAN_ID)["readiness"] == "approved"


def test_a_write_whose_last_entry_is_not_the_new_one_is_restored(tmp_path, monkeypatch, capsys):
    # covers: ACD-300c-4-ii
    # angle: discrimination
    """The read-back demands the LAST amended_by entry to be the one just appended: a block builder that
    writes a different last entry (earlier entries intact) makes the write fail read-back, the record is restored byte for byte and
    the run exits non-zero."""
    import approve_acs  # noqa: PLC0415

    real = approve_acs._build_amended_by_block
    monkeypatch.setattr(approve_acs, "_build_amended_by_block", lambda block, entry: real(block, entry).replace("action: approved", "action: other"))
    store = batch_store(tmp_path)
    target = store.path(_CLEAN_ID)
    before = target.read_bytes()
    monkeypatch.chdir(store.repo_root)

    code = _main(["--ids", _CLEAN_ID, "--priority", "high", "--json"])

    assert code != 0, capsys.readouterr().err
    assert target.read_bytes() == before
