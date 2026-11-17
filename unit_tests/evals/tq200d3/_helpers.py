"""
MODULE: unit_tests/evals/tq200d3/_helpers.py
GOAL: Shared helpers for the TQ-200d-3 test family (the local-only eval set of the test-designer
    agent, scored by the produced-tests mode). Not a test file.
BUSINESS CONTEXT: The test designer produces no test file. Its output is the requirement record it edits
    (test_spec, test_design_authorship, test_design_opened_files), so a recorded gold output holds that
    record at ``files/<store>/<record id>.yaml`` (the path the live mode exports it to, and the path the
    scoring sandbox replays it to) and the one-JSON-object reply as ``report.md``. Every bad output is the
    REAL gold record of its row, parsed and re-serialised with the real YAML serialiser, with exactly ONE
    thing changed, so it can only fail for the reason the change carries. Reuses the TQ-200d-4 helpers for
    scoring and the runner CLI. No model, no network.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

import unit_tests.evals.tq200d4._helpers as d4

REPO_ROOT = d4.REPO_ROOT
SETS_DIR = d4.SETS_DIR
CONFIG = d4.CONFIG
module = d4.module
run_cli = d4.run_cli
failed = d4.failed
passed = d4.passed
gold_dir = d4.gold_dir

AGENT = "test-designer"
ROW_IDS = {"bug": "bug-fix", "gate": "gate", "new": "new-behaviour"}
AC_IDS = {"bug": "TDE-9701", "gate": "TDE-9702", "new": "TDE-9703"}
SET_PATH = SETS_DIR / f"{AGENT}.jsonl"

# The assertion kinds the TQ-200d-3 build adds, one failure per kind (see the report to the coder).
K_SCHEMA = "designer_record_schema_valid"
K_JUDGEMENT = "designer_states_judgement"
K_WRONG = "designer_names_wrong_versions"
K_NEITHER = "designer_states_neither"
K_WRITTEN = "designer_design_written"
ROW_KINDS = {
    "bug": {K_SCHEMA, K_JUDGEMENT, K_WRONG, K_WRITTEN},
    "gate": {K_SCHEMA, K_JUDGEMENT, K_WRONG, K_WRITTEN},
    "new": {K_SCHEMA, K_NEITHER, K_WRITTEN},
}

REVERT = "revert the fix"
ALIAS = "the fix undone"
ALWAYS = "the gate always allows"
DROP_RETRY = "drop the retry_due condition"
DROP_WINDOW = "drop the window-open condition"
DROP_LIMIT = "drop the position-limit condition"
# OQ-15 as amended 2026-10-25: the word-sequence variants each condition token also matches; the row spec carries them.
VARIANTS = {
    "bug": {"retry_due": ["retry due", "retry is due", "retry_due"]},
    "gate": {
        "window open": ["window open", "window is open", "open window", "window closed", "window is closed"],
        "position limit": ["position limit", "limit reached", "limit is reached"],
    },
}
STYLES = ("block", "flow", "json", "crlf", "comments", "sorted")


def load_rows() -> list[dict]:
    """Read the REAL set file; a missing file is the absence the tests report."""
    assert SET_PATH.is_file(), f"{SET_PATH} does not exist"
    return [json.loads(ln) for ln in SET_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


def real_row(key: str) -> dict:
    """The real row *key* (a ROW_IDS key) of the test-designer set."""
    for row in load_rows():
        if row.get("id") == ROW_IDS[key]:
            return row
    msg = f"row {ROW_IDS[key]!r} is not in {SET_PATH.name}"
    raise AssertionError(msg)


def agent_config() -> dict:
    """The agent's entry in agent_eval_config.json."""
    return d4.agent_config(AGENT)


def score(row: dict, output_dir: Path, work_dir: Path) -> dict:
    """Score one recorded output through the scoring module, as the mode does for the agent."""
    return d4.score(AGENT, row, output_dir, work_dir)


