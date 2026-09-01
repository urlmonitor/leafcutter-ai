"""
MODULE: test_repair_epic_member_pr_phase
GOAL: Failing (RED) test-first specification for the not-yet-written
    scripts/repair_epic_member_pr_phase.py — a one-time repair script for the
    333 epic-member tickets that carry `pull-request: needed` even though the
    build driver deliberately never dispatches that phase for a ticket inside
    an epic (one epic-level PR covers the whole branch).

STATUS: scripts/repair_epic_member_pr_phase.py does not exist yet. This is
    TDD test-first: python-coder implements the script against the contract
    fixed here. Every test below is expected to fail RED until it lands —
    `_run_script()` raises ImportError immediately because `_SCRIPT_PATH` is
    not a file, so every test fails at the first line of its body with
    ImportError. That is the legitimate red state for a script that has not
    been written yet (see verification run notes in the sign-off comment).

CONTRACT FIXED BY THIS FILE (the coder must satisfy this, not invent one):

    python3 scripts/repair_epic_member_pr_phase.py [--dry-run] [--tickets-dir PATH]

    - PATH defaults to <repo>/tickets and is walked recursively for *.md files.
    - A ticket is a REPAIR CANDIDATE iff (a) its path contains the segment
      `00_inbox/epics/` (POSIX-normalised) AND (b) its frontmatter `agents:`
      map has `pull-request: needed`.
    - For a repair candidate whose frontmatter `status` is NOT `done`:
        * the exact line `  pull-request: needed` becomes
          `  pull-request: not_needed` (never `signed_off` — no per-ticket
          pull-request phase ever ran for an epic member, so recording one
          that did is a phantom sign-off)
        * the exact `- [ ] pull-request` row is deleted from the
          `## Sign-offs` checklist (the whole line including its newline)
        * every other byte of the file — every other agents: entry, every
          other Sign-offs row, the whole body — is untouched
    - A repair candidate whose frontmatter `status` IS `done` is left
      completely untouched (byte-for-byte, mtime included).
    - A ticket outside the `00_inbox/epics/` path segment is left completely
      untouched, even though it sits inside the same --tickets-dir walk and
      may carry the identical `pull-request: needed` value (for a standalone
      ticket the phase genuinely runs).
    - A ticket whose frontmatter cannot be parsed as YAML is named in the
      script's output (stdout or stderr), is never written to, and makes the
      run's exit code non-zero.
    - --dry-run performs zero writes (content and mtime of every file are
      unchanged) but still reports what it would change.
    - The run is idempotent: running it a second time over its own output
      changes nothing and reports zero `changed`.
    - The run prints five integer counts, one per line, in the form
      `<label>: <int>` (label case-insensitive; a leading bullet/whitespace is
      allowed) using exactly these five labels: `examined`, `changed`,
      `skipped_done`, `skipped_not_applicable`, `refused`. `examined` must
      equal the sum of the other four.
    - Exit code is 0 when `refused` is 0, non-zero when `refused` > 0.

NO `# covers:` TAG ON ANY TEST IN THIS FILE: this is a one-time repair of a
    finite, already-enumerated population (333 tickets / 23 epic folders), not
    a durable product guarantee with an AC behind it. Per this ticket's
    explicit test-writer dispatch instructions, no AC id exists to tag with
    and none is invented to satisfy the pre-commit tagging hook.

REAL-ARTIFACT DISCIPLINE (EPIC-PhantomDoneFilesTouched lesson, restated in
    this worktree's CLAUDE.md "Real-artifact behavioral spot-check before
    declaring done"): every ticket fixture below is either (a) copied
    VERBATIM (shutil.copy2, no re-serialization) from a real ticket that is
    on disk in this very worktree's tickets/00_inbox/epics/ tree today, or
    (b) that same verbatim text with exactly one deliberate corruption
    applied in memory (the malformed-frontmatter fixture — no ticket in the
    real store is naturally malformed, so a test of the refusal path needs a
    hand-introduced defect; the base text it corrupts is still real). No
    fixture in this file is a hand-typed YAML/Markdown literal starting from
    a blank page.

REAL SOURCE TICKETS USED (read and confirmed on disk before writing this file):
    - tickets/00_inbox/epics/EPIC-DispatchPreflightGate/04_TICKET-20260708-BO-1900a-2.md
      (status: todo, epic member, pull-request: needed — the main-case donor)
    - tickets/00_inbox/epics/EPIC-BuildPipelinePhantomRemediation/05_bp1200b1_ci_test_gate_blocking.md
      (status: done, epic member, pull-request: needed — the already-done donor)
    - tickets/TICKET-20260716-TKT-500f-11.md
      (status: in_progress, NOT an epic member, pull-request: needed — the
      standalone donor; proves the epics-path filter, not a blanket walk)
    - tickets/00_inbox/epics/EPIC-ACStoreFoundation/01_schema_validation.md
      (status: todo, epic member, pull-request: needed, NO ## Sign-offs section
      at all — an older ticket template variant found only by running the
      script for real against the full store; confirmed on disk by the
      coordinator. 17 of the 332 qualifying tickets have this shape. See
      "NO-SIGN-OFFS-SECTION SHAPE" below.)

NO-SIGN-OFFS-SECTION SHAPE (found running the script for real, not anticipated
    up front): 17 of the 332 qualifying tickets use an older template that has
    no `## Sign-offs` section at all. Per `_check_parity` in
    `templates/scripts/commit_guardian/_signoff_parity_checks.py:443-448`, a
    `not_needed` agent with no `## Sign-offs` section is trivially compliant
    (the parsed signoffs map is empty, so `name in signoffs` is False and no
    violation fires) — so for this shape the frontmatter flip alone is the
    COMPLETE repair; there is no row to remove, and the script must not
    invent a `## Sign-offs` section that never existed (that would be
    authoring a record it has no standing to author). This is also strictly
    an improvement over the pre-repair state: today `pull-request: needed`
    with no Sign-offs row IS a violation on the sibling branch of that same
    function ("missing from ## Sign-offs"), so the flip removes an existing
    violation rather than creating one.

CROSS-LAYER SEAM (Rule 3): the repaired ticket's frontmatter `agents:` map
    and `## Sign-offs` checklist are read downstream by the REAL pre-commit
    guard `check_ticket_signoff_parity.py` (via `_validate_ticket_content`),
    which enforces exactly the invariant this repair produces: a `not_needed`
    agent must be absent from `## Sign-offs`. One test below pipes the repair
    script's actual on-disk output into that real consumer function and
    asserts it reports zero pull-request-related violations — proving the
    repaired file is not just internally plausible but genuinely consumable
    by the real downstream gate.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "repair_epic_member_pr_phase.py"

_SRC_NOT_DONE = (
    _REPO_ROOT
    / "tickets"
    / "00_inbox"
    / "epics"
    / "EPIC-DispatchPreflightGate"
    / "04_TICKET-20260708-BO-1900a-2.md"
)
_SRC_DONE = (
    _REPO_ROOT
    / "tickets"
    / "00_inbox"
    / "epics"
    / "EPIC-BuildPipelinePhantomRemediation"
    / "05_bp1200b1_ci_test_gate_blocking.md"
)
_SRC_STANDALONE = _REPO_ROOT / "tickets" / "TICKET-20260716-TKT-500f-11.md"
_SRC_NO_SIGNOFFS = (
    _REPO_ROOT
    / "tickets"
    / "00_inbox"
    / "epics"
    / "EPIC-ACStoreFoundation"
    / "01_schema_validation.md"
)

_NOT_IMPLEMENTED_MSG = "scripts/repair_epic_member_pr_phase.py not yet implemented"

_OLD_AGENT_LINE = "  pull-request: needed\n"
_NEW_AGENT_LINE = "  pull-request: not_needed\n"
_SIGNOFF_LINE = "- [ ] pull-request\n"


# ---------------------------------------------------------------------------
# Fixture-verifying pre-flight (fail loudly if a donor ticket drifts)
# ---------------------------------------------------------------------------


def _assert_donor_tickets_present() -> None:
    for path in (_SRC_NOT_DONE, _SRC_DONE, _SRC_STANDALONE, _SRC_NO_SIGNOFFS):
        assert path.is_file(), (
            f"donor ticket fixture missing from the real store: {path} — "
            "this test file's fixtures are copied verbatim from real tickets; "
            "if this file moved, re-point the constant, do not hand-author a replacement."
        )


_assert_donor_tickets_present()


# ---------------------------------------------------------------------------
# Test-tree builder — real artifacts, one deliberate corruption
# ---------------------------------------------------------------------------


def _build_tree(tmp_path: Path, *, include_malformed: bool) -> dict[str, Path]:
    """Build a realistic tickets/ tree from verbatim copies of real tickets.

    Layout mirrors the real repo: standalone tickets sit directly under
    tickets/00_inbox/, epic-member tickets sit under
    tickets/00_inbox/epics/<Epic>/ — so a naive rglob("*.md") walk would see
    all of them, forcing the implementation to actually filter on path
    rather than merely being handed a pre-filtered directory.
    """
    tickets_root = tmp_path / "tickets"
    epics_root = tickets_root / "00_inbox" / "epics"
    not_done_dir = epics_root / "EPIC-Alpha"
    done_dir = epics_root / "EPIC-Beta"
    inbox_dir = tickets_root / "00_inbox"
    not_done_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    inbox_dir.mkdir(parents=True, exist_ok=True)

    not_done_path = not_done_dir / "ticket_not_done.md"
    shutil.copy2(_SRC_NOT_DONE, not_done_path)

    done_path = done_dir / "ticket_done.md"
    shutil.copy2(_SRC_DONE, done_path)

    standalone_path = inbox_dir / "ticket_standalone.md"
    shutil.copy2(_SRC_STANDALONE, standalone_path)

    paths = {
        "tickets_root": tickets_root,
        "not_done": not_done_path,
        "done": done_path,
        "standalone": standalone_path,
    }

    if include_malformed:
        malformed_dir = epics_root / "EPIC-Gamma"
        malformed_dir.mkdir(parents=True, exist_ok=True)
        malformed_path = malformed_dir / "ticket_malformed.md"
        base_text = _SRC_NOT_DONE.read_text(encoding="utf-8")
        assert "agents:\n" in base_text, (
            "donor ticket's frontmatter shape changed — fixture corruption anchor "
            "'agents:\\n' is no longer present; update this fixture."
        )
        # Deliberate corruption: an unterminated YAML flow sequence. This is the
        # one fixture in this file that is not a pure verbatim copy — it starts
        # from real text and applies a single hand-introduced defect, because no
        # ticket in the real store is naturally malformed and the refusal path
        # needs one to prove itself against.
        corrupted_text = base_text.replace(
            "agents:\n",
            "agents:\n  bad_key: [unterminated\n",
            1,
        )
        malformed_path.write_text(corrupted_text, encoding="utf-8")
        paths["malformed"] = malformed_path

    return paths


def _build_no_signoffs_tree(tmp_path: Path) -> dict[str, Path]:
    """Build a single-file tree from the real no-##-Sign-offs-section donor.

    Isolated in its own tree (rather than folded into `_build_tree`'s 4-file
    matrix) so the run's exit code and counts are unambiguous for this shape
    alone: this ticket is the ONLY candidate, so a correct implementation
    exits 0 (nothing refused) — mixing it into the existing malformed-file
    tree would make the exit-code assertion meaningless.
    """
    tickets_root = tmp_path / "tickets"
    ticket_dir = tickets_root / "00_inbox" / "epics" / "EPIC-Delta"
    ticket_dir.mkdir(parents=True, exist_ok=True)

    ticket_path = ticket_dir / "ticket_no_signoffs.md"
    shutil.copy2(_SRC_NO_SIGNOFFS, ticket_path)

    return {"tickets_root": tickets_root, "ticket": ticket_path}


def _expected_repaired_text(original_text: str) -> str:
    """Compute the exact expected post-repair text via targeted string surgery
    on the ORIGINAL bytes (never via re-parsing + re-dumping YAML), so a test
    comparing against this value proves the implementation edits surgically
    rather than reformatting unrelated fields on re-serialization.
    """
    assert _OLD_AGENT_LINE in original_text, (
        f"donor ticket does not contain the expected agent line {_OLD_AGENT_LINE!r} — "
        "fixture assumption broken, update the donor or this helper."
    )
    assert _SIGNOFF_LINE in original_text, (
        f"donor ticket does not contain the expected Sign-offs line {_SIGNOFF_LINE!r} — "
        "fixture assumption broken, update the donor or this helper."
    )
    updated = original_text.replace(_OLD_AGENT_LINE, _NEW_AGENT_LINE, 1)
    updated = updated.replace(_SIGNOFF_LINE, "", 1)
    return updated


# ---------------------------------------------------------------------------
# Script invocation (reachability: real CLI entry point via subprocess)
# ---------------------------------------------------------------------------


def _run_script(args: list[str]) -> subprocess.CompletedProcess:
    if not _SCRIPT_PATH.is_file():
        raise ImportError(_NOT_IMPLEMENTED_MSG)
    cmd = [sys.executable, str(_SCRIPT_PATH), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Report-count parsing helper
# ---------------------------------------------------------------------------

_COUNT_LABELS = (
    "examined",
    "changed",
    "skipped_done",
    "skipped_not_applicable",
    "refused",
)


def _extract_counts(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in _COUNT_LABELS:
        match = re.search(
            rf"(?im)^\s*[-*]?\s*{re.escape(label)}\s*[:=]\s*(\d+)\b",
            output,
        )
        if match:
            counts[label] = int(match.group(1))
    return counts


# ---------------------------------------------------------------------------
# 1. Main case — needed -> not_needed, Sign-offs row removed, rest untouched
# ---------------------------------------------------------------------------


def test_main_case_epic_member_repaired_byte_for_byte_elsewhere(tmp_path: Path) -> None:
    """An epic-member ticket that is not done: `pull-request: needed` becomes
    `not_needed`, its Sign-offs row disappears, and the expected text is
    computed by editing the ORIGINAL real bytes directly — not by re-parsing
    and re-dumping YAML — so any reformatting of an unrelated field (key
    order, quoting, list style) fails this test.
    """
    tree = _build_tree(tmp_path, include_malformed=False)
    original_text = tree["not_done"].read_text(encoding="utf-8")
    expected_text = _expected_repaired_text(original_text)

    result = _run_script(["--tickets-dir", str(tree["tickets_root"])])

    actual_text = tree["not_done"].read_text(encoding="utf-8")
    assert actual_text == expected_text, (
        "repaired ticket is not byte-identical to the original with only the "
        "two targeted edits applied — some other byte changed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# 2. not_needed, never signed_off — asserted explicitly and in isolation
# ---------------------------------------------------------------------------


def test_written_value_is_exactly_not_needed_never_signed_off(tmp_path: Path) -> None:
    """The single most important invariant: no per-ticket pull-request phase
    ever ran for an epic member, so the repaired value MUST be `not_needed`
    and must NEVER be `signed_off` — a test that only checks "no longer
    'needed'" would pass an implementation that phantom-signs-off the phase.
    """
    tree = _build_tree(tmp_path, include_malformed=False)

    _run_script(["--tickets-dir", str(tree["tickets_root"])])

    content = tree["not_done"].read_text(encoding="utf-8")
    agent_lines = [
        line for line in content.splitlines() if line.strip().startswith("pull-request:")
    ]
    assert len(agent_lines) == 1, (
        f"expected exactly one 'pull-request:' agent line, found: {agent_lines!r}"
    )
    assert agent_lines[0].strip() == "pull-request: not_needed", (
        f"expected 'pull-request: not_needed', got {agent_lines[0].strip()!r} "
        "(writing 'signed_off' here would be a phantom sign-off — no per-ticket "
        "pull-request phase ever ran for an epic member)"
    )
    assert "signed_off" not in agent_lines[0]


# ---------------------------------------------------------------------------
# 3. Already-done tickets are untouched
# ---------------------------------------------------------------------------


def test_already_done_ticket_is_byte_for_byte_untouched(tmp_path: Path) -> None:
    """A done epic-member ticket is not this repair's to change — flipping a
    phase on a finished ticket rewrites a record that is no longer live.
    """
    tree = _build_tree(tmp_path, include_malformed=False)
    original_text = tree["done"].read_text(encoding="utf-8")
    original_mtime = tree["done"].stat().st_mtime_ns

    _run_script(["--tickets-dir", str(tree["tickets_root"])])

    assert tree["done"].read_text(encoding="utf-8") == original_text, (
        "a status: done epic-member ticket was modified by the repair — "
        "done tickets must be left completely untouched"
    )
    assert tree["done"].stat().st_mtime_ns == original_mtime, (
        "a status: done ticket's mtime changed even though its content check "
        "passed — the file must not be written to at all, not merely "
        "written back identically"
    )


# ---------------------------------------------------------------------------
# 4. Non-epic tickets are untouched
# ---------------------------------------------------------------------------


def test_standalone_ticket_outside_epics_path_is_untouched(tmp_path: Path) -> None:
    """A standalone ticket (outside tickets/00_inbox/epics/) keeps
    `pull-request: needed` — for a standalone ticket the phase genuinely
    runs. This ticket sits in the SAME --tickets-dir walk as the epic
    tickets, so this proves the epics-path filter is real, not merely that
    the ticket was out of scope of whatever directory was scanned.
    """
    tree = _build_tree(tmp_path, include_malformed=False)
    original_text = tree["standalone"].read_text(encoding="utf-8")
    assert "pull-request: needed" in original_text

    _run_script(["--tickets-dir", str(tree["tickets_root"])])

    assert tree["standalone"].read_text(encoding="utf-8") == original_text, (
        "a standalone (non-epic-member) ticket was modified — an "
        "implementation that walks the whole tickets tree without an "
        "epics-path filter breaks every standalone ticket carrying "
        "pull-request: needed"
    )


# ---------------------------------------------------------------------------
# 5. Idempotent — safe to re-run as more epic tickets are generated
# ---------------------------------------------------------------------------


def test_second_run_is_idempotent_and_reports_zero_changes(tmp_path: Path) -> None:
    """More epic tickets will be generated before the upstream generator fix
    lands, so this script WILL be re-run against a tree it has already
    partially repaired. The second run must change nothing.
    """
    tree = _build_tree(tmp_path, include_malformed=False)

    first = _run_script(["--tickets-dir", str(tree["tickets_root"])])
    first_counts = _extract_counts(first.stdout + first.stderr)
    content_after_first = tree["not_done"].read_text(encoding="utf-8")

    second = _run_script(["--tickets-dir", str(tree["tickets_root"])])
    second_counts = _extract_counts(second.stdout + second.stderr)
    content_after_second = tree["not_done"].read_text(encoding="utf-8")

    assert content_after_first == content_after_second, (
        "running the repair a second time changed a file that was already repaired"
    )
    assert first_counts.get("changed") == 1, (
        f"expected the first run to report changed: 1, got {first_counts!r}\n"
        f"stdout:\n{first.stdout}\nstderr:\n{first.stderr}"
    )
    assert second_counts.get("changed") == 0, (
        f"expected the second (idempotent) run to report changed: 0, got {second_counts!r}\n"
        f"stdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    )


# ---------------------------------------------------------------------------
# 6. Refuses rather than guesses on unparseable frontmatter
# ---------------------------------------------------------------------------


def test_refuses_unparseable_frontmatter_names_file_and_exits_nonzero(tmp_path: Path) -> None:
    """Absent evidence is not permission: a ticket whose frontmatter cannot
    be parsed must be named in the output, must never be written to, and
    must make the whole run exit non-zero.
    """
    tree = _build_tree(tmp_path, include_malformed=True)
    malformed_path = tree["malformed"]
    original_text = malformed_path.read_text(encoding="utf-8")
    original_mtime = malformed_path.stat().st_mtime_ns

    result = _run_script(["--tickets-dir", str(tree["tickets_root"])])

    assert result.returncode != 0, (
        "a run containing an unparseable ticket must exit non-zero\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined_output = result.stdout + result.stderr
    assert malformed_path.name in combined_output, (
        "the unparseable ticket's file name must be named in the run's output "
        f"so an operator can find it; got:\n{combined_output}"
    )
    assert malformed_path.read_text(encoding="utf-8") == original_text, (
        "the unparseable ticket must never be written to — refuse, don't guess"
    )
    assert malformed_path.stat().st_mtime_ns == original_mtime, (
        "the unparseable ticket's mtime changed — it must not be opened for writing at all"
    )


# ---------------------------------------------------------------------------
# 7. --dry-run writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_writes_nothing_but_still_reports_the_change(tmp_path: Path) -> None:
    """--dry-run must be side-effect-free on disk (content AND mtime) while
    still telling the operator what it would do — a silent dry-run is
    useless for reviewing 316 files before committing to a real run.
    """
    tree = _build_tree(tmp_path, include_malformed=False)
    mtimes_before = {
        key: tree[key].stat().st_mtime_ns for key in ("not_done", "done", "standalone")
    }
    texts_before = {key: tree[key].read_text(encoding="utf-8") for key in mtimes_before}

    result = _run_script(["--dry-run", "--tickets-dir", str(tree["tickets_root"])])

    for key in mtimes_before:
        assert tree[key].read_text(encoding="utf-8") == texts_before[key], (
            f"--dry-run modified {key} on disk"
        )
        assert tree[key].stat().st_mtime_ns == mtimes_before[key], (
            f"--dry-run touched {key}'s mtime on disk"
        )

    combined_output = result.stdout + result.stderr
    assert tree["not_done"].name in combined_output, (
        "dry-run must report which ticket it would change\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "not_needed" in combined_output, (
        "dry-run must report the value it would write, not just the file name"
    )


# ---------------------------------------------------------------------------
# 8. Report counts add up
# ---------------------------------------------------------------------------


def test_report_counts_are_self_consistent(tmp_path: Path) -> None:
    """An operator repairing 316 real files needs the script to agree with
    itself: examined must equal the sum of every bucket a file can land in.
    """
    tree = _build_tree(tmp_path, include_malformed=True)

    result = _run_script(["--tickets-dir", str(tree["tickets_root"])])

    counts = _extract_counts(result.stdout + result.stderr)
    for label in _COUNT_LABELS:
        assert label in counts, (
            f"report is missing the '{label}: <int>' line\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    assert counts["examined"] == (
        counts["changed"]
        + counts["skipped_done"]
        + counts["skipped_not_applicable"]
        + counts["refused"]
    ), f"reported counts do not sum to examined: {counts!r}"

    # This fixture tree has exactly one file in each bucket.
    assert counts["examined"] == 4, counts
    assert counts["changed"] == 1, counts
    assert counts["skipped_done"] == 1, counts
    assert counts["skipped_not_applicable"] == 1, counts
    assert counts["refused"] == 1, counts


# ---------------------------------------------------------------------------
# 9. Cross-layer seam (Rule 3): repaired output fed into the REAL downstream
#    consumer — check_ticket_signoff_parity.py's _validate_ticket_content.
# ---------------------------------------------------------------------------

_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"


def _load_real_signoff_parity_validator():
    """Import the REAL downstream consumer of the artifact this repair
    produces. Not mocked, not re-implemented — the actual pre-commit guard
    module that reads a ticket's agents: map against its Sign-offs checklist.
    """
    if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
        sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
    import importlib

    module = importlib.import_module("check_ticket_signoff_parity")
    return module._validate_ticket_content


def test_seam_repaired_ticket_satisfies_real_signoff_parity_consumer(
    tmp_path: Path,
) -> None:
    """Rule 3 — pipe the repair script's REAL on-disk output into the REAL
    check_ticket_signoff_parity consumer (not a mock of it) and assert the
    consumer reports zero pull-request-related violations. That consumer's
    `_check_parity` is exactly the rule this repair exists to satisfy: a
    `not_needed` agent must be absent from `## Sign-offs`. A repair that
    writes the right frontmatter value but leaves an orphaned Sign-offs row
    (or vice versa) fails this test even though it might pass a same-module
    unit check.
    """
    if not _SCRIPT_PATH.is_file():
        raise ImportError(_NOT_IMPLEMENTED_MSG)

    validate_ticket_content = _load_real_signoff_parity_validator()

    tree = _build_tree(tmp_path, include_malformed=False)
    _run_script(["--tickets-dir", str(tree["tickets_root"])])

    repaired_content = tree["not_done"].read_text(encoding="utf-8")
    violations = validate_ticket_content(repaired_content, str(tree["not_done"]), set())
    pull_request_violations = [v for v in violations if "pull-request" in v]

    assert pull_request_violations == [], (
        "the repaired ticket fails the REAL downstream signoff-parity consumer:\n"
        f"{pull_request_violations!r}\nfull violation list: {violations!r}"
    )


# ---------------------------------------------------------------------------
# 10. No-##-Sign-offs-section shape — repair without inventing a section
# ---------------------------------------------------------------------------


def test_no_signoffs_section_shape_is_repaired_not_refused(tmp_path: Path) -> None:
    """17 of the 332 qualifying tickets use an older template with no
    `## Sign-offs` section at all (real donor:
    tickets/00_inbox/epics/EPIC-ACStoreFoundation/01_schema_validation.md).
    Per `_check_parity` in `_signoff_parity_checks.py`, a `not_needed` agent
    with no `## Sign-offs` section is trivially compliant — there is no row
    to remove, so the frontmatter flip alone is the complete repair for this
    shape. This ticket must land in `changed`, not `refused`, and the run
    must exit 0 when it is the only candidate.

    This is a genuinely different assertion from the main-case test: it
    proves the absence of a `## Sign-offs` section is treated as "nothing to
    remove" rather than as "refuse, the expected shape is missing" — and
    that the script does not helpfully author a `## Sign-offs` section that
    never existed (it has no standing to author that record).
    """
    tree = _build_no_signoffs_tree(tmp_path)
    original_text = tree["ticket"].read_text(encoding="utf-8")
    assert "## Sign-offs" not in original_text, (
        "donor ticket's shape changed — it is supposed to have NO ## Sign-offs "
        "section; this fixture no longer represents the shape under test"
    )
    assert _OLD_AGENT_LINE in original_text, (
        f"donor ticket does not contain the expected agent line {_OLD_AGENT_LINE!r} — "
        "fixture assumption broken, update the donor or this test."
    )
    # Expected text: ONLY the agents-map line changes. Computed by editing the
    # original bytes directly (never via re-parse/re-dump), same discipline as
    # the main-case test's `_expected_repaired_text`.
    expected_text = original_text.replace(_OLD_AGENT_LINE, _NEW_AGENT_LINE, 1)

    result = _run_script(["--tickets-dir", str(tree["tickets_root"])])

    actual_text = tree["ticket"].read_text(encoding="utf-8")
    assert actual_text == expected_text, (
        "repaired no-Sign-offs-section ticket is not byte-identical to the "
        "original with only the agents-map line changed — some other byte "
        "changed, or a ## Sign-offs section was invented.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "## Sign-offs" not in actual_text, (
        "the script invented a ## Sign-offs section that never existed in the "
        "original ticket — it has no standing to author that record"
    )

    assert result.returncode == 0, (
        "the run must exit 0 when the no-Sign-offs-section ticket is the only "
        "candidate and it is correctly classified as changed, not refused\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    counts = _extract_counts(result.stdout + result.stderr)
    assert counts.get("changed") == 1, (
        f"expected changed: 1, got {counts!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert counts.get("refused") == 0, (
        f"expected refused: 0 — the missing ## Sign-offs section must not be "
        f"treated as a refusal, got {counts!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert counts.get("examined") == 1, counts
