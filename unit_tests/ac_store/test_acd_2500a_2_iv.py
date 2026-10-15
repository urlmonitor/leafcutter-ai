"""
MODULE: test_acd_2500a_2_iv
GOAL: Red-first specification of ACD-2500a-2-iv: a readiness raised to `approved`
    by an authoring agent is restored to its before-stage value
    (scripts/ac_store/requirement_rule_check.py, family "readiness never raised to
    approved by an authoring agent", ticket 13).
BUSINESS CONTEXT: ACD-400c -- a requirement joins the buildable queue only once a
    person has approved it. The check restores the value; the user-run approval
    step is exempt by STAGE IDENTITY (`--stage approval`), never by inspecting the
    readiness values.
ARCHITECTURE: The before-state comes from the workflow, never the stage agent:
    `--before-snapshot FILE` (JSON {id: value|null}) in every test but one, and
    `--before-ref HEAD` (git show) in the single git-based test, which `git init`s
    a tmp repo. Rule: after == approved and before != approved -> restore; a record
    absent from the before-state (created during the stage) is restored to the
    authoring default `draft` and reported with its before-state stated as absent.
    The queue test uses the real scan_ac_store (ready filter: readiness == approved).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_READINESS,
    REPO_ROOT,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    make_store,
    run_cli_subprocess,
    valid_record,
    write_snapshot,
)

_R = "ACD-9990"          # draft at stage start, approved at stage end
_CONTROL = "ACD-9991"    # approved before AND after the stage: nothing to restore
_SCAN = REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"


def _strip_key_block(text: str, key: str) -> str:
    """`text` without the column-0 `key:` line and the lines belonging to its value."""
    kept: list[str] = []
    skipping = False
    for line in re.findall(r"[^\n]*\n|[^\n]+", text):
        if line.startswith(f"{key}:"):
            skipping = True
            continue
        if skipping and (line[:1] in (" ", "\t") or re.match(r"-[ \r\n]", line)):
            continue
        skipping = False
        kept.append(line)
    return "".join(kept)


def _raised_store(tmp_path, *, level: str = "L0"):
    """R is approved on disk; the before-state snapshot says it was draft. The control
    record was already approved before the stage and still is."""
    store = make_store(
        tmp_path,
        [
            valid_record(_R, level=level, readiness="approved"),
            valid_record(_CONTROL, level=level, readiness="approved"),
        ],
    )
    snapshot = write_snapshot(store, {_R: "draft", _CONTROL: "approved"})
    return store, ("--before-snapshot", str(snapshot))


def test_agent_raised_approved_restored_to_prior_value(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: criterion
    """R (draft at stage start, approved at stage end) reads 'draft' after the check;
    every other byte of R is unchanged; the already-approved control keeps 'approved'
    byte for byte."""
    store, before = _raised_store(tmp_path)
    r_text = store.path(_R).read_bytes().decode("utf-8")
    control_bytes = store.path(_CONTROL).read_bytes()

    exit_code, report = check_store(store, *before)

    assert store.read(_R)["readiness"] == "draft"
    r_after = store.path(_R).read_bytes().decode("utf-8")
    assert r_after.count("readiness:") == 1
    assert _strip_key_block(r_after, "readiness") == _strip_key_block(r_text, "readiness")
    assert store.path(_CONTROL).read_bytes() == control_bytes
    assert report["verdict"] == "passed" and exit_code == 0


def test_readiness_fix_names_file_removed_and_restored_values(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: criterion
    """Exactly one 'fixed' entry, in the readiness family, naming R's file, the value
    'approved' that was removed and the value 'draft' that was restored; the control
    produces no finding."""
    store, before = _raised_store(tmp_path)

    _, report = check_store(store, *before)

    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["rule_family"] == FAMILY_READINESS
    assert finding["rule_family"] == "readiness never raised to approved by an authoring agent"
    assert finding["disposition"] == "fixed"
    assert finding["file"] == store.rel(_R) and finding["record_id"] == _R
    text = finding_text(finding)
    assert "approved" in text and "draft" in text
    assert findings_for(report, record_id=_CONTROL) == []


def test_restored_record_not_in_buildable_queue(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: reachability
    """The scan_ac_store ready set holds R before the stage's check (control: the
    scenario is genuinely buildable) and no longer holds it after the real CLI
    restored R; the already-approved control stays buildable."""
    store, before = _raised_store(tmp_path, level="L2")
    ac_root = store.repo_root / "docs" / "acceptance-criteria"

    def ready_ids() -> set[str]:
        proc = subprocess.run(
            [sys.executable, str(_SCAN), "--ac-root", str(ac_root), "--json"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        return {item["ac_id"] for item in json.loads(proc.stdout)["ready"]}

    assert {_R, _CONTROL} <= ready_ids()  # the raised record would be built right now

    run = run_cli_subprocess(cli_argv(store, *before), cwd=store.repo_root)

    assert run.exit_code == 0, run.stderr
    ready_after = ready_ids()
    assert _R not in ready_after
    assert _CONTROL in ready_after


def test_user_approval_step_raise_not_flagged(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: boundary
    """A record raised reviewed -> approved at `--stage approval` produces no finding
    and keeps 'approved' byte for byte. The same on-disk state and before-state at an
    authoring stage ('ba') IS restored, so the exemption is the stage identity and not
    a property of the values."""
    approval_root = tmp_path / "approval"
    approval_root.mkdir()
    store = make_store(approval_root, [valid_record(_R, level="L0", readiness="approved")])
    snapshot = write_snapshot(store, {_R: "reviewed"})
    frozen = store.path(_R).read_bytes()

    exit_code, report = check_store(
        store, "--before-snapshot", str(snapshot), stage="approval"
    )

    assert findings_for(report, rule_family=FAMILY_READINESS) == []
    assert report["findings"] == []
    assert store.path(_R).read_bytes() == frozen
    assert store.read(_R)["readiness"] == "approved"
    assert report["verdict"] == "passed" and exit_code == 0

    authoring_root = tmp_path / "authoring"
    authoring_root.mkdir()
    store_ba = make_store(authoring_root, [valid_record(_R, level="L0", readiness="approved")])
    snapshot_ba = write_snapshot(store_ba, {_R: "reviewed"})

    _, report_ba = check_store(store_ba, "--before-snapshot", str(snapshot_ba), stage="ba")

    assert store_ba.read(_R)["readiness"] == "reviewed"
    assert [f["disposition"] for f in findings_for(report_ba, rule_family=FAMILY_READINESS)] == ["fixed"]


def test_record_created_during_stage_restored_to_draft_stating_absent(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: boundary
    """A record that did not exist at stage start (absent from the before-state) and
    ends 'approved' is restored to the authoring default 'draft' and reported 'fixed'
    with its before-state stated as absent."""
    store = make_store(tmp_path, [valid_record(_R, level="L0", readiness="approved")])
    snapshot = write_snapshot(store)
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    del data[_R]  # not in the stage-start state
    snapshot.write_text(json.dumps(data), encoding="utf-8")

    _, report = check_store(store, "--before-snapshot", str(snapshot))

    assert store.read(_R)["readiness"] == "draft"
    findings = findings_for(report, record_id=_R, rule_family=FAMILY_READINESS)
    assert [f["disposition"] for f in findings] == ["fixed"]
    text = finding_text(findings[0]).lower()
    assert "absent" in text and "draft" in text and "approved" in text


def test_before_ref_reads_stage_start_state_from_git(tmp_path):
    # covers: ACD-2500a-2-iv
    # angle: seam
    """`--before-ref HEAD` takes the before-state from the committed repo: R is 'draft'
    in HEAD, the stage raised it to 'approved' in the working tree, and the real CLI
    restores 'draft' with no snapshot file involved."""
    store = make_store(tmp_path, [valid_record(_R, level="L0", readiness="draft")])

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
             "-c", "commit.gpgsign=false", *args],
            cwd=store.repo_root, check=True, capture_output=True, text=True, timeout=60,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "stage start")
    raised = store.read(_R)
    raised["readiness"] = "approved"
    store.write(raised)  # the authoring agent's raise, uncommitted

    exit_code, report = check_store(store, "--before-ref", "HEAD")

    assert store.read(_R)["readiness"] == "draft"
    findings = findings_for(report, record_id=_R, rule_family=FAMILY_READINESS)
    assert [f["disposition"] for f in findings] == ["fixed"]
    assert report["verdict"] == "passed" and exit_code == 0