def score_gold_cli(tmp_path: Path):
    """Run the real runner CLI with --score-gold for the agent; return (process, parsed payload or None)."""
    return d4.score_gold_cli(AGENT, tmp_path)


# --- the recorded record --------------------------------------------------------------------------


def record_file(out_dir: Path, ac_id: str) -> Path:
    """The ONE ``<ac id>.yaml`` under ``<out_dir>/files`` (the exported, replayable path of the edited record)."""
    found = sorted((out_dir / "files").rglob(f"{ac_id}.yaml")) if (out_dir / "files").is_dir() else []
    assert len(found) == 1, f"the output {out_dir} must hold exactly one files/**/{ac_id}.yaml (the record the designer edited): {found}"
    return found[0]


def gold_record(key: str) -> dict:
    """The recorded gold record of row *key*, parsed."""
    return yaml.safe_load(record_file(gold_dir(real_row(key)), AC_IDS[key]).read_text(encoding="utf-8"))


def serialise(data: dict, style: str) -> bytes:
    """*data* as the bytes a designer's edited record file could hold, in one of several formattings."""
    block = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    if style == "json":
        return (json.dumps(data, indent=2) + "\n").encode("utf-8")
    if style == "flow":
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=True, width=10**6).encode("utf-8")
    if style == "sorted":
        return yaml.safe_dump(data, sort_keys=True).encode("utf-8")
    if style == "crlf":
        return block.replace("\n", "\r\n").encode("utf-8")
    if style == "comments":
        return f"# edited field by field by the test designer\n{block}# end of record\n".encode()
    return block.encode("utf-8")


def with_record(key: str, tmp_path: Path, mutate: Callable[[dict], None] | None = None, *, style: str = "block",
                reply: str | None = None, name: str = "swapped_output") -> Path:
    """Copy the gold output of row *key*; rewrite its record after ``mutate(record)``; optionally replace report.md."""
    gold = gold_dir(real_row(key))
    out = tmp_path / name
    shutil.copytree(gold, out)
    target = record_file(out, AC_IDS[key])
    data = copy.deepcopy(gold_record(key))
    if mutate is not None:
        mutate(data)
    target.write_bytes(serialise(data, style))
    if reply is not None:
        (out / "report.md").write_text(reply, encoding="utf-8")
    return out


def fixture_record_bytes(key: str) -> bytes:
    """The bytes of the row's PENDING fixture record: what the sandbox holds when the agent writes nothing."""
    expected = real_row(key)["expected"]
    return (REPO_ROOT / expected["fixture"] / expected["store"] / f"{AC_IDS[key]}.yaml").read_bytes()


def with_record_bytes(key: str, tmp_path: Path, raw: bytes | None) -> Path:
    """Copy the gold output of row *key*; replace the record file with *raw* bytes (None deletes it)."""
    out = with_record(key, tmp_path)
    target = record_file(out, AC_IDS[key])
    if raw is None:
        target.unlink()
    else:
        target.write_bytes(raw)
    return out


def spec_of(data: dict) -> list[dict]:
    """The test_spec list of a record."""
    assert isinstance(data.get("test_spec"), list) and data["test_spec"], "the gold record must hold a written test_spec"
    return data["test_spec"]


def guard_of(data: dict) -> dict:
    """The gold design's guarding entry: the first entry that carries a non-empty must_catch."""
    guards = [e for e in spec_of(data) if e.get("must_catch")]
    assert guards, "the gold design must hold an entry carrying must_catch (the guarding entry)"
    return guards[0]


def set_names(names: list[str], angle: str | None = "discrimination") -> Callable[[dict], None]:
    """A mutation: the guarding entry's must_catch becomes *names* (angle set, or removed when None)."""
    def mutate(data: dict) -> None:
        guard = guard_of(data)
        guard["must_catch"] = list(names)
        if angle is None:
            guard.pop("angle", None)
        else:
            guard["angle"] = angle
    return mutate


