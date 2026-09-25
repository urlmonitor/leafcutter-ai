"""
MODULE: test_inf_1100d_3_ii
AC: INF-1100d-3-ii -- "A database test run without the setting stops and
    names the missing setting"

GOAL: Behavioral, subprocess-driven tests proving (a) a real Step-2b
    pattern-shaped DB test ends as pytest ERROR (never PASSED, never
    SKIPPED) and attempts zero connections when db_connection_test is
    unset/blank, (b) the shared resolver returns a configured address
    verbatim, and (c) the resolver in scripts/db_check/checker.py is the
    ONLY reader of testing_context.db_connection_test -- the same module
    INF-1100d-3-i's checker lives in.

The module under test (scripts/db_check/checker.py) does not exist yet:
test-writer runs BEFORE python-coder. Every test below is RED by
construction; imports happen lazily inside test bodies so a missing module
surfaces as a per-test failure rather than a whole-file collection error.

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "resolver returns '' / None and lets the driver default connect" ->
      P2 attempts a connection -> caught by the CONNECT_ATTEMPTED.flag
      assertion in test_db_pattern_test_errors_naming_setting_when_unset_or_blank.
    - "pytest.skip on unset" -> caught by the ERROR-outcome (not SKIPPED)
      assertion in the same test.
    - "checker keeps its own blank-check" -> caught by
      test_checker_and_db_pattern_share_one_resolver's stub-substitution
      counterfactual.
    - "always raise" -> caught by test_resolver_returns_project_address_verbatim
      (P3 must NOT raise) and by the seam test's P3 case.
"""
# @ac-tag: INF-1100d-3-ii

from __future__ import annotations

import sys
import unittest

from ._inf_1100d_3_db_check_harness import (
    RESOLVER_P3_ADDRESS,
    SCRIPTS_DIR,
    STUB_RESOLVER_ADDRESS,
    make_tmp_dir,
    run_pattern_shaped_pytest,
    write_pattern_shaped_project,
    write_project,
)


class TestDbPatternEndsInErrorWhenUnconfigured(unittest.TestCase):
    def _assert_pattern_errors_with_zero_connections(self, testing_context: dict) -> None:
        paths = write_pattern_shaped_project(make_tmp_dir("inf1100d3ii_pattern_"), testing_context)
        result = run_pattern_shaped_pytest(paths, timeout=8.0)
        combined = (result.stdout or "") + "\n" + (result.stderr or "")

        self.assertNotEqual(
            result.returncode,
            0,
            f"pattern-shaped test must not exit 0 when unconfigured. output:\n{combined}",
        )
        lowered = combined.lower()
        self.assertIn(
            "error",
            lowered,
            f"expected an ERROR outcome (not passed, not skipped). output:\n{combined}",
        )
        self.assertNotIn(
            "1 passed",
            lowered,
            f"must_catch 'pytest.skip on unset' surrogate -- test must not pass. output:\n{combined}",
        )
        self.assertNotIn(
            "skipped",
            lowered,
            f"must_catch 'pytest.skip on unset' -- ERROR, not SKIPPED. output:\n{combined}",
        )
        self.assertIn(
            "testing_context.db_connection_test",
            combined,
            f"error message must name the missing setting. output:\n{combined}",
        )
        self.assertFalse(
            paths["connect_flag"].exists(),
            "must_catch \"resolver returns '' / None and lets the driver default "
            "connect\": the psycopg2 stub recorded a connect() attempt for an "
            f"unconfigured setting: {paths['connect_flag'].read_text() if paths['connect_flag'].exists() else ''}",
        )

    def test_db_pattern_test_errors_naming_setting_when_unset_or_blank(self):
        # covers: INF-1100d-3-ii
        # angle: reachability
        """P1 (unset) and P2 ('   ') -- a real Step-2b pattern-shaped test,
        run by pytest as a real subprocess in a temp project, must end as
        ERROR, name testing_context.db_connection_test, and never let a
        driver connect() fire."""
        self._assert_pattern_errors_with_zero_connections({})
        self._assert_pattern_errors_with_zero_connections({"db_connection_test": "   "})


