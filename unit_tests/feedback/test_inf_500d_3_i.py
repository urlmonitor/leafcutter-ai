"""
MODULE: test_inf_500d_3_i
GOAL: RED tests for AC INF-500d-3-i -- two submissions in the same second each leave
    their own id-recovery file, holding their own id.
CONTRACT: the recovery file keeps the form ``feedback_id_<digits>.txt`` in the temporary
    directory (so the documented ``sidecar:[^ ]*feedback_id_[0-9]*.txt`` search is
    unchanged) but is unique per submission BY CONSTRUCTION; a name already present
    yields a different name and is never replaced or truncated.
HOW: the real ``submit_feedback.py`` of a copied layout runs as separate overlapping
    subprocesses, each layout with its own declared sink and a TMPDIR confined to the
    test's tmp dir. See ``_inf_500d_3_helpers``. No build.py is spawned.
"""
# @ac-tag: INF-500d-3-i

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_3_helpers as t
from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_ii_check import RUN_A, fill
from unit_tests.feedback._inf_500d_4_vi_helpers import _declared_prompts, _shell


@pytest.fixture(scope="module")
def twenty(tmp_path_factory):
    layout = t.make_layout(tmp_path_factory.mktemp("twenty"))
    return layout, t.launch(layout, 20, "twenty-probe")


def _signoff_grep(layout_root) -> str:
    text = _declared_prompts(layout_root)["signoff"]
    line = next((ln.strip() for ln in text.splitlines() if ln.strip().startswith("grep -o 'sidecar:")), None)
    assert line is not None, "signoff no longer carries the documented sidecar recovery search"
    return line


def _apply_search(grep_line, run, layout, index):
    # The instruction's placeholders are filled for a concrete run (shared fill of INF-500d-3-ii), so the
    # documented search reads that submission's own error file, which holds the captured stderr.
    filled = fill(grep_line, RUN_A).replace("/tmp/", f"{layout.tmpdir}/")
    err = Path(filled.split()[-1])
    assert err.parent == layout.tmpdir, f"the search must read a file in the temp dir, got {err}"
    err.write_text(run.stderr, encoding="utf-8")
    proc = _shell(filled, layout.project, layout.tmpdir)
    return proc.stdout.splitlines()


def test_two_same_second_submissions_leave_two_distinct_recovery_files(tmp_path):
    # covers: INF-500d-3-i
    # angle: criterion
    """Two same-second submissions leave two feedback_id_<digits>.txt files, not one overwritten file."""
    layout, runs = t.same_second_pair(tmp_path, "pair")
    files = layout.recovery_files()
    assert [f.name for f in files if not t.DIGITS_NAME_RE.match(f.name)] == []
    assert len(files) == 2, f"two submissions must leave two recovery files, found {[f.name for f in files]}"
    assert t.sidecar_path(runs[0]) != t.sidecar_path(runs[1])


def test_first_submissions_announced_recovery_file_holds_exactly_its_id(tmp_path):
    # covers: INF-500d-3-i
    # angle: criterion
    """The first submission's announced file holds exactly its printed id and is not the second's file."""
    _layout, runs = t.same_second_pair(tmp_path, "first")
    first, second = runs
    assert t.ID_RE.match(first.id) and first.id != second.id
    path = t.sidecar_path(first)
    assert path.read_text(encoding="utf-8") == first.id, f"{path} holds {path.read_text(encoding='utf-8')!r}"
    assert path != t.sidecar_path(second), "both submissions announce one shared file"


def test_second_submissions_announced_recovery_file_holds_exactly_its_id(tmp_path):
    # covers: INF-500d-3-i
    # angle: criterion
    """The second submission's announced file holds exactly its printed id and is not the first's file."""
    _layout, runs = t.same_second_pair(tmp_path, "second")
    first, second = runs
    assert t.ID_RE.match(second.id) and first.id != second.id
    path = t.sidecar_path(second)
    assert path.read_text(encoding="utf-8") == second.id, f"{path} holds {path.read_text(encoding='utf-8')!r}"
    assert path != t.sidecar_path(first), "both submissions announce one shared file"


def test_neither_recovery_file_is_overwritten_by_the_other_submission(tmp_path):
    # covers: INF-500d-3-i
    # angle: discrimination
    """Over several same-second rounds every announced file still holds its own id and no two paths agree."""
    breaches = []
    for round_no in range(4):
        _layout, runs = t.same_second_pair(tmp_path / f"round{round_no}", f"round{round_no}")
        paths = [t.sidecar_path(r) for r in runs]
        if paths[0] == paths[1]:
            breaches.append(f"round {round_no}: both announce {paths[0]}")
        breaches += [f"round {round_no}: {p} holds {p.read_text(encoding='utf-8')!r}, not {r.id}"
                     for p, r in zip(paths, runs, strict=True) if p.read_text(encoding="utf-8") != r.id]
    assert not breaches, "\n".join(breaches)


