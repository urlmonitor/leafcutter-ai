"""
MODULE: unit_tests/ac_store/test_generator_frontmatter_gaps.py
GOAL: RED test stubs for two verified defects in
    scripts/ac_store/generate_ticket_from_ac.py, plus one bonus defect found
    live in the same code path.

    Defect A (ACD-400b-7 / ACD-400b-7-i): the generator copies the source AC's
    `depends_on` (a list of AC ids, typically the AC's own parent) VERBATIM
    into the generated ticket's frontmatter `depends_on`
    (generate_ticket_from_ac.py ~line 1847:
    ``"depends_on": ac.get("depends_on") or []``). The ticket frontmatter
    guard (templates/hooks/ticket_frontmatter_guard.py::_check_depends_on)
    requires every `depends_on` entry to resolve to a SIBLING TICKET FILE in
    the same folder — an AC id never resolves, so the guard hard-blocks the
    generated ticket. VERIFIED LIVE: generating tickets for ACD-400b-6,
    ACD-400b-7, and BO-2500a-6 each produced `depends_on: [<parent-AC-id>]`,
    and the guard rejected the file with
    "depends_on references missing file: '<parent-AC-id>'".

    Defect B (ACD-400b-6 / ACD-400b-6-i): `files_touched` derivation can
    OMIT the AC's real implementation source file. The actual mechanism
    (confirmed by reading `_extract_local_paths` in
    generate_ticket_from_ac.py): that helper requires
    ``isinstance(link, dict)`` for every `doc_links` entry and silently
    `continue`s past any entry that is a PLAIN STRING — even a local `.py`
    path with no URL. Plain-string `doc_links` entries are an explicitly
    supported AC-store schema shape (see the "must accept a doc_links entry
    in either supported shape" implementation note on ACD-400b-6), so this is
    a real, silent data-loss bug, not a schema violation. This exactly
    reproduces the VERIFIED case on ACD-400a-3.yaml, whose `doc_links` is a
    list of plain strings including both
    `scripts/ac_store/scan_ac_store.py` (the behavior's home file) and
    `scripts/ac_store/ac_prioritizer.py` (a delegating helper). The generated
    ticket's `files_touched` came back as only
    `[scripts/ac_store/ac_prioritizer.py]` — extracted incidentally from an
    `it_requirements` prose bullet that happens to name that path — while
    `scan_ac_store.py` was silently dropped because it never appears in any
    prose bullet and its `doc_links` entry is a bare string.

    Bonus defect (found live on BO-2500a-6, same code path): a dotfile-
    prefixed path such as ``.github/workflows/ci.yml``, named in a
    list-form `it_requirements` prose bullet, has its leading ``.``
    stripped in the generated `files_touched` (emitted as
    ``github/workflows/ci.yml``). Mechanism confirmed INSIDE this file:
    `_PROSE_PATH_TOKEN_RE` (generate_ticket_from_ac.py ~line 130) anchors on
    ``[A-Za-z0-9_]`` as the path token's *first* character — a ``.`` is not
    in that class, so `re.finditer` finds its leftmost match starting one
    character late, at ``g`` in ``github/...``, and the leading dot is never
    part of the captured token. This is NOT a `doc_links` bug: a `doc_links`
    entry's `path` value is used verbatim with no regex, so an explicit
    ``{path: ".github/workflows/ci.yml", ...}`` dict entry survives fine —
    only the *prose-bullet* extraction path used for list-form
    `it_requirements` is affected.

ARCHITECTURE: All tests are BEHAVIORAL — they invoke
    generate_ticket_from_ac.py as a real subprocess against a temp AC store
    and temp tickets root (mirroring the established pattern in
    tests/ac_store/test_generate_ticket_from_ac.py), then parse the actual
    generated ticket's YAML frontmatter. Fixture AC YAML files are written via
    `yaml.dump()` — never a hand-indented literal — per the project's
    fixture-authenticity rule (a hand-typed fixture reproduces the author's
    mental model, which is the same blind spot that hides real-format bugs).
    The frontmatter guard is invoked the way it is actually invoked in
    production: as a subprocess reading a PostToolUse JSON payload from
    stdin naming the file path (see `_run_frontmatter_guard`).

MUST BE RED before the corresponding fix lands in generate_ticket_from_ac.py.
    Run with ``AC_ENFORCE_STRICT=1`` to see the true pass/fail state — the
    `pytest_ac_enforcement` plugin otherwise downgrades assertion failures
    covering not-done ACs to XFAIL so they do not block CI.

TICKETS: TICKET-20260813-ACD-400b-6.md, TICKET-20260813-ACD-400b-7.md
COVERS: ACD-400b-6, ACD-400b-6-i, ACD-400b-7, ACD-400b-7-i
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
_GUARD_SCRIPT = _REPO_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"


class _FrontmatterError(ValueError):
    """Raised when a generated ticket's frontmatter cannot be parsed."""


