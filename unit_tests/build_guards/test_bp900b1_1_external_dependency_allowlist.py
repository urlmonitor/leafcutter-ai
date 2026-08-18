"""Dedicated test coverage for AC BP-900b-1-1.

BP-900b-1-1 — Allowlisted external scripts do not trigger broken-reference
failures.

Gherkin (verbatim, docs/acceptance-criteria/build_pipeline/BP-900-deployment-
completeness/BP-900b-1-1.yaml)::

    Given an agent template references a script path "scripts/external_tool.py"
    And that path is listed in the external-dependency allowlist
    (a configuration file or constant that the guard reads),
    When the guard cross-checks references against deployable scripts,
    Then the allowlisted reference is treated as resolved
    And it does NOT appear in the broken-reference list
    And the build exits zero (assuming no other broken references exist)

INVESTIGATION NOTE (ADR-003 Source-of-Truth Discipline, Rule 1 classification):
the behavioral mechanism this AC describes (``EXTERNAL_DEPENDENCY_ALLOWLIST`` /
``check_broken_references`` / ``build_broken_ref_report`` in
``scripts/build_propagation_audit.py``, wired end-to-end into
``build._check_script_reference_guard``) was already authored under a prior
epic (EPIC-BuildGuardFalsePositive/03) and is already exercised indirectly by
``unit_tests/test_build_guard_real_package.py::test_guard_exits_0_on_clean_package``
against the real package. This file adds DIRECT, dedicated unit coverage
(classification: test_drift — no prior test names ``check_broken_references``
or this AC by id) plus a genuine documentation gap this ticket's own
``files_touched`` calls out: ``docs/architecture/components/template-compiler.md``
has no section describing the ``EXTERNAL_DEPENDENCY_ALLOWLIST`` mechanism or
citing AC BP-900b-1-1 by id (confirmed absent via direct grep before writing
this test — see ``TestBP900b11ArchitectureDocDescribesAllowlist`` below). That
test is RED until the doc section is added; the behavioral tests above it are
expected to pass immediately against the existing implementation (see Step 4
"Zero exit" handling in the test-writer contract — documented here rather than
silently treated as a fresh red baseline).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — unit_tests/build_guards/test_*.py is 2 levels down from worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# scripts/ must be in sys.path for build_propagation_audit
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Lazy import so a genuine ImportError is a clear, readable failure rather than
# a collection-time crash for the whole file.
try:
    from build_propagation_audit import (
        build_broken_ref_report,
        check_broken_references,
    )
except ImportError:
    build_broken_ref_report = None  # type: ignore[assignment]
    check_broken_references = None  # type: ignore[assignment]


class _BuildPropagationAuditNotAvailable(ImportError):
    """build_propagation_audit is not importable from scripts/."""

    def __init__(self) -> None:
        super().__init__(
            "build_propagation_audit could not be imported from scripts/ — "
            "check_broken_references / build_broken_ref_report must exist to "
            "satisfy AC BP-900b-1-1."
        )


# ===========================================================================
# BP-900b-1-1 — behavioral: allowlisted reference is treated as resolved
# ===========================================================================


class TestBP900b11AllowlistedReferenceResolved(unittest.TestCase):
    """AC BP-900b-1-1: an allowlisted external script reference is treated
    as resolved and never appears in the broken-reference set, even when it
    is not present in the deployed-scripts set."""

    def test_ac1_allowlisted_reference_not_in_broken_set(self):
        # covers: BP-900b-1-1
        """Given the AC's own literal example path "scripts/external_tool.py"
        is referenced by a template and IS listed in the allowlist, then it
        must NOT appear in the set returned by check_broken_references(),
        even though it is absent from deployed_scripts."""
        if check_broken_references is None:
            raise _BuildPropagationAuditNotAvailable

        refs = {"scripts/external_tool.py"}
        deployed_scripts: set[str] = set()  # the external script is never deployed by us
        allowlist = frozenset({"scripts/external_tool.py"})

        broken = check_broken_references(refs, deployed_scripts, allowlist=allowlist)

        self.assertEqual(
            broken,
            set(),
            "An allowlisted reference must be treated as resolved and must "
            f"NOT appear in the broken-reference set. Got: {broken!r}",
        )

    def test_ac1_non_allowlisted_reference_still_reported_broken(self):
        # covers: BP-900b-1-1
        """Control case: a reference that is neither deployed nor allowlisted
        MUST still be reported broken — the allowlist must not silently
        swallow every unresolved reference, only the ones it explicitly
        names."""
        if check_broken_references is None:
            raise _BuildPropagationAuditNotAvailable

        refs = {"scripts/external_tool.py", "scripts/genuinely_missing.py"}
        deployed_scripts: set[str] = set()
        allowlist = frozenset({"scripts/external_tool.py"})

        broken = check_broken_references(refs, deployed_scripts, allowlist=allowlist)

        self.assertEqual(
            broken,
            {"scripts/genuinely_missing.py"},
            "Only the non-allowlisted, non-deployed reference should be "
            f"reported broken. Got: {broken!r}",
        )


class TestBP900b11BuildExitsZero(unittest.TestCase):
    """AC BP-900b-1-1: 'the build exits zero (assuming no other broken
    references exist)' — modeled here via build_broken_ref_report(), the
    factory build._check_script_reference_guard() uses to decide its exit
    code (empty list -> exit 0; non-empty list -> exit 1)."""

    def test_ac1_report_is_empty_when_only_allowlisted_refs_present(self):
        # covers: BP-900b-1-1
        """When the only unresolved reference is allowlisted, the broken-
        reference report must be empty, which is exactly the condition
        build._check_script_reference_guard() checks before returning 0."""
        if build_broken_ref_report is None:
            raise _BuildPropagationAuditNotAvailable

        refs_to_sources = {
            "scripts/external_tool.py": {"agents/some-agent.md"},
        }
        allowlist = frozenset({"scripts/external_tool.py"})

        entries = build_broken_ref_report(
            refs_to_sources, deployed_scripts=set(), allowlist=allowlist
        )

        self.assertEqual(
            entries,
            [],
            "build_broken_ref_report() must return an empty list when the "
            "only unresolved reference is allowlisted — this is the "
            "condition build._check_script_reference_guard() checks before "
            f"returning exit code 0. Got: {entries!r}",
        )

    def test_ac1_real_default_allowlist_used_when_none_passed(self):
        # covers: BP-900b-1-1
        """The default (module-level) allowlist must be applied automatically
        when no explicit allowlist is passed — this is the path
        build._check_script_reference_guard() actually exercises in
        production (it calls build_broken_ref_report() with no allowlist
        argument)."""
        if build_broken_ref_report is None:
            raise _BuildPropagationAuditNotAvailable

        # scripts/build.py is a REAL entry in the module's default
        # EXTERNAL_DEPENDENCY_ALLOWLIST (self-reference, documented inline in
        # build_propagation_audit.py). Using a real allowlisted entry here
        # (rather than the Gherkin's illustrative "external_tool.py") proves
        # the DEFAULT allowlist — not just a caller-supplied override — is
        # what actually resolves the reference.
        refs_to_sources = {
            "scripts/build.py": {"skills/some-skill/SKILL.md"},
        }

        entries = build_broken_ref_report(refs_to_sources, deployed_scripts=set())

        self.assertEqual(
            entries,
            [],
            "scripts/build.py is a real entry in the module's default "
            "EXTERNAL_DEPENDENCY_ALLOWLIST; build_broken_ref_report() called "
            "with no explicit allowlist argument must still resolve it and "
            f"return an empty list. Got: {entries!r}",
        )


# ===========================================================================
# BP-900b-1-1 — documentation coverage: template-compiler.md must describe
# the external-dependency allowlist mechanism by name
# ===========================================================================


class TestBP900b11ArchitectureDocDescribesAllowlist(unittest.TestCase):
    """AC BP-900b-1-1: docs/architecture/components/template-compiler.md must
    document the external-dependency allowlist mechanism.

    ``docs/architecture/components/template-compiler.md`` is one of this
    ticket's declared ``files_touched`` targets. As of writing this test, the
    document mentions the lower-case phrase "external-dependency allowlist"
    only once, in passing, as one of three suggested-action descriptions for
    an unrelated AC (BP-900c-1) — it never names the actual
    ``EXTERNAL_DEPENDENCY_ALLOWLIST`` constant, never cites AC BP-900b-1-1 by
    id, and never states the resolved/not-broken/exit-zero semantics this AC
    requires. Confirmed absent via direct grep before authoring this test.
    This test is expected to be RED until a dedicated section is added.
    """

    def test_ac1_doc_names_allowlist_constant_and_ac_id(self):
        # covers: BP-900b-1-1
        """template-compiler.md must name the EXTERNAL_DEPENDENCY_ALLOWLIST
        constant and cite AC BP-900b-1-1, so a reader of the architecture doc
        can find the external-dependency allowlist mechanism without reading
        the source directly."""
        doc_path = (
            _REPO_ROOT
            / "docs"
            / "architecture"
            / "components"
            / "template-compiler.md"
        )
        self.assertTrue(
            doc_path.is_file(),
            f"Expected architecture doc at {doc_path} — this ticket's own "
            "files_touched names it.",
        )
        text = doc_path.read_text(encoding="utf-8")

        self.assertIn(
            "EXTERNAL_DEPENDENCY_ALLOWLIST",
            text,
            "template-compiler.md must name the EXTERNAL_DEPENDENCY_ALLOWLIST "
            "constant (scripts/build_propagation_audit.py) explicitly, not "
            "just paraphrase it as 'external-dependency allowlist'.",
        )
        self.assertIn(
            "BP-900b-1-1",
            text,
            "template-compiler.md must cite AC BP-900b-1-1 by id in the "
            "section documenting the external-dependency allowlist "
            "mechanism, matching the convention used by the doc's other "
            "AC-specific sections (e.g. 'AC BP-900b-1', 'AC BP-900c-1').",
        )
        self.assertIn(
            "does NOT appear in the broken-reference",
            text,
            "template-compiler.md must state the AC's resolved/not-broken "
            "semantics — that an allowlisted reference does NOT appear in "
            "the broken-reference report — not just name the constant.",
        )


if __name__ == "__main__":
    unittest.main()
