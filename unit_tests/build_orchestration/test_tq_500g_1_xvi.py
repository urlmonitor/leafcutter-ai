"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xvi.py
GOAL: RED tests for TQ-500g-1-xvi: an operator command (``wrong_version_writer.py reset``) clears one work's
    pins, all of them or one name's, and nothing else clears a pin.
BUSINESS CONTEXT: Every test drives the real writer, gate and runner CLIs (subprocess, fresh processes) on the
    real git sandbox of the TQ-500g-1-xi family (``_tq500g1xi_fixtures``); pin files are written with json.dumps
    in the pin store's own shape (the xiii ``write_pins``) or produced by a real first gate run. Today the
    writer has no ``reset`` step, so each test fails on an assertion about the JSON the CLI prints (argparse
    exits 2 and prints no JSON object), never on an import.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f
import unit_tests.build_orchestration._tq500g1xii_fixtures as v
import unit_tests.build_orchestration._tq500g1xiii_fixtures as w

PROP = "propagation that reaches only one level deep"
PROP_TYPED = " Propagation that reaches only one level deep "  # the operator's spelling: caps, edge spaces
RESET_SOURCE = "re-prepared: pin reset by the operator"
RESET_KEYS = ["work_key", "cleared", "not_pinned", "error"]
N1_PIN = (f.REFRESH, f.COND, f.COND_ALT)
PROP_PIN = (f.REFRESH, f.COND, "if True")


def _run_reset(sb, work_key: str, name: str | None = None):
    """Run the writer's reset step (``--name`` omitted when None); return ``(proc, JSON)``."""
    cmd = [sys.executable, str(ix.WRITER), "reset", "--work-key", work_key]
    if name is not None:
        cmd += ["--name", name]
    cmd += ["--test-root", str(sb.work)]
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120, env=x.env())
    return proc, ix.parse_one_json(proc, "reset step")


def _seed(sb) -> None:
    """07 holds two pins, 08 holds pins for the same two names (so a cross-key clear shows)."""
    w.write_pins(sb, {f.N1: [N1_PIN], PROP: [PROP_PIN]}, f.WK1)
    w.write_pins(sb, {f.N1: [N1_PIN], PROP: [PROP_PIN]}, f.WK2)


def _names(items: list[dict]) -> list[str]:
    return [i["name"] for i in items]


def _marker_ok(entry: dict, name: str, cleared_id: str) -> None:
    """*entry* is the reset marker left in place of the pin of *name* whose identity was *cleared_id*."""
    assert f.key_of(entry["name"]) == f.key_of(name), entry
    assert entry["reset"] is True and entry["cleared_alteration_id"] == cleared_id, entry
    assert entry["replacements"] == [] and entry["alteration_id"] is None and entry["failed_check"] is None, entry