# ---------------------------------------------------------------------------
# Shared fixture / invocation helpers
# ---------------------------------------------------------------------------

_BASE_AC_FIELDS: dict = {
    "component": "ac-driven-dev",
    "level": "L2",
    "status": "active",
    "req_status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "estimated_complexity": "S",
    "change_target": "code",
    "risk_surface": "contract_boundary",
    "doc_links": [],
    "depends_on": [],
    "implemented_by": [],
}


def _ac(ac_id: str, **overrides: object) -> dict:
    """Build a minimal, guard-satisfying AC record, merging in *overrides*.

    Args:
        ac_id: The AC id (used to derive a default title).
        **overrides: Fields that replace the base defaults (e.g. depends_on,
            doc_links, it_requirements, criteria).

    Returns:
        A dict ready to be written as an AC YAML fixture.
    """
    data: dict = dict(_BASE_AC_FIELDS)
    data["title"] = f"Fixture for {ac_id}"
    data["criteria"] = (
        "Given a test fixture\nWhen the generator runs\nThen a ticket is produced.\n"
    )
    data.update(overrides)
    return data


def _write_ac(ac_dir: Path, ac_id: str, data: dict) -> Path:
    """Write a real AC YAML fixture via yaml.dump — never a hand-indented literal.

    Args:
        ac_dir: Directory to write the AC YAML file into.
        ac_id: The AC id (used for both the filename and the `id` field).
        data: The AC record fields (without `id` — it is injected here).

    Returns:
        Path to the written AC YAML file.
    """
    record = {"id": ac_id, **data}
    ac_path = ac_dir / f"{ac_id}.yaml"
    with open(ac_path, "w", encoding="utf-8") as fh:
        yaml.dump(record, fh, default_flow_style=False, allow_unicode=True)
    return ac_path


