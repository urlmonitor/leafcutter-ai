"""
MODULE: test_tq_500g_1_ix_reply
GOAL: TQ-500g-1-ix, reply handling: exact owed names, claims that never reach the
    manifest, unreadable and stale replies, and the working tree left alone.
BUSINESS CONTEXT: Real sandbox repo + real AC store + json.dump replies
    (_tq500g1ix_fixtures); the writer is driven through its CLI only.
"""

from __future__ import annotations

import json
from collections import Counter

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix

_ENTRY_KEYS = {
    "name", "status", "reason", "files", "diff", "replacements", "alteration_id", "source",
}


def test_owed_names_exactly_once_and_unowed_or_alias_names_absent(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: discrimination
    # Catches: an unowed name from the reply written to the manifest
    # Catches: name answered twice: one answer picked
    # Catches: the owed set taken from the reply instead of the test entries
    sb = ix.build_sandbox(tmp_path)
    twice = ix.prep(ix.N8, ("refresh_config.py", 'return "skip"', 'return "skip."'))
    entries = [*ix.default_entries(), twice, dict(twice), ix.prep(ix.UNDONE, ("settings.py", "TIMEOUT = 5", "TIMEOUT = 6")),
               ix.prep(ix.N1.upper() + " ", ("refresh_config.py", ix.COND, ix.COND_ALT))]
    proc, out = ix.write_default(sb, entries)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    names = [e["name"] for e in m["entries"]]
    assert sorted(names) == sorted(ix.OWED) and len(names) == 9, names
    assert Counter(names).most_common(1)[0][1] == 1, f"a name appears more than once: {names}"
    for stray in (ix.ALIAS, ix.UNDONE, ix.UNOWED, ix.N1.upper() + " "):
        assert stray not in names, f"{stray!r} was recorded"
    ix.assert_refused(m, ix.N8, "more than one alteration returned")
    assert ix.entry(m, ix.N1)["status"] == "prepared", "control: the exact-spelled R1 is still prepared"
    assert sorted(out["ignored_reply_names"]) == sorted(
        [ix.ALIAS, ix.UNDONE, ix.UNOWED, ix.N1.upper() + " "]), out["ignored_reply_names"]
    assert [e["name"] for e in out["entries"]] == names, "stdout entries must match the manifest order"


def test_outcome_claims_and_anomalies_never_reach_the_manifest(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: discrimination
    # Catches: a reply claim field copied into a manifest entry
    sb = ix.build_sandbox(tmp_path)
    extras = {"caught": True, "would_catch": [ix.CLAIM_TEST], "outcome": "caught", "tested_by": ix.CLAIM_TEST}
    entries = ix.default_entries()
    entries[1].update(extras)
    proc, out = ix.write_default(sb, entries, anomalies=[ix.ANOMALY], verdict="all caught", caught_by=[ix.CLAIM_TEST])
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    # altered_copy values are absolute paths under pytest's tmp_path, whose folder name is
    # derived from this test's name ("test_outcome_..."); blank them so the scan sees only
    # what the writer chose to record, never the sandbox location.
    scrubbed = json.loads(json.dumps(m))
    for e in scrubbed["entries"]:
        for f in e.get("files", []):
            f["altered_copy"] = ""
    text = json.dumps(scrubbed)
    for leak in (ix.CLAIM_TEST, "ANOMALYMARK", "WRONGDIFFMARK", "all caught", "would_catch", "caught_by", "outcome"):
        assert leak not in text, f"{leak!r} reached the manifest"
    assert set(m) == {"work_key", "entries"} and m["work_key"] == ix.WORK_KEY
    for e in m["entries"]:
        assert set(e) == _ENTRY_KEYS, f"{e['name']!r} carries keys {sorted(e)}"
    assert out["preparer_anomalies"] == [ix.ANOMALY]
    assert list(out) == ix.EXPECTED_KEYS, f"stdout keys {list(out)}"
    assert ix.CLAIM_TEST not in json.dumps(out["entries"])


def test_unreadable_or_failed_reply_stops_with_named_error(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: an empty reply read as owing no wrong version
    sb = ix.build_sandbox(tmp_path)
    good = json.dumps(ix.reply_obj(ix.default_entries()))
    unreadable = "the preparer's reply could not be read:"
    cases = [
        ("empty file", ix.write_reply(sb, "", "r1.json"), None, unreadable),
        ("cut off part-way", ix.write_reply(sb, good[: len(good) // 2], "r2.json"), None, unreadable),
        ("other work key", ix.write_reply(sb, ix.reply_obj(ix.default_entries(), work_key="another-work"), "r3.json"), None, unreadable),
        ("neither shape", ix.write_reply(sb, {"entries": "no"}, "r4.json"), None, unreadable),
        ("empty stdin", None, "", unreadable),
        ("failed shape", ix.write_reply(sb, {"status": "failed", "blocker_summary": "no file readable", "anomalies": []}, "r5.json"),
         None, "the preparer reported failure: no file readable"),
    ]
    for label, path, stdin, error in cases:
        proc, out = ix.run_writer(sb, "write", reply=path, stdin=stdin)
        assert proc.returncode == 1, f"{label}: exit {proc.returncode}"
        assert out["written"] is False and out["manifest_path"] is None, f"{label}: {out}"
        assert out["error"] is not None and out["error"].startswith(error), f"{label}: error {out['error']!r}"
        assert not sb.manifest_path.exists(), f"{label}: a manifest was written"
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True and out["error"] is None, "control: a good reply is read"
    assert len(ix.load_manifest(sb)["entries"]) == 9


def test_stale_manifest_never_survives_a_new_preparation(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: failure
    # Catches: the stale manifest from an earlier preparation left in place
    sb = ix.build_sandbox(tmp_path)
    stale_copy = sb.copies_dir / "stale-name" / "refresh_config.py"
    stale_copy.parent.mkdir(parents=True)
    stale_copy.write_bytes(b"STALE COPY\n")
    sb.manifest_path.write_text(json.dumps({"work_key": ix.WORK_KEY, "entries": []}), encoding="utf-8")
    proc, out = ix.run_writer(sb, "write", reply=ix.write_reply(sb, ""))
    assert proc.returncode == 1 and out["written"] is False, out
    assert not sb.manifest_path.exists(), "the stale manifest survived an unreadable reply"
    assert ix.copy_files(sb) == [], "stale copies survived an unreadable reply"
    stale_copy.parent.mkdir(parents=True, exist_ok=True)
    stale_copy.write_bytes(b"STALE COPY\n")
    only_r3 = [ix.prep(ix.N3, ("refresh_config.py", 'return "skip"', 'return "skip."'))]
    proc, out = ix.write_default(sb, only_r3)
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    assert m["work_key"] == ix.WORK_KEY and len(m["entries"]) == 9
    assert ix.entry(m, ix.N3)["status"] == "prepared"
    assert [f.name for f in ix.copy_files(sb)] == ["refresh_config.py"] and not stale_copy.exists()
    assert ix.entry(m, ix.N1)["reason"] == "no alteration returned", "the new reply, not the old, was recorded"


def test_working_tree_unchanged_and_no_stash(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: criterion
    # Catches: copies written inside the working tree
    # Catches: git stash used to hold the alterations
    sb = ix.build_sandbox(tmp_path)
    before = (fx.git_state(sb.work), fx.tree_digest(sb.work))
    assert "scratch_note.txt" in before[0]["status"], "fixture: the status must not be empty"
    git_files = {p for p in sb.git_dir.rglob("*") if p.is_file()}
    proc, out = ix.write_default(sb)
    assert proc.returncode == 0 and out["written"] is True, out
    assert (fx.git_state(sb.work), fx.tree_digest(sb.work)) == before
    assert before[0]["stash"] == "" and fx.git_state(sb.work)["stash"] == ""
    fresh = {p for p in sb.git_dir.rglob("*") if p.is_file()} - git_files
    stray = [p for p in fresh if sb.work_dir not in p.parents and p.name != "index"]
    assert fresh and stray == [], f"files written outside {sb.work_dir}: {stray}"
    assert ix.Path(out["manifest_path"]).resolve() == sb.manifest_path.resolve()
    assert len(ix.copy_files(sb)) == 1
