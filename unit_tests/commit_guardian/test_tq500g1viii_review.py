"""
MODULE: unit_tests/commit_guardian/test_tq500g1viii_review.py
GOAL: Regression tests for the TQ-500g-1-viii review findings: a record is tied to the ticket's own source_ac (H-1),
    and ticket paths are normalised (N-1).
BUSINESS CONTEXT: Real subprocess runs of the hook and of the record module's own ``open`` in a real git repo.
    The marker stores the ticket's frontmatter ``source_ac`` (written with yaml.safe_dump, as tools write it).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

import unit_tests.commit_guardian._tq500g1viii_fixtures as fx

KEY = "08_review_ticket"
OTHER = "TQ-OTHER-1"


def _ticket(source_ac) -> str:
    front = {"status": "todo"} if source_ac is None else {"status": "todo", "source_ac": source_ac}
    return "---\n" + yaml.safe_dump(front) + "---\n# ticket\n"


def _case(tmp_path: Path, name: str, source_ac):
    """A repo whose ticket carries *source_ac*, the marker opened by the module's CLI, ticket + code staged."""
    work = fx.make_repo(tmp_path / name, KEY)
    fx.write_bytes(work / fx.ticket_rel(KEY), _ticket(source_ac))
    fx.open_marker(work, KEY)
    paths = fx.stage_work(work, KEY)
    return work, paths


def _marker(work: Path) -> dict:
    return json.loads((fx.verdict_dir(work, KEY) / "open.json").read_text(encoding="utf-8"))


def test_records_bound_to_marker_source_ac_snapshot(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: discrimination
    # must_catch: dropped --source-ac commits ungated code
    ac_id, rb_pass, rb_na = fx.real_red_baseline_verdicts()

    # The snapshot comes from the ticket's frontmatter, never from the caller.
    assert _marker(_case(tmp_path, "some", [ac_id])[0])["source_ac"] == [ac_id]
    assert _marker(_case(tmp_path, "none", None)[0])["source_ac"] == []
    work = fx.make_repo(tmp_path / "caller", KEY)
    args = ["open", "--worktree", str(work), "--ticket-key", KEY, "--ticket-path", fx.ticket_rel(KEY)]
    assert fx.run_py(fx.RECORDS, [*args, "--source-ac", OTHER], work).returncode != 0, "open must take no caller-supplied source_ac"
    bad = fx.make_repo(tmp_path / "bad", KEY)
    fx.write_bytes(bad / fx.ticket_rel(KEY), "---\nsource_ac: [unclosed\n---\n")
    proc = fx.run_py(fx.RECORDS, ["open", "--worktree", str(bad), "--ticket-key", KEY, "--ticket-path", fx.ticket_rel(KEY)], bad)
    assert proc.returncode != 0 and '"opened": true' not in proc.stdout, f"an unreadable frontmatter must fail open closed: {proc.stdout!r}"

    work, paths = _case(tmp_path, "dropped", [ac_id])  # not-applicable records with ids [] for a ticket that owes runs
    fx.write_record(work, KEY, "red_baseline", rb_na)
    fx.write_record(work, KEY, "wrong_version", fx.wv_na(), paths={})
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0, f"not-applicable records for a ticket with a source_ac must block: {text!r}"

    work, paths = _case(tmp_path, "other", [ac_id])  # records that name a different AC
    fx.write_record(work, KEY, "red_baseline", rb_pass, ids=[OTHER])
    fx.write_record(work, KEY, "wrong_version", fx.wv_pass(), ids=[OTHER], paths=paths)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and (OTHER in text or "source_ac" in text), f"records for another AC must block: {text!r}"

    work, paths = _case(tmp_path, "nokey", [ac_id])  # a marker with no source_ac blocks
    fx.write_record(work, KEY, "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, KEY, "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    marker = _marker(work)
    del marker["source_ac"]
    (fx.verdict_dir(work, KEY) / "open.json").write_text(json.dumps(marker), encoding="utf-8")
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and "source_ac" in text, f"a marker with no source_ac must block: {text!r}"

    work, paths = _case(tmp_path, "match", [ac_id])  # control: matching ids, applicable, fresh
    fx.write_record(work, KEY, "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, KEY, "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    assert fx.run_hook(work)[0].returncode == 0, "control: matching ids must go on"

    work, paths = _case(tmp_path, "k3", None)  # control: a genuine K3 ticket with not-applicable records
    fx.write_record(work, KEY, "red_baseline", rb_na)
    fx.write_record(work, KEY, "wrong_version", fx.wv_na(), paths={})
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"control: K3 with not-applicable records must go on: {text!r}"


def test_marker_ticket_path_normalised_like_staged_paths(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: boundary
    # must_catch: marker ticket path compared un-normalised, so a staged ticket is not attributed
    ac_id, rb_pass, _ = fx.real_red_baseline_verdicts()
    for name, given in (("dot", "./" + fx.ticket_rel(KEY)), ("back", fx.ticket_rel(KEY).replace("/", "\\"))):
        work = fx.make_repo(tmp_path / name, KEY)
        proc = fx.run_py(fx.RECORDS, ["open", "--worktree", str(work), "--ticket-key", KEY, "--ticket-path", given], work)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _marker(work)["ticket_path"] == fx.ticket_rel(KEY), _marker(work)
        paths = fx.stage_work(work, KEY)
        fx.write_record(work, KEY, "red_baseline", rb_pass, ids=[])
        fx.write_record(work, KEY, "wrong_version", fx.wv_pass(), ids=[], paths=paths)
        proc, text = fx.run_hook(work)
        assert proc.returncode == 0, f"{given!r}: the staged ticket must be attributed to the marker: {text!r}"
    # the hook normalises a marker written by an older opener
    (fx.verdict_dir(work, KEY) / "open.json").write_text(json.dumps({"ticket_key": KEY, "ticket_path": "./" + fx.ticket_rel(KEY), "source_ac": [], "opened_at": "x"}), encoding="utf-8")
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"the hook must normalise the stored path too: {text!r}"