def strip_wrong_versions(data: dict) -> None:
    """A mutation: no entry names a wrong version and none is a discrimination test (the 'neither' design)."""
    for entry in spec_of(data):
        entry.pop("must_catch", None)
        if entry.get("angle") == "discrimination":
            entry["angle"] = "criterion"


def extra_entry(data: dict, **fields) -> dict:
    """Append a new entry modelled on the guarding or first entry (a distinct name), with *fields* set."""
    base = next((e for e in spec_of(data) if e.get("must_catch")), spec_of(data)[0])
    entry = {k: v for k, v in copy.deepcopy(base).items() if k not in ("must_catch", "angle")}
    entry["name"] = f"{base['name']}_extra{len(spec_of(data))}"
    entry.update(fields)
    spec_of(data).append(entry)
    return entry


# --- scoring expectations --------------------------------------------------------------------------


def expect_passes(row: dict, tmp_path: Path, output_dir: Path, label: str = "good") -> dict:
    """Score *output_dir* for *row*; every assertion passes."""
    record = score(row, output_dir, tmp_path / label)
    assert record["score"]["passed"] is True, failed(record)
    return record


def only(kind: str, *words: str, absent: tuple[str, ...] = ()) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """One expected failing kind with the words its detail must hold and the words it must not."""
    return {kind: (words, absent)}


def expect_fails(row: dict, tmp_path: Path, output_dir: Path, expected: dict[str, tuple[tuple[str, ...], tuple[str, ...]]],
                 label: str = "bad") -> dict:
    """Score a bad output: exactly the kinds of *expected* fail (``failed kinds == kinds``), the row fails.

    *expected* maps each failing kind to ``(words its detail holds, words it must not hold)``, checked
    against that rule's own wording. Some other assertion of the row still passes (the control).
    """
    record = score(row, output_dir, tmp_path / label)
    assert record["score"]["passed"] is False, record["score"]
    assert sorted(a["kind"] for a in failed(record)) == sorted(expected), failed(record)
    for item in failed(record):
        need, never = expected[item["kind"]]
        for word in need:
            assert word in item["detail"], f"{word!r} missing from {item['kind']} detail {item['detail']!r}"
        for word in never:
            assert word not in item["detail"], f"{word!r} must not be in {item['kind']} detail {item['detail']!r}"
    assert passed(record), "control: some other assertion of the row still passes"
    return record


def detail_of(record: dict, kind: str) -> str:
    """The detail of the (single) assertion *kind* of a scored row."""
    found = [a["detail"] for a in record["score"]["assertions"] if a["kind"] == kind]
    assert len(found) == 1, f"the row must hold exactly one {kind} assertion: {found}"
    return found[0]


# --- the sandbox, built as the mode builds it -------------------------------------------------------


def build_row_sandbox(key: str, tmp_path: Path) -> Path:
    """Build the row's scoring sandbox exactly as the mode does (fixture project + the scripts the agent has)."""
    runs = module("produced_tests_runs")
    mode = module("produced_tests_mode")
    expected = real_row(key)["expected"]
    sandbox = tmp_path / key / "sandbox"
    runs.build_sandbox(REPO_ROOT / expected["fixture"], sandbox, runs.hold_back_dirs(expected.get("assertions", [])),
                       mode.support_for(agent_config(), REPO_ROOT))
    return sandbox


def run_prepass(sandbox: Path, store: str, ids: list[str]) -> subprocess.CompletedProcess:
    """Run the REAL scripts/ac_store/design_prepass.py for the row's records in the sandbox."""
    script = REPO_ROOT / "scripts" / "ac_store" / "design_prepass.py"
    return subprocess.run(
        [sys.executable, str(script), "--ids", ",".join(ids), "--store-root", str(sandbox / store), "--repo-root", str(sandbox)],
        capture_output=True, text=True, timeout=120, check=False, cwd=sandbox,
    )