def test_existing_recovery_file_is_never_replaced_or_truncated_on_a_forced_name_collision(tmp_path):
    # covers: INF-500d-3-i
    # angle: discrimination
    """With clock, pid and random sources frozen the first-choice name repeats; the first file must survive intact."""
    layout = t.make_layout(tmp_path)
    argvs = [h.submit_args(note=f"frozen {phase}", phase=phase) for phase in ("python-coder", "pr-reviewer")]
    script_dir = str(h.submit_script(layout.out_root).parent)
    proc = h.run_code(t.FROZEN_CODE, [script_dir, json.dumps(argvs)], layout.project, layout.tmpdir)
    assert proc.returncode == 0, proc.stderr
    first, second = (t.Run("", "", r["rc"], r["stdout"], r["stderr"]) for r in json.loads(proc.stdout))
    assert (first.rc, second.rc) == (0, 0)
    assert t.ID_RE.match(first.id) and t.ID_RE.match(second.id) and first.id != second.id
    p1, p2 = t.sidecar_path(first), t.sidecar_path(second)
    assert p1 != p2, f"the second run replaced the first run's recovery file {p1}"
    assert p1.read_text(encoding="utf-8") == first.id, f"first file now holds {p1.read_text(encoding='utf-8')!r}"
    assert p2.read_text(encoding="utf-8") == second.id
    assert [f.name for f in layout.recovery_files() if not t.DIGITS_NAME_RE.match(f.name)] == []
    assert len(layout.recovery_files()) == 2


def test_twenty_same_second_submissions_leave_twenty_distinct_recovery_files(twenty):
    # covers: INF-500d-3-i
    # angle: discrimination
    """Twenty concurrent processes leave exactly twenty distinct digits-only recovery files."""
    layout, runs = twenty
    assert [r.rc for r in runs] == [0] * 20, [r.stderr for r in runs if r.rc]
    files = layout.recovery_files()
    assert [f.name for f in files if not t.DIGITS_NAME_RE.match(f.name)] == []
    assert len(files) == 20, f"expected 20 recovery files, found {len(files)}"
    assert len({t.sidecar_path(r) for r in runs}) == 20


def test_each_printed_id_appears_in_exactly_one_recovery_file(twenty):
    # covers: INF-500d-3-i
    # angle: criterion
    """Every printed id is the exact content of exactly one file and no file holds an unprinted id."""
    layout, runs = twenty
    printed = Counter(r.id for r in runs)
    held = Counter(f.read_text(encoding="utf-8") for f in layout.recovery_files())
    assert sum(printed.values()) == 20 and set(printed.values()) == {1}
    assert held == printed, f"printed-but-unheld {dict(printed - held)}, held-but-unprinted {dict(held - printed)}"


def test_each_error_stream_names_the_recovery_file_holding_its_own_printed_id(twenty):
    # covers: INF-500d-3-i
    # angle: criterion
    """Each submission's single sidecar line names a file whose content is that submission's own id."""
    _layout, runs = twenty
    wrong = [f"{r.note}: {t.sidecar_path(r).name} holds {t.sidecar_path(r).read_text(encoding='utf-8')!r}, not {r.id}"
             for r in runs if t.sidecar_path(r).read_text(encoding="utf-8") != r.id]
    assert not wrong, "\n".join(wrong)


@pytest.mark.shared_layout_reader
def test_documented_recovery_search_returns_exactly_one_match_per_submission(shared_reference_layout, twenty):
    # covers: INF-500d-3-i
    # angle: seam
    """The signoff skill's documented grep, applied to each real stderr, returns exactly one match."""
    layout, runs = twenty
    grep_line = _signoff_grep(shared_reference_layout)
    bad = {i: m for i, r in enumerate(runs) if len(m := _apply_search(grep_line, r, layout, i)) != 1}
    assert not bad, f"the documented search must return exactly one match per submission, got {bad}"


@pytest.mark.shared_layout_reader
def test_documented_search_match_names_the_file_holding_the_printed_id(shared_reference_layout, twenty):
    # covers: INF-500d-3-i
    # angle: seam
    """The documented search's single match (prefix removed) is a file holding the id that submission printed."""
    layout, runs = twenty
    grep_line = _signoff_grep(shared_reference_layout)
    wrong = []
    for index, run in enumerate(runs):
        matches = _apply_search(grep_line, run, layout, index)
        assert len(matches) == 1 and "sink:" not in matches[0], matches
        found = layout.tmpdir.joinpath(matches[0].split("sidecar:", 1)[1])
        if not found.is_file() or found.read_text(encoding="utf-8") != run.id:
            wrong.append(f"{run.note}: {matches[0]} does not hold {run.id}")
    assert not wrong, "\n".join(wrong)


def test_submit_feedback_is_reachable_as_a_subprocess_and_leaves_a_recovery_file(tmp_path):
    # covers: INF-500d-3-i
    # angle: reachability
    """Real argv, real subprocess: exit 0, one stdout line, a sidecar line naming an existing file holding the id."""
    layout = t.make_layout(tmp_path)
    proc = h.submit(layout.out_root, layout.project, layout.tmpdir, note="reach")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [proc.stdout.strip()] and t.ID_RE.match(proc.stdout.strip())
    run = t.Run("reach", "python-coder", 0, proc.stdout, proc.stderr)
    assert t.sidecar_path(run).is_file()
    assert t.sidecar_path(run).read_text(encoding="utf-8") == run.id


def test_recovery_file_is_a_real_digits_only_artifact_in_the_confined_temp_directory(tmp_path):
    # covers: INF-500d-3-i
    # angle: real_artifact
    """The file read back from the confined TMPDIR is feedback_id_<digits>.txt, holds the id, and is the only file."""
    layout = t.make_layout(tmp_path)
    proc = h.submit(layout.out_root, layout.project, layout.tmpdir, note="artifact")
    assert proc.returncode == 0, proc.stderr
    run = t.Run("artifact", "python-coder", 0, proc.stdout, proc.stderr)
    on_disk = sorted(p.name for p in layout.tmpdir.iterdir())
    assert len(on_disk) == 1 and t.DIGITS_NAME_RE.match(on_disk[0]), on_disk
    path = t.sidecar_path(run)
    assert path.parent == layout.tmpdir and path.name == on_disk[0]
    assert path.read_text(encoding="utf-8") == run.id
