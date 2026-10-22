"""
MODULE: unit_tests/commit_guardian/test_tq500g1viii_hook_staleness.py
GOAL: RED test for TQ-500g-1-viii B6, the per-path staleness rule of the new hook: every staged CODE path must
    appear in the wrong-version record's ``paths`` with the sha256 of its STAGED (index) content.
BUSINESS CONTEXT: Real subprocess runs in a real git repo whose index is manipulated with real git commands. The
    controls matter as much as the block: a knowledge .md staged after the runs, an unstaged leftover that
    differs from the record, and the same staged content must all go on. Code paths are those whose extension is
    in commit_guardian.json file_size.checked_extensions; that configuration is read, not copied (the .js case
    below is a checked extension that is not .py).
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.commit_guardian._tq500g1viii_fixtures as fx

KEY = "07_stale_ticket"


def _ready(tmp_path: Path, name: str):
    """A repo with the marker open, ticket + code v1 staged, and both records written for that exact code."""
    ac_id, rb_pass, _ = fx.real_red_baseline_verdicts()
    work = fx.make_repo(tmp_path / name, KEY)
    fx.open_marker(work, KEY)
    paths = fx.stage_work(work, KEY)
    fx.write_record(work, KEY, "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, KEY, "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    return work


def test_b6_code_changed_after_runs_is_out_of_date(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: discrimination
    # must_catch: no staleness check
    # must_catch: digest computed over the working tree instead of the staged content
    # must_catch: non-code files staged after the runs block the commit

    # Control: the staged content is exactly what the record holds -> goes on.
    work = _ready(tmp_path, "same")
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"control: unchanged staged code must go on: rc={proc.returncode} {text!r}"

    # Control: a knowledge note staged after the runs (building-epics 5.9) is not a code path.
    work = _ready(tmp_path, "knowledge")
    fx.write_bytes(work / fx.KNOWLEDGE, "note v1, written after the runs\n")
    fx.stage(work, fx.KNOWLEDGE)
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"a non-code file staged after the runs must not block: rc={proc.returncode} {text!r}"

    # Control: an unstaged leftover that differs from the record (a sibling's file) is not staged, so not judged.
    work = _ready(tmp_path, "leftover")
    fx.write_bytes(work / fx.CODE, fx.CODE_V2)  # working tree differs from the record; the index still holds v1
    fx.write_bytes(work / "scripts" / "leftover.py", "x = 1\n")  # never staged
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"unstaged leftovers must not block (the digest is over the staged content): rc={proc.returncode} {text!r}"

    # The block: a .py staged with different content after the record was written.
    work = _ready(tmp_path, "changed")
    fx.write_bytes(work / fx.CODE, fx.CODE_V2)
    fx.stage(work, fx.CODE)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.names_reason(text, r"out of date") and fx.CODE in text, (
        f"changed staged code must block as out of date, naming the path: rc={proc.returncode} {text!r}")

    # Staged content decides, not the working tree: stage v2, then put v1 back unstaged -> still out of date.
    work = _ready(tmp_path, "restored")
    fx.write_bytes(work / fx.CODE, fx.CODE_V2)
    fx.stage(work, fx.CODE)
    fx.write_bytes(work / fx.CODE, fx.CODE_V1)  # the working tree matches the record again; the index does not
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.names_reason(text, r"out of date"), (
        f"the digest must be taken from the index, not the working tree: rc={proc.returncode} {text!r}")

    # A new code path the record never saw is out of date too (a path absent from `paths`), as is a checked .js.
    for extra, body in (("scripts/new_module.py", "y = 2\n"), ("workflows/step.js", "const z = 3;\n")):
        work = _ready(tmp_path, "new_" + Path(extra).suffix.lstrip("."))
        fx.write_bytes(work / extra, body)
        fx.stage(work, extra)
        proc, text = fx.run_hook(work)
        assert proc.returncode != 0 and fx.names_reason(text, r"out of date"), (
            f"an unrecorded code path {extra} must block as out of date: rc={proc.returncode} {text!r}")