def _run_generator(
    ac_id: str, ac_root: Path, tickets_root: Path
) -> subprocess.CompletedProcess:
    """Run generate_ticket_from_ac.py as a real subprocess against temp roots.

    Args:
        ac_id: The AC id to generate a ticket for.
        ac_root: Temp directory containing the fixture AC YAML.
        tickets_root: Temp directory to write the generated ticket into.

    Returns:
        The completed subprocess result (stdout/stderr/returncode captured).
    """
    cmd = [
        sys.executable,
        str(_GEN_SCRIPT),
        "--ac",
        ac_id,
        "--ac-root",
        str(ac_root),
        "--tickets-root",
        str(tickets_root),
        # TKT-600b-1-i: the generator refuses rather than guess when the
        # phase-deferral declaration is location-dependent. These fixtures are
        # standalone tickets, so the kind is declared explicitly. Note this is
        # NOT boilerplate to copy blindly into a new test — a test covering an
        # epic member must pass "epic_member", or it will assert against the
        # wrong phase record and pass for the wrong reason.
        "--location-kind",
        "standalone",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _generate_ticket(ac_id: str, ac_dir: Path, tickets_dir: Path, ac_data: dict) -> Path:
    """Write the fixture AC, generate its ticket, and return the ticket's path.

    Args:
        ac_id: The AC id.
        ac_dir: Temp AC store root (already created).
        tickets_dir: Temp tickets root (already created).
        ac_data: AC record fields (see `_ac`).

    Returns:
        Path to the single generated ticket file.
    """
    _write_ac(ac_dir, ac_id, ac_data)
    result = _run_generator(ac_id, ac_dir, tickets_dir)
    assert result.returncode == 0, (
        f"generator failed for {ac_id}: rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    matches = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
    assert len(matches) == 1, f"expected exactly one ticket for {ac_id}, got {matches}"
    return matches[0]


def _parse_frontmatter(ticket_path: Path) -> dict:
    """Parse the YAML frontmatter block from a generated ticket file.

    Args:
        ticket_path: Path to the generated ticket markdown file.

    Returns:
        The parsed frontmatter mapping.

    Raises:
        _FrontmatterError: When the file has no closed frontmatter block, or
            the block does not parse to a mapping.
    """
    content = ticket_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise _FrontmatterError(f"{ticket_path}: no frontmatter block")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise _FrontmatterError(f"{ticket_path}: frontmatter block not closed")
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        raise _FrontmatterError(f"{ticket_path}: frontmatter did not parse to a mapping")
    return fm


def _make_project_root_marker(root: Path) -> None:
    """Create a project-root marker directly above the tickets/ folder.

    ``ticket_frontmatter_guard.find_project_root()`` walks up from the ticket
    file looking for one of ``.git``, ``CLAUDE.md``, ``pyproject.toml``, or
    ``requirements-dev.txt`` within 15 parent levels. A bare ``tmp_path``
    fixture has NONE of these anywhere above it, so without this marker the
    guard silently prints a WARNING and returns ``None`` from
    ``_resolve_ticket_path`` — the hook then exits 0 with NO output at all,
    which this test suite's own ``_run_frontmatter_guard`` helper would
    (wrongly) read as "not blocked". That is a false green: the guard never
    actually validated anything. Creating an empty ``.git`` directory here
    (the guard only checks ``.exists()``, never that it is a real repo) makes
    the guard actually run its checks against the generated ticket.

    Args:
        root: The tmp_path root whose immediate child is the ``tickets/``
            directory passed to the generator as ``--tickets-root``.
    """
    (root / ".git").mkdir(exist_ok=True)


def _run_frontmatter_guard(ticket_path: Path) -> tuple[bool, str]:
    """Invoke the REAL ticket_frontmatter_guard.py the way it is actually invoked.

    The guard is a Claude Code PostToolUse hook: it reads a JSON payload from
    stdin naming the file that was just written/edited
    (``{"tool_input": {"file_path": <path>}}``) and prints
    ``{"decision": "block", "reason": ...}`` to stdout when it finds a
    violation — otherwise it prints nothing. Per the hook's own documented
    contract ("Exit 0 with {decision: block} = inject the reason back to
    Claude"), the OS process exit code is ALWAYS 0 regardless of outcome — so
    the real pass/fail signal is whether a block decision was printed, not
    the exit code. This helper asserts the process did not crash (exit 0)
    AND returns whether a block decision was emitted, so callers can assert
    on the actual guard verdict rather than a signal that never varies.

    Args:
        ticket_path: Path to the generated ticket file to validate.

    Returns:
        ``(blocked, reason)`` — ``blocked`` is True when the guard emitted a
        block decision; ``reason`` is the guard's explanation (empty when
        not blocked).
    """
    payload = json.dumps({"tool_input": {"file_path": str(ticket_path)}})
    result = subprocess.run(
        [sys.executable, str(_GUARD_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"guard process crashed (it must always exit 0 per its own contract): "
        f"rc={result.returncode} stderr={result.stderr}"
    )
    stdout = (result.stdout or "").strip()
    if not stdout:
        return False, ""
    try:
        decision = json.loads(stdout)
    except json.JSONDecodeError:
        return False, ""
    if isinstance(decision, dict) and decision.get("decision") == "block":
        return True, str(decision.get("reason", ""))
    return False, ""


# ---------------------------------------------------------------------------
# Defect A — ACD-400b-7 / ACD-400b-7-i: depends_on leaks AC ids
# ---------------------------------------------------------------------------


class TestDependsOnDoesNotLeakAcIds:
    """AC-level depends_on must never leak into the generated ticket's
    frontmatter depends_on — the frontmatter guard hard-blocks any AC id
    there because it expects sibling ticket filenames.
    """

    def test_generated_standalone_ticket_depends_on_excludes_ac_ids(self, tmp_path: Path) -> None:
        # covers: ACD-400b-7
        """ACD-400b-7: a ticket generated from an AC whose depends_on lists AC
        ids has a depends_on that contains none of those AC ids.

        Must be RED before the fix: generate_ticket_from_ac.py currently does
        ``"depends_on": ac.get("depends_on") or []`` (verbatim copy), so the
        parent AC id survives into the ticket frontmatter unchanged.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9000a-1"
        parent_id = "ZZGAP-9000a"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose depends_on lists its own parent AC id\n"
                "When the generator produces a standalone ticket from that AC\n"
                "Then the generated ticket's depends_on excludes AC identifiers.\n"
            ),
            depends_on=[parent_id],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        depends_on = fm.get("depends_on") or []
        assert parent_id not in depends_on, (
            f"generated ticket depends_on leaked the AC-level dependency "
            f"{parent_id!r}: depends_on={depends_on!r}. generate_ticket_from_ac.py "
            f"currently copies ac.get('depends_on') verbatim (~line 1847) instead "
            f"of scoping the ticket's depends_on to ticket-level references."
        )

    def test_generated_ticket_passes_frontmatter_guard(self, tmp_path: Path) -> None:
        # covers: ACD-400b-7
        """ACD-400b-7: running templates/hooks/ticket_frontmatter_guard.py
        against the generated ticket must not emit a block decision (no
        depends_on validation error).

        Must be RED before the fix: the guard's _check_depends_on requires
        every depends_on entry to resolve to a sibling ticket file; an AC id
        never resolves, so the real guard rejects the file today.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        _make_project_root_marker(tmp_path)

        ac_id = "ZZGAP-9000b-1"
        parent_id = "ZZGAP-9000b"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose depends_on lists its own parent AC id\n"
                "When the generator produces a standalone ticket from that AC\n"
                "Then the frontmatter guard does not reject the ticket.\n"
            ),
            depends_on=[parent_id],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)

        blocked, reason = _run_frontmatter_guard(ticket_path)
        assert not blocked, (
            f"the real ticket_frontmatter_guard.py rejected the generated ticket: "
            f"{reason}. Invoked exactly as Claude Code's PostToolUse hook invokes "
            f"it (JSON payload on stdin naming the written file)."
        )

    def test_ticket_from_ac_depending_on_parent_not_blocked_by_guard(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-400b-7-i
        """ACD-400b-7-i: the specific real-world case VERIFIED LIVE — an AC
        whose depends_on is exactly [<its-own-parent-AC-id>] must generate a
        ticket the guard accepts (exit 0 / no block decision), with no AC id
        surviving into the ticket's own depends_on.

        Must be RED before the fix: this reproduces the exact live failure —
        generating tickets for ACD-400b-6, ACD-400b-7, and BO-2500a-6 each
        produced depends_on: [<parent-AC-id>], and the guard rejected the
        file with "depends_on references missing file: '<parent-AC-id>'".
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        _make_project_root_marker(tmp_path)

        ac_id = "ZZGAP-9000c-1"
        parent_id = "ZZGAP-9000c"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose only depends_on entry is its own parent AC\n"
                "When the generator produces the standalone ticket\n"
                "Then the commit is not hard-blocked by the guard.\n"
            ),
            depends_on=[parent_id],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        depends_on = fm.get("depends_on") or []
        assert parent_id not in depends_on, (
            f"depends_on must not contain the parent AC id {parent_id!r}; "
            f"got depends_on={depends_on!r}."
        )

        blocked, reason = _run_frontmatter_guard(ticket_path)
        assert not blocked, (
            f"guard hard-blocked a ticket generated from an AC that depends only "
            f"on its own parent: {reason}. VERIFIED LIVE on ACD-400b-6, "
            f"ACD-400b-7, and BO-2500a-6."
        )


# ---------------------------------------------------------------------------
# Defect B — ACD-400b-6 / ACD-400b-6-i: files_touched drops the home file
# ---------------------------------------------------------------------------


class TestFilesTouchedNeverDropsImplementationSource:
    """files_touched must never silently omit a local implementation source
    path — even when the AC lists it as a PLAIN STRING doc_links entry (a
    supported doc_links shape per the AC-store schema).

    Real mechanism (confirmed by reading generate_ticket_from_ac.py):
    `_extract_local_paths` requires ``isinstance(link, dict)`` for every
    doc_links entry and `continue`s past any bare-string entry — dropping it
    from files_touched entirely, regardless of its extension or content.
    This is the exact mechanism behind the VERIFIED ACD-400a-3 bug.
    """

    def test_files_touched_includes_the_acs_implementation_source(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-400b-6
        """ACD-400b-6: generating a ticket from an AC whose doc_links names a
        real local source file (as a plain string) must include that file in
        files_touched.

        Must be RED before the fix: _extract_local_paths()'s
        isinstance(link, dict) guard skips plain-string doc_links entries
        entirely, so this path never reaches files_touched.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9001a-1"
        home_file = "scripts/ac_store/scan_ac_store.py"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose doc_links names a local source file as a plain "
                "string\n"
                "When the generator produces the ticket for that AC\n"
                "Then files_touched contains that source file.\n"
            ),
            # Plain-string doc_links entry — the AC-store schema's OTHER
            # supported shape (see ACD-400a-3.yaml, the verified live case).
            doc_links=[home_file],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert home_file in files_touched, (
            f"files_touched must contain the AC's real implementation source "
            f"{home_file!r} even though it is listed as a plain-string doc_links "
            f"entry (not the {{path, relationship, status}} dict form). "
            f"_extract_local_paths() currently requires isinstance(link, dict) and "
            f"skips bare-string entries entirely — this is the exact mechanism "
            f"behind the verified ACD-400a-3 bug. Got files_touched={files_touched!r}."
        )

    def test_files_touched_does_not_drop_home_file_when_helper_also_linked(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-400b-6-i
        """ACD-400b-6-i: reproduces the VERIFIED ACD-400a-3 shape almost
        verbatim — doc_links is a list of plain-string paths, with the
        delegating helper (ac_prioritizer.py) also independently extractable
        from an it_requirements prose bullet, while the home file
        (scan_ac_store.py) is ONLY named as a bare-string doc_links entry.
        Both must survive into files_touched.

        Must be RED before the fix: the real, verified bug generated
        files_touched=['scripts/ac_store/ac_prioritizer.py'] with the home
        file missing entirely.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9001b-1"
        home_file = "scripts/ac_store/scan_ac_store.py"
        helper_file = "scripts/ac_store/ac_prioritizer.py"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose doc_links reference two local source files — a "
                "delegating helper listed first and the file where the behavior "
                "actually lives listed second\n"
                "When the generator produces the ticket for that AC\n"
                "Then files_touched contains the behavior's home file\n"
                "And files_touched also contains the delegating helper.\n"
            ),
            doc_links=[
                "docs/acceptance-criteria/index.yaml",
                "docs/reference/ac-schema.md",
                helper_file,
                home_file,
            ],
            it_requirements=[
                "The fix must live in the scanner's classification path; do not "
                "add a second, parallel blocking codepath.",
                f"{helper_file} must produce results consistent with the "
                f"scanner's classification (share or mirror the same "
                f"ancestor-exclusion logic; no divergent blocking rules).",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert home_file in files_touched, (
            f"the AC's behavior home file {home_file!r} must never be dropped "
            f"from files_touched even when a delegating helper ({helper_file!r}) "
            f"is also linked and happens to be independently extractable from "
            f"prose. Got files_touched={files_touched!r} — this reproduces the "
            f"VERIFIED ACD-400a-3 bug (files_touched=["
            f"'scripts/ac_store/ac_prioritizer.py'] with scan_ac_store.py "
            f"silently missing)."
        )
        assert helper_file in files_touched, (
            f"the delegating helper {helper_file!r} must also remain present in "
            f"files_touched. Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# Bonus defect found live — leading-dot stripped from prose-extracted paths
# ---------------------------------------------------------------------------


class TestFilesTouchedPreservesDotfilePrefixedPaths:
    """A dotfile-prefixed path (e.g. '.github/workflows/ci.yml'), named in a
    list-form it_requirements prose bullet, must survive files_touched
    extraction with its leading '.' intact.

    Real mechanism (confirmed INSIDE generate_ticket_from_ac.py, not
    elsewhere): `_PROSE_PATH_TOKEN_RE` anchors on ``[A-Za-z0-9_]`` as the
    path token's first character, which excludes '.'. `re.finditer` then
    finds its leftmost match starting one character late (at 'g' in
    'github/...'), so the leading dot is never captured. A doc_links entry's
    explicit `path` value is NOT affected — it is used verbatim with no
    regex — so this bug is specific to the prose-bullet extraction path used
    for list-form it_requirements (generate_ticket_from_ac.py
    `_extract_paths_from_prose`, ~lines 429-465).
    """

    def test_files_touched_preserves_leading_dot_paths(self, tmp_path: Path) -> None:
        # covers: ACD-400b-8
        """Observed live on BO-2500a-6: generating that ticket emitted
        'github/workflows/ci.yml' with the leading dot stripped instead of
        '.github/workflows/ci.yml'.

        Must be RED before the fix: _PROSE_PATH_TOKEN_RE's first-character
        class excludes '.', so the regex match starts one character into the
        real token, silently dropping the leading dot.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9002a-1"
        dotfile_path = ".github/workflows/ci.yml"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given an AC whose it_requirements names a dotfile-prefixed path\n"
                "When the generator produces the ticket for that AC\n"
                "Then files_touched preserves the leading dot of that path.\n"
            ),
            it_requirements=[
                f"Add a new step to {dotfile_path} that runs the new check",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert dotfile_path in files_touched, (
            f"a dotfile-prefixed path named in prose ({dotfile_path!r}) must "
            f"survive files_touched extraction with its leading '.' intact. "
            f"_PROSE_PATH_TOKEN_RE requires the token to START with "
            f"[A-Za-z0-9_], so the leading '.' is excluded from the match and "
            f"the token is captured one character late as "
            f"'github/workflows/ci.yml'. Got files_touched={files_touched!r}."
        )
