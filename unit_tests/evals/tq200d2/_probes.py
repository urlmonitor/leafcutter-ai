"""
MODULE: unit_tests/evals/tq200d2/_probes.py
GOAL: Shared reads for the tests of the TQ-200d scorer fixes (TQ-200d-2-i, -2-ii, -4-i, -4-iv):
    the reference entry of a kind, the probe files an entry names, the produced-tests lines of the
    evals README, and the known-issue register. Not a test file.
BUSINESS CONTEXT: Each scorer change must update its entry on the assertion-kinds reference page, and
    the entry must name its passing and failing examples by recorded probe files the unit tests score,
    so a page that says "this passes" cannot drift from what the scorer does. These helpers read the
    REAL pages, README and register; the scoring of a probe is done by the caller through the real
    scoring path.
ARCHITECTURE: Entries are parsed with the TQ-200d-1-ii page parser. A probe file is named on the entry
    as a backticked repo-relative path (with a directory part) under the ``Passing example`` or
    ``Failing example`` label; every named path must exist.
"""

from __future__ import annotations

import re

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d4._helpers as d4

REPO_ROOT = ref.REPO_ROOT
PROBE_PATH = re.compile(r"`((?:[\w.-]+/)+[\w.-]+\.(?:md|json|jsonl|recorded))`")
README = REPO_ROOT / "scripts" / "evals" / "README.md"
KI_DIR = REPO_ROOT / "docs" / "known-issues" / "testing-quality"
KI_INDEX = REPO_ROOT / "docs" / "known-issues" / "testing-quality.md"
PAGE_LINK = "../../docs/reference/"
NTC_ROW_ID = "no-test-collected"
COUNT_KIND = "report_pass_quotes_a_count"
PYTEST_KIND = "commands_ran_pytest"


def ntc_row() -> dict:
    """The real row ``no-test-collected`` of the test-runner set (TQ-200d-4-iv)."""
    for row in d4.load_rows("test-runner"):
        if row.get("id") == NTC_ROW_ID:
            return row
    msg = f"row {NTC_ROW_ID!r} is not in {d4.set_path('test-runner').name}"
    raise AssertionError(msg)


def entry_of(kind: str) -> dict:
    """The one reference entry of *kind* on the real pages."""
    found = [e for _name, e in ref.all_entries(ref.read_real_pages()) if e["kind"] == kind]
    assert len(found) == 1, f"the reference pages must hold exactly one entry for {kind!r}, found {len(found)}"
    return found[0]


def part(entry: dict, label: str) -> str:
    """The text of one labelled part of an entry."""
    return "\n".join(entry["parts"].get(label, []))


def text_of(entry: dict) -> str:
    """The whole entry as one lower-cased, whitespace-normalised string."""
    return ref.norm(" ".join(part(entry, label) for label in entry["parts"])).lower()


def probe_files(entry: dict, label: str) -> list[str]:
    """Repo-relative paths named (in backticks) in the *label* part of the entry; each must be an existing file."""
    named = PROBE_PATH.findall(part(entry, label))
    missing = [n for n in named if not (REPO_ROOT / n).is_file()]
    assert not missing, f"{entry['kind']}: the {label} part names files that do not exist: {missing}"
    return named


def assertion(record: dict, kind: str) -> dict:
    """The scored assertion of *kind* in a scored row (the row must hold exactly one)."""
    found = [a for a in record["score"]["assertions"] if a["kind"] == kind]
    assert len(found) == 1, f"the row must score {kind!r} once: {[a['kind'] for a in record['score']['assertions']]}"
    return found[0]


def readme_lines(kind: str) -> list[str]:
    """The lines of the README's produced-tests section that name *kind* as a whole word."""
    body = ref.section(README.read_text(encoding="utf-8"), "Produced-tests mode")
    assert body, "scripts/evals/README.md must keep its 'Produced-tests mode' section"
    return [ln for ln in body.splitlines() if re.search(rf"(?<!\w){re.escape(kind)}(?!\w)", ln)]


def check_readme_line(kind: str, family_page: str, *words: str) -> None:
    """Exactly one README line names *kind*, links its family page, holds each of *words*, and stays one short sentence."""
    lines = readme_lines(kind)
    assert len(lines) == 1, f"the produced-tests section must name {kind!r} on exactly one line, found {len(lines)}"
    line = lines[0]
    assert f"{PAGE_LINK}{family_page}" in line, f"the {kind!r} line must link the {family_page} entry: {line!r}"
    for word in words:
        assert word.lower() in line.lower(), f"the {kind!r} line must say {word!r}: {line!r}"
    assert len(line) <= 500, f"the {kind!r} line states the rule in one sentence and does not restate the entry: {len(line)} characters"


def counts_of_register() -> tuple[tuple[int, int, int, int], str]:
    """``((blocker, high, low, resolved) counted from the directory, the register's count line)``."""
    opened = {b: len(list(KI_DIR.glob(f"open-{b}-*.md"))) for b in ("blocker", "high", "low")}
    resolved = len(list((KI_DIR / "resolved").glob("*.md")))
    line = next(ln for ln in KI_INDEX.read_text(encoding="utf-8").splitlines() if ln.startswith("**Open:"))
    return (opened["blocker"], opened["high"], opened["low"], resolved), line


def register_counts_match_the_directory() -> None:
    """The index's Open / Resolved line equals the counts of the directory."""
    (blocker, high, low, resolved), line = counts_of_register()
    expected = f"**Open: {blocker + high + low}** ({blocker} blocker, {high} high, {low} low) · **Resolved: {resolved}**"
    assert line.startswith(expected), f"recount the register from the directory: expected {expected!r}, found {line!r}"


def ki_resolved(stem: str, *ac_ids: str) -> None:
    """The known issue *stem* moved to resolved: no open file, a resolved file whose Status names the ACs, an index row under Resolved."""
    opened = KI_DIR / f"open-low-{stem}.md"
    moved = KI_DIR / "resolved" / f"resolved-low-{stem}.md"
    assert not opened.exists(), f"{opened.name} must be moved (git mv) to resolved/"
    assert moved.is_file(), f"{moved.name} must exist under resolved/"
    status = next((ln for ln in moved.read_text(encoding="utf-8").splitlines() if ln.startswith("- **Status:**")), "")
    assert "RESOLVED" in status, f"the Status line of {moved.name} must say RESOLVED: {status!r}"
    for ac_id in ac_ids:
        assert ac_id in status, f"the Status line of {moved.name} must name {ac_id}: {status!r}"
    index = KI_INDEX.read_text(encoding="utf-8")
    open_part, _, resolved_part = index.partition("\n## Resolved")
    ki_id = "KI-TQ-" + stem.removeprefix("ki-tq-")
    assert ki_id not in open_part, f"the Open section of the register must no longer list {ki_id}"
    assert ki_id in resolved_part, f"the Resolved section of the register must list {ki_id}"
    register_counts_match_the_directory()