def _tree_bytes(root: Path, skip: set[Path]) -> dict[str, bytes]:
    """Every file under *root* (relative POSIX path -> bytes), minus *skip* and git's own index."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and p not in skip and p.name != "index"}


def test_reset_one_name_clears_only_that_pin():
    # covers: TQ-500g-1-xvi
    # angle: criterion
    # Catches: the whole work cleared when one name is given; the same name cleared in another work key;
    # the name compared without trim and case-fold. Control: 07's other pin and 08's file are untouched.
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _seed(sb)
        before_wk1 = f.pins(sb, f.WK1)
        before_wk2_bytes = f.pin_bytes(sb, f.WK2)
        proc, out = _run_reset(sb, f.WK1, PROP_TYPED)
        assert proc.returncode == 0 and list(out) == RESET_KEYS, (proc.returncode, out, proc.stderr[-300:])
        assert out["work_key"] == f.WK1 and out["error"] is None and out["not_pinned"] == [], out
        cleared_id = f.alteration_id(f.repl_dicts(PROP_PIN))
        assert len(out["cleared"]) == 1 and f.key_of(out["cleared"][0]["name"]) == f.key_of(PROP), out["cleared"]
        assert out["cleared"][0]["alteration_id"] == cleared_id, out["cleared"]
        after = f.pins(sb, f.WK1)
        assert sorted(after) == sorted(before_wk1), "the clear removed a key instead of leaving a reset marker"
        assert after[f.key_of(f.N1)] == before_wk1[f.key_of(f.N1)], "the other pin of the work changed"
        _marker_ok(after[f.key_of(PROP)], PROP, cleared_id)
        assert f.pin_bytes(sb, f.WK2) == before_wk2_bytes, "the pin file of another work key changed"


def test_next_run_re_prepares_the_reset_name():
    # covers: TQ-500g-1-xvi
    # angle: criterion
    # Catches: a reset pin still applied on the next run; the reset name reported "prepared: not pinned".
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [f.N1, PROP])
        _seed(sb)
        n1_before = f.pins(sb, f.WK1)[f.key_of(f.N1)]
        assert _run_reset(sb, f.WK1, PROP)[0].returncode == 0
        proc, listed = f.run_list(sb, f.WK1)
        assert proc.returncode == 0 and _names(listed["to_prepare"]) == [PROP], listed
        sources = {d["name"]: d["source"] for d in listed["decisions"]}
        assert sources == {f.N1: f.PINNED, PROP: RESET_SOURCE}, sources
        entry = ix.prep(PROP, f.repl(f.COND_ALT), caught_by=[x.E1], would_catch=True, outcome="caught")
        done, out = f.finish(sb, [entry], f.WK1)
        assert done.returncode == 0 and out["gate_passed"] is True, out
        rows = [r for r in out["verdict"]["results"] if r["wrong_version"] == PROP]
        assert rows and {r["source"] for r in rows} == {RESET_SOURCE}, rows
        stored = f.pins(sb, f.WK1)
        new_repls = f.repl_dicts(f.repl(f.COND_ALT))
        assert stored[f.key_of(PROP)]["reset"] is False and stored[f.key_of(PROP)]["replacements"] == new_repls, stored[f.key_of(PROP)]
        assert stored[f.key_of(PROP)]["alteration_id"] == f.alteration_id(new_repls)
        assert stored[f.key_of(f.N1)] == n1_before, "the other pin of the work changed"


def test_reset_without_a_name_clears_the_whole_work_only():
    # covers: TQ-500g-1-xvi
    # angle: boundary
    # Catches: a whole-work reset that removes every work key's pins. Boundary: a work with no pin file.
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _seed(sb)
        before_wk1 = f.pins(sb, f.WK1)
        before_wk2_bytes = f.pin_bytes(sb, f.WK2)
        proc, out = _run_reset(sb, f.WK1)
        assert proc.returncode == 0 and list(out) == RESET_KEYS and out["error"] is None and out["not_pinned"] == [], (proc.returncode, out)
        want = {f.key_of(n): before_wk1[f.key_of(n)]["alteration_id"] for n in (f.N1, PROP)}
        assert {f.key_of(c["name"]): c["alteration_id"] for c in out["cleared"]} == want and len(out["cleared"]) == 2, out["cleared"]
        after = f.pins(sb, f.WK1)
        for name in (f.N1, PROP):
            _marker_ok(after[f.key_of(name)], name, want[f.key_of(name)])
        assert f.pin_bytes(sb, f.WK2) == before_wk2_bytes, "a whole-work reset changed another work key's pins"
        proc3, none = _run_reset(sb, f.WK3)  # no pin file at all
        assert proc3.returncode == 0 and none["cleared"] == [] and none["error"] is None, (proc3.returncode, none)
        assert not f.pin_path(sb, f.WK3).exists(), "a reset of a work without pins created a pin file"


def test_reset_of_an_unpinned_name_clears_nothing_and_says_so():
    # covers: TQ-500g-1-xvi
    # angle: failure
    # Catches: an unknown name silently ignored without being named. Also: a reset marker is not a pin, a bad
    # work key is refused with exit 1, and none of them touches the pin file.
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _seed(sb)
        raw = f.pin_bytes(sb, f.WK1)
        proc, out = _run_reset(sb, f.WK1, "retry only once")
        assert proc.returncode == 0 and list(out) == RESET_KEYS, (proc.returncode, out)
        assert out["cleared"] == [] and out["not_pinned"] == ["retry only once"] and out["error"] is None, out
        assert f.pin_bytes(sb, f.WK1) == raw, "naming a name without a pin changed the pin file"
        assert _run_reset(sb, f.WK1, PROP)[1]["cleared"], "control: the real pin is cleared"
        after_first = f.pin_bytes(sb, f.WK1)
        proc2, again = _run_reset(sb, f.WK1, PROP)  # only a reset marker is left now
        assert proc2.returncode == 0 and again["cleared"] == [] and _names([{"name": n} for n in again["not_pinned"]]) == [PROP], again
        assert f.pin_bytes(sb, f.WK1) == after_first
        proc3, bad = _run_reset(sb, "../" + f.WK1)
        assert proc3.returncode == 1 and bad["cleared"] == [] and isinstance(bad["error"], str) and bad["error"].strip(), (proc3.returncode, bad)


def test_reset_keeps_history_and_the_working_tree():
    # covers: TQ-500g-1-xvi
    # angle: boundary
    # Catches: a reset that deletes kept manifests (history/, the current manifest, plan.json, copies).
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        for entries in (f.first_entries(), None):  # run 1 prepares and pins, run 2 keeps run 1's manifest in history
            done, out = f.finish(sb, entries, f.WK1)
            assert done.returncode == 0 and out["gate_passed"] is True, out
        work_dir = sb.git_dir / "leafcutter" / "work" / f.WK1
        assert (work_dir / "history" / "0001").is_dir() and (work_dir / "alterations.json").is_file(), "control: no kept manifest"
        pin_file = f.pin_path(sb, f.WK1)
        files_before = _tree_bytes(sb.git_dir / "leafcutter", {pin_file})
        tree_before = x.snapshot(sb)
        proc, out = _run_reset(sb, f.WK1, f.N1)
        assert proc.returncode == 0 and len(out["cleared"]) == 1, (proc.returncode, out)
        assert _tree_bytes(sb.git_dir / "leafcutter", {pin_file}) == files_before, "the reset changed a file other than the pin file"
        assert x.snapshot(sb) == tree_before, "the reset changed the working tree, index or status"


def test_no_other_step_clears_a_pin():
    # covers: TQ-500g-1-xvi
    # angle: discrimination
    # Catches: recover or put-back clearing the pin store; preparing another name rewriting the pin file
    # without the existing pins. Each step is a real CLI in a fresh process.
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [f.N1, f.ALWAYS])
        _, first = f.finish(sb, f.first_entries(), f.WK1)
        assert first["gate_passed"] is True and sorted(f.pins(sb, f.WK1)) == sorted(f.key_of(n) for n in (f.N1, f.ALWAYS)), first
        two = {k: json.dumps(e, sort_keys=True) for k, e in f.pins(sb, f.WK1).items()}

        def same_two(step: str) -> None:
            now = {k: json.dumps(e, sort_keys=True) for k, e in f.pins(sb, f.WK1).items()}
            assert {k: now.get(k) for k in two} == two, f"{step} changed or removed a pin"

        v.set_owed(sb, [f.N1, f.ALWAYS, v.N5])  # step 1: a new run that prepares a third name
        proc, listed = f.run_list(sb, f.WK1)
        assert proc.returncode == 0 and _names(listed["to_prepare"]) == [v.N5], listed
        done, out = f.finish(sb, v.fresh_entries(v.N5), f.WK1)
        same_two("preparing another name")
        if out["gate_passed"] is True:
            assert f.key_of(v.N5) in f.pins(sb, f.WK1), "control: the third name was not pinned by its passing preparation"
        after_prepare = f.pin_bytes(sb, f.WK1)
        # step 2: a cut-short run leaves an open journal on the real RunGate; recover puts the file back.
        scripts = str(ix.REPO_ROOT / "scripts" / "build_orchestration")
        left_open = textwrap.dedent(f"""
            import sys
            from pathlib import Path
            sys.path.insert(0, {scripts!r})
            import _wvr_gate as g
            root = Path({str(sb.work.resolve())!r})
            target = root / {f.REFRESH!r}
            g.RunGate(root, g.gate_root(root) / "left-open").apply("left open", {{{f.REFRESH!r}: target.read_bytes() + b"# ALTERED\\n"}})
        """)
        subprocess.run([sys.executable, "-c", left_open], cwd=sb.work, check=True, capture_output=True, timeout=120)
        assert b"# ALTERED" in (sb.work / f.REFRESH).read_bytes(), "control: the cut-short run left the code altered"
        rec_proc, rec = fx.run_recover(sb)
        assert rec_proc.returncode == 0 and b"# ALTERED" not in (sb.work / f.REFRESH).read_bytes(), rec
        same_two("recover after a cut-short run")
        assert f.pin_bytes(sb, f.WK1) == after_prepare, "recover rewrote the pin file"
        # step 3: a code change elsewhere in the pinned file, then another finish.
        f.edit_source(sb, f.LOG_OLD, f.LOG_NEW)
        done3, out3 = f.finish(sb, None, f.WK1)
        same_two("a code change elsewhere followed by finish")
        assert out3["writer"]["written"] is True, (done3.returncode, out3["writer"])
        # Control: the operator command is the one step that does clear a pin, and only the named one.
        proc_r, cleared = _run_reset(sb, f.WK1, f.N1)
        assert proc_r.returncode == 0 and _names(cleared["cleared"]) == [f.N1], cleared
        assert f.pins(sb, f.WK1)[f.key_of(f.N1)]["reset"] is True and f.pins(sb, f.WK1)[f.key_of(f.ALWAYS)]["reset"] is False


def test_tq_500g_1_xvi_reachable_from_entry_point():
    # covers: TQ-500g-1-xvi
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_writer.py reset (CLI via subprocess)
    with tempfile.TemporaryDirectory() as tmp:
        sb = v.build(Path(tmp), [f.N1, f.ALWAYS])
        done, first = f.finish(sb, f.first_entries(), f.WK1)  # the real gate CLI leaves the real pins
        assert done.returncode == 0 and first["gate_passed"] is True, first
        pinned_id = f.pins(sb, f.WK1)[f.key_of(f.ALWAYS)]["alteration_id"]
        proc, out = _run_reset(sb, f.WK1, f.ALWAYS)
        assert proc.returncode == 0 and out["cleared"] == [{"name": f.ALWAYS, "alteration_id": pinned_id}], (proc.returncode, out)
        again, listed = f.run_list(sb, f.WK1)  # a fresh process consumes the marker in its plan
        assert again.returncode == 0 and _names(listed["to_prepare"]) == [f.ALWAYS], listed
        assert {d["name"]: d["source"] for d in listed["decisions"]} == {f.N1: f.PINNED, f.ALWAYS: RESET_SOURCE}, listed["decisions"]
