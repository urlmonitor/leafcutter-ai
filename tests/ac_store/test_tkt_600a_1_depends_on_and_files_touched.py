"""
MODULE: tests/ac_store/test_tkt_600a_1_depends_on_and_files_touched.py
GOAL: Failing test stubs for TKT-600a-1 — generate_ticket_from_ac.py must
    exclude prose-illustration paths from files_touched and emit a
    guard-valid depends_on (structural-parent AC ids dropped, sibling AC ids
    with a co-located ticket translated to that ticket's filename, dangling
    AC ids with no ticket in scope dropped).
BUSINESS CONTEXT: TKT-600a-1 (source AC docs/acceptance-criteria/
    ticket-creation/TKT-600-clean-generated-frontmatter/TKT-600a-1.yaml).
    Two live defects observed during the BO-2600 build: (1)
    _build_files_touched -> _extract_paths_from_prose harvests any
    '/'-containing, known-extension token out of list-form it_requirements
    bullets, so illustrative example paths used only to describe a scenario
    land in files_touched; (2) _build_frontmatter currently hardcodes
    depends_on: [] unconditionally, which happens to drop dangling AC ids
    but never TRANSLATES a real sibling dependency to its co-located ticket
    filename, so a legitimate ticket-level dependency is silently lost.
ARCHITECTURE: Tests 1-2 call _build_files_touched directly (pure-function
    unit tests) after inserting scripts/ac_store onto sys.path, mirroring how
    generate_ticket_from_ac.py's own sibling-module loading works. Tests 3-4
    drive the REAL CLI entry point end-to-end via subprocess (real-artifact
    round trip per BP-1100f-2: the ticket file is actually written to a temp
    tickets_root and read back off disk), then validate the resulting
    depends_on both by direct assertion and by running the real
    templates/hooks/ticket_frontmatter_guard.py `validate()`/
    `_check_depends_on()` functions against the on-disk ticket — the actual
    guard that will reject the generated ticket at commit time.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
GEN_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
GUARD_SCRIPT = WORKTREE_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"

_AC_STORE_DIR = str(WORKTREE_ROOT / "scripts" / "ac_store")
if _AC_STORE_DIR not in sys.path:
    sys.path.insert(0, _AC_STORE_DIR)

import generate_ticket_from_ac as gen_module  # noqa: E402


def _load_guard_module():
    """Import templates/hooks/ticket_frontmatter_guard.py by file path.

    The module lives outside any importable package (it is a deployed hook
    template), so it must be loaded via importlib.util.spec_from_file_location
    rather than a normal ``import`` statement.
    """
    spec = importlib.util.spec_from_file_location(
        "ticket_frontmatter_guard_under_test", GUARD_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_ac(directory: Path, ac_id: str, overrides: dict | None = None) -> Path:
    """Write a minimal valid AC YAML file for testing."""
    defaults = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "component": "test",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "criteria": textwrap.dedent("""\
            Given a test condition,
            When the generator runs,
            Then a ticket is produced.
        """),
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "depends_on": [],
        "doc_links": [],
        "implemented_by": [],
    }
    if overrides:
        defaults.update(overrides)
    ac_file = directory / f"{ac_id}.yaml"
    with open(ac_file, "w", encoding="utf-8") as fh:
        yaml.dump(defaults, fh, default_flow_style=False, allow_unicode=True)
    return ac_file


def _run_generator(ac_id: str, ac_root: Path, tickets_root: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL generate_ticket_from_ac.py CLI end-to-end."""
    cmd = [
        sys.executable, str(GEN_SCRIPT),
        "--ac", ac_id,
        "--ac-root", str(ac_root),
        "--tickets-root", str(tickets_root),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _parse_frontmatter(md_content: str) -> dict:
    parts = md_content.split("---", 2)
    return yaml.safe_load(parts[1])


class TestFilesTouchedExcludesProseIllustrationPaths:
    """AC TKT-600a-1: files_touched excludes prose-illustration paths."""

    def test_files_touched_excludes_prose_illustration_paths(self):
        # covers: TKT-600a-1
        """Illustrative example paths quoted inside a narrative it_requirements
        bullet (used only to describe a scenario, not a real edit surface)
        must NOT appear in _build_files_touched's output. This reproduces the
        exact bullet text pattern from TKT-600a-1's own it_requirements.notes
        field, which triggered the live BO-2600 over-extraction defect.

        To make this pass: restrict _extract_paths_from_prose (or its
        caller, _build_files_touched) so it no longer harvests arbitrary
        '/'-containing tokens from narrative bullets — only the structured
        reference_file_path and edit-surface doc_links may populate
        files_touched.
        """
        ac = {
            "it_requirements": [
                "Two independent defects observed live during the BO-2600 build.",
                (
                    "files_touched over-extraction pulls illustrative example "
                    "paths (e.g. src/foo.py, deploy/foo.py, src/config/foo.py "
                    "used only to describe an exploit scenario) into "
                    "files_touched."
                ),
                "depends_on passthrough writes AC ids verbatim.",
            ],
        }
        files_touched = gen_module._build_files_touched(ac)

        assert "src/foo.py" not in files_touched, (
            f"illustrative example path leaked into files_touched: {files_touched}"
        )
        assert "deploy/foo.py" not in files_touched, (
            f"illustrative example path leaked into files_touched: {files_touched}"
        )
        assert "src/config/foo.py" not in files_touched, (
            f"illustrative example path leaked into files_touched: {files_touched}"
        )


class TestFilesTouchedKeepsRealReferenceFilePath:
    """AC TKT-600a-1: real edit-surface paths are still kept."""

    def test_files_touched_keeps_real_reference_file_path(self):
        # covers: TKT-600a-1
        """The structured reference_file_path and edit-surface doc_links
        (relationship in {constrains, creates, implements, modifies,
        specifies}) must still appear in files_touched after the prose
        over-extraction fix — this guards against an overcorrection that
        drops real edit-surface paths along with the illustrative ones.
        """
        ac = {
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "doc_links": [
                {
                    "path": "templates/skills/build-ac/SKILL.md",
                    "relationship": "modifies",
                    "status": "exists",
                },
                {
                    "path": "https://example.com/spec",
                    "relationship": "related",
                    "status": "exists",
                },
            ],
        }
        files_touched = gen_module._build_files_touched(ac)

        assert "scripts/ac_store/generate_ticket_from_ac.py" in files_touched
        assert "templates/skills/build-ac/SKILL.md" in files_touched
        assert not any(f.startswith("http") for f in files_touched)


class TestDependsOnDropsStructuralParent:
    """AC TKT-600a-1: a leaf AC whose only dep is its structural parent -> []."""

    def test_depends_on_drops_structural_parent(self, tmp_path: Path) -> None:
        # covers: TKT-600a-1
        """A standalone leaf AC whose only depends_on entry is its own
        structural parent (e.g. TKTX-600a-1 -> TKTX-600a via
        ac_parent_id.derive_parent_id) must yield a generated ticket with
        depends_on: [] — never a dangling AC-id reference the
        ticket_frontmatter_guard would reject. Runs the REAL CLI entry point
        end-to-end and reads the written ticket file back off disk
        (real-artifact round trip, BP-1100f-2).
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # No ticket exists for the parent — it is a structural parent AC
        # id only, not a sibling ticket in scope.
        child_id = "TKTX-600a-1"
        _write_ac(ac_dir, child_id, {"depends_on": ["TKTX-600a"]})

        result = _run_generator(child_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}\n{result.stdout}"

        ticket_files = list(tickets_dir.glob(f"TICKET-*-{child_id}.md"))
        assert len(ticket_files) == 1
        fm = _parse_frontmatter(ticket_files[0].read_text(encoding="utf-8"))

        assert fm.get("depends_on") == [], (
            f"structural-parent AC id must be dropped, got "
            f"depends_on={fm.get('depends_on')!r}"
        )


class TestDependsOnIsGuardValid:
    """AC TKT-600a-1: depends_on never leaks a raw, unresolvable AC id."""

    def test_depends_on_is_guard_valid(self, tmp_path: Path) -> None:
        # covers: TKT-600a-1
        """A leaf AC whose depends_on lists (a) its structural parent, (b) a
        sibling AC id that DOES have a co-located ticket already generated in
        the same tickets_root, and (c) a dangling AC id with no ticket
        anywhere in scope, must yield a generated ticket whose depends_on:

          * does NOT contain the structural-parent AC id,
          * does NOT contain the dangling AC id,
          * DOES contain the sibling's ticket FILENAME (translated from the
            AC id), so the dependency is preserved rather than silently
            dropped.

        The resulting ticket is then run through the real
        templates/hooks/ticket_frontmatter_guard.py `_check_depends_on()`
        function — the actual guard that blocks a commit — and must produce
        zero depends_on-related errors.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # Sibling AC + its already-generated ticket, co-located in
        # tickets_dir so ticket_frontmatter_guard can resolve it.
        sibling_id = "TKTX-600a-2"
        _write_ac(ac_dir, sibling_id)
        sibling_result = _run_generator(sibling_id, ac_dir, tickets_dir)
        assert sibling_result.returncode == 0, sibling_result.stderr
        sibling_ticket = next(tickets_dir.glob(f"TICKET-*-{sibling_id}.md"))

        child_id = "TKTX-600a-1"
        _write_ac(
            ac_dir,
            child_id,
            {"depends_on": ["TKTX-600a", sibling_id, "TKTX-NOWHERE-9"]},
        )
        result = _run_generator(child_id, ac_dir, tickets_dir)
        assert result.returncode == 0, f"Generator failed: {result.stderr}\n{result.stdout}"

        child_ticket = next(tickets_dir.glob(f"TICKET-*-{child_id}.md"))
        fm = _parse_frontmatter(child_ticket.read_text(encoding="utf-8"))
        depends_on = fm.get("depends_on")
        assert depends_on is not None, (
            f"generated ticket has no depends_on field in frontmatter: {fm!r}"
        )

        assert "TKTX-600a" not in depends_on, (
            f"structural-parent AC id leaked verbatim: {depends_on!r}"
        )
        assert "TKTX-NOWHERE-9" not in depends_on, (
            f"dangling AC id with no ticket in scope leaked verbatim: {depends_on!r}"
        )
        assert sibling_ticket.name in depends_on, (
            f"sibling AC dependency was not translated to its ticket filename "
            f"({sibling_ticket.name!r}); got depends_on={depends_on!r}"
        )

        # Run the REAL guard against the real on-disk ticket.
        guard = _load_guard_module()
        fm_full = guard.parse_frontmatter(child_ticket.read_text(encoding="utf-8"))
        errors = guard._check_depends_on(fm_full, child_ticket)
        assert errors == [], f"ticket_frontmatter_guard depends_on errors: {errors}"