class TestResolverReturnsAddressVerbatim(unittest.TestCase):
    def test_resolver_returns_project_address_verbatim(self):
        # covers: INF-1100d-3-ii
        # angle: criterion
        """P3: the resolver returns EXACTLY
        postgresql://app:app@db.internal:5432/app_test -- no trimming, no
        normalisation, no credential rewriting. This is also the control
        against a resolver that always raises (must_catch: 'always
        raise')."""
        project_root = write_project(
            make_tmp_dir("inf1100d3ii_resolver_"),
            {"db_connection_test": RESOLVER_P3_ADDRESS},
        )
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        from db_check.checker import resolve_test_db_address  # type: ignore[import-not-found]

        result = resolve_test_db_address(project_root)
        self.assertEqual(result, RESOLVER_P3_ADDRESS)


class TestCheckerAndResolverShareOneReader(unittest.TestCase):
    def test_checker_and_db_pattern_share_one_resolver(self):
        # covers: INF-1100d-3-ii
        # angle: seam
        """For P1, P2 and P3 the INF-1100d-3-i checker's verdict and the
        resolver's own outcome agree, AND substituting a stub resolver
        function directly on the shared module object changes the
        checker's verdict for the SAME blank project -- proving the checker
        has no second, duplicated blank-check of its own (must_catch:
        'checker keeps its own blank-check')."""
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import db_check.checker as checker_module  # type: ignore[import-not-found]

        cases = [
            ({}, "not_configured"),
            ({"db_connection_test": "   "}, "not_configured"),
            ({"db_connection_test": RESOLVER_P3_ADDRESS}, "configured"),
        ]

        for testing_context, expectation in cases:
            with self.subTest(testing_context=testing_context):
                project_root = write_project(make_tmp_dir("inf1100d3ii_seam_"), testing_context)

                check_result = checker_module.check_test_db(project_root)
                resolver_raised = False
                try:
                    checker_module.resolve_test_db_address(project_root)
                except Exception:  # noqa: BLE001 -- black-box probe: the AC does not
                    # yet fix the resolver's exception TYPE, only that it raises
                    # (naming the setting) when unconfigured, so this test must
                    # accept whatever exception class the real implementation uses.
                    resolver_raised = True

                if expectation == "not_configured":
                    self.assertEqual(check_result.get("status"), "not_configured")
                    self.assertTrue(
                        resolver_raised,
                        "resolver must raise when the checker reports not_configured "
                        "for the SAME project -- disagreement means a second reader.",
                    )
                else:
                    self.assertNotEqual(check_result.get("status"), "not_configured")
                    self.assertFalse(
                        resolver_raised,
                        "must_catch 'always raise': resolver must not raise on a "
                        "configured (P3) project.",
                    )

        # Counterfactual: substitute ONLY the resolver function on the
        # shared module object; the checker's own verdict for a blank
        # project must flip away from not_configured if (and only if) the
        # checker actually calls through this module attribute rather than
        # re-implementing its own blank-check.
        blank_project = write_project(make_tmp_dir("inf1100d3ii_seam_stub_"), {})
        original_resolver = checker_module.resolve_test_db_address

        def _stub_resolver(target_root):
            return STUB_RESOLVER_ADDRESS

        checker_module.resolve_test_db_address = _stub_resolver
        try:
            stubbed_result = checker_module.check_test_db(blank_project)
        finally:
            checker_module.resolve_test_db_address = original_resolver

        self.assertNotEqual(
            stubbed_result.get("status"),
            "not_configured",
            "must_catch 'checker keeps its own blank-check': substituting the "
            "shared resolver did not change the checker's verdict for a blank "
            f"project. got: {stubbed_result!r}",
        )


if __name__ == "__main__":
    unittest.main()
